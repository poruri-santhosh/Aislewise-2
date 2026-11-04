import os
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import psycopg2
from dotenv import load_dotenv
from flask import Flask, current_app, jsonify, render_template, request
from psycopg2.extras import Json, RealDictCursor

from shopper_review_schema import validate_shopper_review_payload


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, template_folder="templates", static_folder="public/static")


class DatabaseConfigurationError(RuntimeError):
    pass


class SentimentModelUnavailable(RuntimeError):
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


@lru_cache(maxsize=1)
def load_registered_sentiment_model(tracking_uri, model_name):
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
    except ImportError as error:
        raise SentimentModelUnavailable(
            "MLflow and the model's Python dependencies are not installed."
        ) from error

    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)
    try:
        registered_model = client.get_registered_model(model_name)
    except mlflow.exceptions.MlflowException as error:
        raise SentimentModelUnavailable(
            f"The registered sentiment model {model_name!r} could not be found."
        ) from error

    ready_versions = [
        version for version in registered_model.latest_versions if version.status == "READY"
    ]
    if not ready_versions:
        raise SentimentModelUnavailable(
            f"The registered sentiment model {model_name!r} has no ready version."
        )

    latest_version = max(ready_versions, key=lambda version: int(version.version))
    try:
        return mlflow.sklearn.load_model(
            f"models:/{model_name}/{latest_version.version}"
        )
    except (ImportError, OSError, ValueError, mlflow.exceptions.MlflowException) as error:
        raise SentimentModelUnavailable(
            f"The registered sentiment model {model_name!r} could not be loaded."
        ) from error


def predict_shopper_sentiment(review_text):
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "").strip()
    if not tracking_uri:
        local_registry = BASE_DIR / "mlflow.db"
        if not local_registry.is_file():
            raise SentimentModelUnavailable(
                "Set MLFLOW_TRACKING_URI to a reachable MLflow model registry."
            )
        tracking_uri = f"sqlite:///{local_registry.as_posix()}"

    model_name = os.getenv("MLFLOW_MODEL_NAME", "Aislewise_Sentiment_Model").strip()
    if not model_name:
        raise SentimentModelUnavailable("MLFLOW_MODEL_NAME must not be empty.")

    model = load_registered_sentiment_model(tracking_uri, model_name)
    try:
        prediction = model.predict([review_text])[0]
    except (ImportError, OSError, TypeError, ValueError) as error:
        raise SentimentModelUnavailable(
            "The registered sentiment model could not evaluate this review."
        ) from error

    label = str(prediction).strip().lower()
    if label in {"1", "1.0", "true", "positive"}:
        return "positive"
    if label in {"0", "0.0", "false", "negative"}:
        return "negative"
    raise SentimentModelUnavailable(
        "The registered sentiment model returned an unsupported sentiment label."
    )


def serialize_shopper_feedback(row):
    return {
        "id": row["id"],
        "customer_name": row["customer_name"],
        "rating": int(row["rating"]),
        "review_text": row["review_text"],
        "sentiment": row["sentiment"],
        "dwell_time_seconds": float(row["dwell_time_seconds"]),
        "cart_items": row["cart_items"],
        "created_at": row["created_at"].isoformat(),
    }


def shopper_feedback_storage_error_response(error):
    current_app.logger.error("Shopper feedback PostgreSQL request failed (%s)", type(error).__name__)
    return jsonify(
        error="Shopper feedback storage is unavailable. Check the PostgreSQL connection and migration."
    ), 503


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


@app.get("/api/shopper-reviews")
def shopper_reviews():
    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        customer_name,
                        rating,
                        review_text,
                        sentiment,
                        dwell_time_seconds,
                        cart_items,
                        created_at
                    FROM shopper_feedback
                    ORDER BY created_at DESC, id DESC
                    LIMIT 20
                    """
                )
                rows = cursor.fetchall()
                cursor.execute("SELECT COUNT(*) AS total FROM shopper_feedback")
                total = cursor.fetchone()["total"]
        return jsonify(
            reviews=[serialize_shopper_feedback(row) for row in rows],
            total=total,
        )
    except psycopg2.errors.UndefinedTable as error:
        current_app.logger.error("Shopper feedback migration has not been applied")
        return jsonify(
            error="Shopper feedback is not initialized. Apply migrations/001_create_shopper_feedback.sql."
        ), 503
    except (DatabaseConfigurationError, psycopg2.Error) as error:
        return shopper_feedback_storage_error_response(error)


@app.post("/api/reviews")
def submit_shopper_review():
    if not request.is_json:
        return jsonify(error="Submit feedback using a JSON request."), 400

    try:
        review = validate_shopper_review_payload(request.get_json(silent=True))
    except ValueError as error:
        return jsonify(error=str(error)), 400

    try:
        sentiment = predict_shopper_sentiment(review["review_text"])
    except SentimentModelUnavailable as error:
        current_app.logger.error("Shopper feedback sentiment inference failed: %s", error)
        return jsonify(
            error="The sentiment model is unavailable. Feedback was not saved; try again later."
        ), 503

    try:
        with database_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    INSERT INTO shopper_feedback (
                        customer_name,
                        rating,
                        review_text,
                        sentiment,
                        dwell_time_seconds,
                        cart_items
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        customer_name,
                        rating,
                        review_text,
                        sentiment,
                        dwell_time_seconds,
                        cart_items,
                        created_at
                    """,
                    (
                        review["customer_name"],
                        review["rating"],
                        review["review_text"],
                        sentiment,
                        review["dwell_time_seconds"],
                        Json(review["cart_items"]),
                    ),
                )
                saved_review = cursor.fetchone()
            connection.commit()
        return jsonify(review=serialize_shopper_feedback(saved_review)), 201
    except psycopg2.errors.UndefinedTable as error:
        current_app.logger.error("Shopper feedback migration has not been applied")
        return jsonify(
            error="Shopper feedback is not initialized. Apply migrations/001_create_shopper_feedback.sql."
        ), 503
    except (DatabaseConfigurationError, psycopg2.Error) as error:
        return shopper_feedback_storage_error_response(error)


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes"}
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=debug,
    )
