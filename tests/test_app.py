import os
from contextlib import contextmanager
from decimal import Decimal

import pytest

import app as web_app


class FakeCursor:
    def __init__(self):
        self.query = ""
        self.parameters = ()
        self.result = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters=()):
        self.query = query
        self.parameters = parameters
        if "COUNT(DISTINCT r.product_id)" in query:
            self.result = {
                "total_reviews": 50000,
                "reviewed_products": 15641,
                "average_rating": Decimal("4.21"),
                "verified_reviews": 25000,
            }
        elif "COUNT(*) AS total" in query:
            self.result = {"total": 1}
        elif "SELECT 1" in query:
            self.result = {"?column?": 1}
        elif "SELECT\n                        r.review_id" in query:
            self.rows = [
                {
                    "review_id": "rev_1",
                    "product_id": "B000TEST01",
                    "product_title": "Test product",
                    "main_category": "Appliances",
                    "rating": Decimal("5.0"),
                    "review_title": "Works well",
                    "review_text": "A complete customer review.",
                    "timestamp": 1679243855665,
                    "verified_purchase": True,
                    "helpful_vote": 3,
                }
            ]

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self):
        self.last_cursor = None

    def cursor(self, **_kwargs):
        self.last_cursor = FakeCursor()
        return self.last_cursor

    def close(self):
        pass


@pytest.fixture
def client(monkeypatch):
    connection = FakeConnection()

    @contextmanager
    def fake_database_connection():
        yield connection

    monkeypatch.setattr(web_app, "database_connection", fake_database_connection)
    web_app.app.config.update(TESTING=True)
    return web_app.app.test_client(), connection


def test_homepage_renders_review_catalogue(client):
    response = client[0].get("/")

    assert response.status_code == 200
    assert b"Every review." in response.data
    assert b"Customer reviews" in response.data
    assert client[0].get("/static/css/styles.css").status_code == 200
    assert client[0].get("/static/js/reviews.js").status_code == 200


def test_summary_returns_catalogue_metrics(client):
    response = client[0].get("/api/summary")

    assert response.status_code == 200
    assert response.json == {
        "total_reviews": 50000,
        "reviewed_products": 15641,
        "average_rating": 4.21,
        "verified_reviews": 25000,
    }


def test_reviews_support_search_filters_and_pagination(client):
    test_client, connection = client
    response = test_client.get(
        "/api/reviews?q=ice+maker&product_id=B000&rating=5"
        "&verified=true&page=2&page_size=20&sort=helpful"
    )

    assert response.status_code == 200
    assert response.json["page"] == 2
    assert response.json["total"] == 1
    assert response.json["reviews"][0]["review_text"] == "A complete customer review."
    assert response.json["reviews"][0]["rating"] == 5.0
    assert tuple(connection.last_cursor.parameters) == (
        "%ice maker%",
        "%ice maker%",
        "%ice maker%",
        "%ice maker%",
        "%B000%",
        5,
        True,
        20,
        20,
    )
    assert "ILIKE" in connection.last_cursor.query
    assert "ORDER BY r.helpful_vote DESC" in connection.last_cursor.query


@pytest.mark.parametrize(
    ("query_string", "message"),
    [
        ("page=0", "page must be a positive whole number."),
        ("page_size=500", "page_size must be 20, 50, or 100."),
        ("rating=6", "rating must be a whole number from 1 to 5."),
        ("verified=maybe", "verified must be true or false."),
        ("sort=arbitrary", "Unknown sort option."),
    ],
)
def test_invalid_review_filters_return_clear_errors(client, query_string, message):
    response = client[0].get(f"/api/reviews?{query_string}")

    assert response.status_code == 400
    assert response.json["error"] == message


def test_database_configuration_error_is_visible(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)

    response = web_app.app.test_client().get("/api/summary")

    assert response.status_code == 503
    assert "PostgreSQL is unavailable" in response.json["error"]


@pytest.mark.integration
def test_live_postgres_serves_the_full_review_catalogue():
    if not (os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")):
        pytest.skip("Set DATABASE_URL or NEON_DATABASE_URL to run PostgreSQL integration checks.")

    test_client = web_app.app.test_client()
    health = test_client.get("/health")
    assert health.status_code == 200
    assert health.json["database"] == "connected"

    summary_response = test_client.get("/api/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json
    assert summary["total_reviews"] > 0
    assert summary["reviewed_products"] > 0

    page_size = 100
    first_page = test_client.get(f"/api/reviews?page=1&page_size={page_size}")
    assert first_page.status_code == 200
    assert len(first_page.json["reviews"]) == page_size
    assert first_page.json["total"] == summary["total_reviews"]

    last_page_number = first_page.json["total_pages"]
    last_page = test_client.get(
        f"/api/reviews?page={last_page_number}&page_size={page_size}"
    )
    assert last_page.status_code == 200
    assert 0 < len(last_page.json["reviews"]) <= page_size

    product_id = first_page.json["reviews"][0]["product_id"]
    product_reviews = test_client.get(
        f"/api/reviews?product_id={product_id}&page_size=20"
    )
    assert product_reviews.status_code == 200
    assert product_reviews.json["total"] > 0
    assert all(
        review["product_id"] == product_id
        for review in product_reviews.json["reviews"]
    )

    filtered_reviews = test_client.get(
        "/api/reviews?rating=5&verified=true&sort=rating_low&page_size=20"
    )
    assert filtered_reviews.status_code == 200
    assert all(
        review["rating"] == 5 and review["verified_purchase"]
        for review in filtered_reviews.json["reviews"]
    )

    search_results = test_client.get(f"/api/reviews?q={product_id}&page_size=20")
    assert search_results.status_code == 200
    assert search_results.json["total"] > 0
    assert all(product_id in review["product_id"] for review in search_results.json["reviews"])
