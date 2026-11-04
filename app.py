import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import psycopg2
from dotenv import load_dotenv
from flask import Flask, current_app, jsonify, render_template, request
from psycopg2.extras import RealDictCursor


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, template_folder="templates", static_folder="public/static")


class DatabaseConfigurationError(RuntimeError):
    pass


@contextmanager
def database_connection():
    database_url = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")
    if not database_url:
        raise DatabaseConfigurationError(
            "Set DATABASE_URL (or the existing NEON_DATABASE_URL) to connect to PostgreSQL."
        )

    try:
        hostname = urlsplit(database_url).hostname
    except ValueError as error:
        raise DatabaseConfigurationError("DATABASE_URL is not a valid PostgreSQL URL.") from error

    default_sslmode = "disable" if hostname in {"localhost", "127.0.0.1", "::1"} else "require"
    sslmode = os.getenv("DATABASE_SSLMODE", default_sslmode)
    connection = psycopg2.connect(
        database_url,
        sslmode=sslmode,
        connect_timeout=10,
    )
    try:
        yield connection
    finally:
        connection.close()


def database_error_response(error):
    current_app.logger.error("PostgreSQL request failed (%s)", type(error).__name__)
    return jsonify(
        error="PostgreSQL is unavailable. Check the database URL, network access, and table setup."
    ), 503


def parse_positive_integer(value, name):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a positive whole number.") from None
    if parsed < 1:
        raise ValueError(f"{name} must be a positive whole number.")
    return parsed


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return jsonify(status="ok", database="connected")
    except (DatabaseConfigurationError, psycopg2.Error) as error:
        return database_error_response(error)


@app.get("/api/summary")
def summary():
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) AS total_reviews,
                        COUNT(DISTINCT r.product_id) AS reviewed_products,
                        ROUND(AVG(r.rating), 2) AS average_rating,
                        COUNT(*) FILTER (WHERE r.verified_purchase IS TRUE) AS verified_reviews
                    FROM reviews AS r
                    """
                )
                result = cursor.fetchone()
        return jsonify(
            total_reviews=result["total_reviews"],
            reviewed_products=result["reviewed_products"],
            average_rating=float(result["average_rating"] or 0),
            verified_reviews=result["verified_reviews"],
        )
    except (DatabaseConfigurationError, psycopg2.Error) as error:
        return database_error_response(error)


@app.get("/api/reviews")
def reviews():
    try:
        page = parse_positive_integer(request.args.get("page", "1"), "page")
        page_size = parse_positive_integer(request.args.get("page_size", "20"), "page_size")
    except ValueError as error:
        return jsonify(error=str(error)), 400

    if page_size not in {20, 50, 100}:
        return jsonify(error="page_size must be 20, 50, or 100."), 400

    search = request.args.get("q", "").strip()
    product_id = request.args.get("product_id", "").strip()
    if len(search) > 120 or len(product_id) > 128:
        return jsonify(error="Search text or product ID is too long."), 400

    rating = request.args.get("rating", "").strip()
    if rating:
        try:
            rating_value = int(rating)
        except ValueError:
            return jsonify(error="rating must be a whole number from 1 to 5."), 400
        if rating_value not in {1, 2, 3, 4, 5}:
            return jsonify(error="rating must be a whole number from 1 to 5."), 400
    else:
        rating_value = None

    verified = request.args.get("verified", "").strip().lower()
    if verified not in {"", "true", "false"}:
        return jsonify(error="verified must be true or false."), 400

    sort_key = request.args.get("sort", "newest")
    sort_options = {
        "newest": "r.timestamp DESC NULLS LAST, r.review_id",
        "oldest": "r.timestamp ASC NULLS LAST, r.review_id",
        "rating_high": "r.rating DESC, r.timestamp DESC NULLS LAST, r.review_id",
        "rating_low": "r.rating ASC, r.timestamp DESC NULLS LAST, r.review_id",
        "helpful": "r.helpful_vote DESC NULLS LAST, r.timestamp DESC NULLS LAST, r.review_id",
    }
    if sort_key not in sort_options:
        return jsonify(error="Unknown sort option."), 400

    conditions = []
    parameters = []
    if search:
        conditions.append(
            "(r.product_id ILIKE %s OR p.title ILIKE %s OR r.title ILIKE %s OR r.text ILIKE %s)"
        )
        search_pattern = f"%{search}%"
        parameters.extend([search_pattern] * 4)
    if product_id:
        conditions.append("r.product_id ILIKE %s")
        parameters.append(f"%{product_id}%")
    if rating_value is not None:
        conditions.append("r.rating = %s")
        parameters.append(rating_value)
    if verified:
        conditions.append("r.verified_purchase IS %s")
        parameters.append(verified == "true")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * page_size

    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM reviews AS r
                    LEFT JOIN products AS p ON p.product_id = r.product_id
                    {where_clause}
                    """,
                    parameters,
                )
                total = cursor.fetchone()["total"]
                cursor.execute(
                    f"""
                    SELECT
                        r.review_id,
                        r.product_id,
                        p.title AS product_title,
                        p.main_category,
                        r.rating,
                        r.title AS review_title,
                        r.text AS review_text,
                        r.timestamp,
                        r.verified_purchase,
                        r.helpful_vote
                    FROM reviews AS r
                    LEFT JOIN products AS p ON p.product_id = r.product_id
                    {where_clause}
                    ORDER BY {sort_options[sort_key]}
                    LIMIT %s OFFSET %s
                    """,
                    [*parameters, page_size, offset],
                )
                review_rows = cursor.fetchall()
    except (DatabaseConfigurationError, psycopg2.Error) as error:
        return database_error_response(error)

    results = []
    for row in review_rows:
        results.append(
            {
                **row,
                "rating": float(row["rating"]) if row["rating"] is not None else None,
                "timestamp": int(row["timestamp"]) if row["timestamp"] is not None else None,
            }
        )

    return jsonify(
        reviews=results,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes"}
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=debug,
    )
