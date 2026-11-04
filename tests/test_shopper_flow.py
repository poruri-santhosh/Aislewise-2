from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

import app as web_app


class ShopperCursor:
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
        if "INSERT INTO shopper_feedback" in query:
            self.result = {
                "id": 41,
                "customer_name": parameters[0],
                "rating": parameters[1],
                "review_text": parameters[2],
                "sentiment": parameters[3],
                "dwell_time_seconds": parameters[4],
                "cart_items": ["milk", "bread"],
                "created_at": datetime(2026, 11, 4, tzinfo=timezone.utc),
            }
        elif "SELECT COUNT(*) AS total FROM shopper_feedback" in query:
            self.result = {"total": 1}
        elif "FROM shopper_feedback" in query:
            self.rows = [
                {
                    "id": 41,
                    "customer_name": "Aislewise shopper",
                    "rating": 5,
                    "review_text": "The route was easy to follow.",
                    "sentiment": "positive",
                    "dwell_time_seconds": 82.0,
                    "cart_items": ["milk", "bread"],
                    "created_at": datetime(2026, 11, 4, tzinfo=timezone.utc),
                }
            ]

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.rows


class ShopperConnection:
    def __init__(self):
        self.cursor_instance = None
        self.committed = False

    def cursor(self, **_kwargs):
        self.cursor_instance = ShopperCursor()
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def close(self):
        pass


@pytest.fixture
def shopper_client(monkeypatch):
    connection = ShopperConnection()

    @contextmanager
    def fake_database_connection():
        yield connection

    monkeypatch.setattr(web_app, "database_connection", fake_database_connection)
    monkeypatch.setattr(web_app, "predict_shopper_sentiment", lambda _text: "positive")
    web_app.app.config.update(TESTING=True)
    return web_app.app.test_client(), connection


def valid_feedback_payload():
    return {
        "customer_name": "  Aislewise shopper  ",
        "rating": 5,
        "review_text": "  The route was easy to follow.  ",
        "dwell_time_seconds": 82,
        "cart_items": ["milk", "bread"],
    }


def test_shopper_mode_and_feedback_form_render(shopper_client):
    response = shopper_client[0].get("/")

    assert response.status_code == 200
    assert b"Shopper Navigation" in response.data
    assert b"Product Intelligence" in response.data
    assert b'id="store-map"' in response.data
    assert b'id="checkout-dialog"' in response.data


def test_shopper_review_is_validated_scored_and_saved(shopper_client):
    test_client, connection = shopper_client
    response = test_client.post("/api/reviews", json=valid_feedback_payload())

    assert response.status_code == 201
    assert response.json["review"]["id"] == 41
    assert response.json["review"]["sentiment"] == "positive"
    assert connection.committed
    assert "INSERT INTO shopper_feedback" in connection.cursor_instance.query
    assert connection.cursor_instance.parameters[:5] == (
        "Aislewise shopper",
        5,
        "The route was easy to follow.",
        "positive",
        82.0,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("customer_name", "  "),
        ("rating", 6),
        ("rating", True),
        ("review_text", ""),
        ("dwell_time_seconds", -1),
        ("dwell_time_seconds", float("inf")),
        ("dwell_time_seconds", 10**400),
        ("cart_items", ["unknown"]),
    ],
)
def test_invalid_shopper_feedback_is_rejected_before_database_write(
    shopper_client, field, value
):
    test_client, connection = shopper_client
    payload = valid_feedback_payload()
    payload[field] = value

    response = test_client.post("/api/reviews", json=payload)

    assert response.status_code == 400
    assert response.json["error"]
    assert connection.cursor_instance is None


def test_shopper_review_catalogue_returns_persisted_feedback(shopper_client):
    response = shopper_client[0].get("/api/shopper-reviews")

    assert response.status_code == 200
    assert response.json["total"] == 1
    assert response.json["reviews"][0]["sentiment"] == "positive"
    assert response.json["reviews"][0]["cart_items"] == ["milk", "bread"]


def test_unavailable_sentiment_model_does_not_save_feedback(shopper_client, monkeypatch):
    test_client, connection = shopper_client

    def unavailable_model(_text):
        raise web_app.SentimentModelUnavailable("Registry unavailable.")

    monkeypatch.setattr(web_app, "predict_shopper_sentiment", unavailable_model)
    response = test_client.post("/api/reviews", json=valid_feedback_payload())

    assert response.status_code == 503
    assert "Feedback was not saved" in response.json["error"]
    assert connection.cursor_instance is None
