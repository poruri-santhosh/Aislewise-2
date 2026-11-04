import os
import joblib
import pandas as pd
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

MODEL_NAME = "Aislewise_Sentiment_Model"

# Root directory path calculation
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCAL_PKL = os.path.join(BASE_DIR, "models", "sentiment_pipeline.pkl")


def load_sentiment_model():
    """
    Load native Python 3.14 model pipeline without version mismatch.
    Falls back to MLflow Version 6 if local pickle is not found.
    """
    if os.path.exists(LOCAL_PKL):
        return joblib.load(LOCAL_PKL)

    import mlflow.pyfunc

    mlflow.set_tracking_uri(f"sqlite:///{os.path.join(BASE_DIR, 'mlflow.db')}")
    return mlflow.pyfunc.load_model("models:/Aislewise_Sentiment_Model/6")


def infer_review_sentiment(model, reviews_df):
    """
    reviews_df meeda inference run chesi sentiment mariyu confidence columns add chesthundi.
    Ensures both 'model_confidence' and 'ml_confidence' exist for DuckDB queries.
    """
    df = reviews_df.copy()
    if df.empty or "text" not in df.columns:
        df["sentiment"] = "neutral"
        df["model_confidence"] = 1.0
        df["ml_confidence"] = 1.0
        return df

    texts = df["text"].fillna("").astype(str).tolist()

    try:
        # Pipeline prediction
        preds = model.predict(texts)
        df["sentiment"] = ["positive" if int(p) == 1 else "negative" for p in preds]

        # Confidence scores
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(texts)
            conf_scores = [float(max(prob)) for prob in probs]
            df["model_confidence"] = conf_scores
            df["ml_confidence"] = conf_scores
        else:
            df["model_confidence"] = 0.95
            df["ml_confidence"] = 0.95
    except Exception as e:
        print(f"Inference error in scenario_mlflow: {e}")
        # Rating-based fallback
        if "rating" in df.columns:
            df["sentiment"] = df["rating"].apply(
                lambda r: "positive" if r >= 4.0 else ("negative" if r <= 2.0 else "neutral")
            )
        else:
            df["sentiment"] = "neutral"
        df["model_confidence"] = 0.85
        df["ml_confidence"] = 0.85

    return df


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