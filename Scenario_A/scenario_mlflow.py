import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient


MODEL_NAME = "Aislewise_Sentiment_Model"


def load_sentiment_model():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    client = MlflowClient()
    versions = client.search_model_versions(f"name='{MODEL_NAME}'")
    ready_versions = [
        version for version in versions if version.status.upper() == "READY"
    ]
    if not ready_versions:
        raise RuntimeError(f"No READY version of {MODEL_NAME!r} is registered.")

    latest_version = max(ready_versions, key=lambda version: int(version.version))
    try:
        return mlflow.sklearn.load_model(
            f"models:/{MODEL_NAME}/{latest_version.version}"
        )
    except Exception as error:
        raise RuntimeError(
            f"Could not load registered {MODEL_NAME!r} version "
            f"{latest_version.version}."
        ) from error


def infer_review_sentiment(model, reviews):
    if reviews.empty:
        reviews = reviews.copy()
        reviews["sentiment"] = []
        reviews["ml_confidence"] = []
        return reviews

    text_column = "review_text" if "review_text" in reviews.columns else "text"
    if text_column not in reviews.columns:
        raise ValueError("Review data must include a 'text' or 'review_text' column.")

    texts = reviews[text_column].fillna("").astype(str).tolist()
    predictions = model.predict(texts)
    probabilities = model.predict_proba(texts)
    if len(predictions) != len(reviews) or len(probabilities) != len(reviews):
        raise ValueError("The sentiment model returned a different number of rows than it received.")

    class_labels = [str(label).strip().lower() for label in model.classes_]
    if len(probabilities[0]) != len(class_labels):
        raise ValueError("The sentiment model probability classes are inconsistent.")

    sentiments = []
    confidences = []
    for prediction, probabilities_for_row in zip(predictions, probabilities):
        label = str(prediction).strip().lower()
        if label in {"1", "1.0", "true", "positive"}:
            sentiment = "positive"
        elif label in {"0", "0.0", "false", "negative"}:
            sentiment = "negative"
        else:
            raise ValueError(f"Unsupported sentiment model label: {label!r}.")

        class_probabilities = dict(zip(class_labels, probabilities_for_row))
        confidence = class_probabilities.get(label)
        if confidence is None:
            target_label = "1" if sentiment == "positive" else "0"
            confidence = class_probabilities.get(target_label)
        if confidence is None:
            target_label = sentiment
            confidence = class_probabilities.get(target_label)
        if confidence is None:
            raise ValueError(f"No probability was returned for sentiment {sentiment!r}.")

        sentiments.append(sentiment)
        confidences.append(float(confidence))

    result = reviews.copy()
    result["sentiment"] = sentiments
    result["ml_confidence"] = confidences
    return result


def register_ml_reviews(connection):
    sentiment_model = load_sentiment_model()
    reviews = connection.execute("SELECT * FROM silver_reviews").df()
    reviews = infer_review_sentiment(sentiment_model, reviews)
    return register_ml_review_frame(connection, reviews)


def register_ml_review_frame(connection, reviews):
    connection.register("silver_reviews_ml", reviews)

    connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE gold_product_discrepancy_flags_ml AS
        WITH product_reviews AS (
            SELECT
                product_id,
                COUNT(*) AS total_reviews,
                ROUND(AVG(rating), 2) AS avg_star_rating,
                COUNT(*) FILTER (WHERE sentiment = 'positive') AS pos_count,
                COUNT(*) FILTER (WHERE sentiment = 'negative') AS neg_count,
                ROUND(
                    COUNT(*) FILTER (WHERE sentiment = 'positive') * 100.0
                    / NULLIF(COUNT(*), 0),
                    2
                ) AS positive_pct,
                ROUND(
                    COUNT(*) FILTER (WHERE sentiment = 'negative') * 100.0
                    / NULLIF(COUNT(*), 0),
                    2
                ) AS negative_pct,
                COALESCE(AVG(COALESCE(ml_confidence, 1.0)), 1.0) AS avg_ml_confidence
            FROM silver_reviews_ml
            GROUP BY product_id
        )
        SELECT
            *,
            CASE
                WHEN avg_star_rating >= 4.0 AND negative_pct >= 35.0
                    THEN 'INVESTIGATE_SCENARIO_A'
                WHEN avg_star_rating <= 3.0 AND positive_pct >= 65.0
                    THEN 'INVESTIGATE_SCENARIO_B'
                WHEN avg_star_rating <= 2.5 AND negative_pct >= 60.0
                    THEN 'INVESTIGATE_SCENARIO_C'
                ELSE 'NORMAL'
            END AS flag
        FROM product_reviews
        """
    )
    return reviews


def register_scenario_b_forensics(connection):
    connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE scenario_b_forensics_ml AS
        WITH review_stats AS (
            SELECT
                r.product_id,
                COUNT(*) AS total_reviews,
                ROUND(AVG(r.rating), 2) AS avg_rating,
                COUNT(*) FILTER (WHERE r.rating >= 4.0) AS star_4_5_count,
                COUNT(*) FILTER (WHERE r.rating <= 2.0) AS star_1_2_count,
                COUNT(*) FILTER (WHERE r.verified_purchase IS TRUE) AS verified_count,
                COUNT(*) FILTER (WHERE r.verified_purchase IS FALSE) AS unverified_count,
                COUNT(*) FILTER (
                    WHERE r.verified_purchase IS FALSE AND r.rating <= 2.0
                ) AS unverified_bad_ratings,
                ROUND(
                    COUNT(*) FILTER (WHERE r.sentiment = 'positive') * 100.0
                    / NULLIF(COUNT(*), 0),
                    1
                ) AS positive_pct,
                ROUND(COALESCE(VAR_SAMP(r.rating), 0), 2) AS rating_variance,
                ROUND(
                    COALESCE(AVG(COALESCE(r.ml_confidence, 1.0)), 1.0),
                    3
                ) AS avg_model_confidence
            FROM silver_reviews_ml AS r
            LEFT JOIN gold_product_discrepancy_flags_ml AS f USING (product_id)
            WHERE f.flag = 'INVESTIGATE_SCENARIO_B'
            GROUP BY r.product_id
        )
        SELECT
            product_id,
            total_reviews,
            avg_rating,
            positive_pct,
            star_4_5_count,
            star_1_2_count,
            verified_count,
            unverified_count,
            unverified_bad_ratings,
            rating_variance,
            avg_model_confidence,
            CASE
                WHEN unverified_bad_ratings > 0 AND star_4_5_count >= 2
                    THEN 'Suspected Review Bombing (Unverified 1-Star)'
                WHEN total_reviews <= 3
                    THEN 'Sample Size Truncation (Under-reviewed)'
                WHEN rating_variance >= 2.0
                    THEN 'Polarized Opinions (1 vs 5 Stars)'
                ELSE 'Genuine Hidden Gem'
            END AS forensic_verdict
        FROM review_stats
        """
    )
