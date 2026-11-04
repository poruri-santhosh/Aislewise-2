"""
Aislewise Sentiment Tracker – Production Training Pipeline
==========================================================
Loads labeled review data directly from warehouse.duckdb (silver_reviews).

Labeling strategy:
  rating >= 4.0  →  positive  (label 1)
  rating <= 2.0  →  negative  (label 0)
  rating == 3.0  →  excluded  (noisy neutral class)

Split: stratified 80 / 20 (train / test)
Model: TF-IDF (unigrams+bigrams) + Logistic Regression
Artifacts: confusion matrix PNG, trained sklearn pipeline
Registry: Aislewise_Sentiment_Model (latest version updated)
"""
import os
import tempfile
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")          # non-interactive backend – safe in all environments
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


# ── 1. Configuration ────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
WAREHOUSE_PATH = PROJECT_ROOT / "warehouse.duckdb"
MODEL_NAME = "Aislewise_Sentiment_Model"

PARAMS = {
    "max_features": 5000,
    "ngram_range": (1, 2),
    "C": 1.0,
    "solver": "liblinear",
    "max_iter": 1000,
    "class_weight": "balanced",
    "test_size": 0.20,
    "random_state": 42,
    "min_text_length": 10,   # characters – filters blank / trivially short texts
}

print("=" * 65)
print(" AISLEWISE SENTIMENT MODEL – PRODUCTION RETRAINING ")
print("=" * 65)


# ── 2. Load labeled data from warehouse.duckdb ───────────────────────────────

print(f"\n[1/6] Loading silver_reviews from {WAREHOUSE_PATH.name} …")
if not WAREHOUSE_PATH.is_file():
    raise FileNotFoundError(
        f"warehouse.duckdb not found at {WAREHOUSE_PATH}. "
        "Run incremental_sync.py first to populate the warehouse."
    )

con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
df_raw = con.execute(
    """
    SELECT
        COALESCE(text, '') AS review_text,
        rating
    FROM silver_reviews
    WHERE rating IS NOT NULL
      AND (rating >= 4.0 OR rating <= 2.0)
    """
).df()
con.close()

# Assign binary labels
df_raw["label"] = (df_raw["rating"] >= 4.0).astype(int)  # 1 = positive, 0 = negative

# Remove trivially short texts (noise)
df_raw = df_raw[df_raw["review_text"].str.strip().str.len() >= PARAMS["min_text_length"]]

total = len(df_raw)
pos = int(df_raw["label"].sum())
neg = total - pos
print(f"    Labeled rows loaded : {total:,}")
print(f"    Positive (label=1)  : {pos:,}  ({pos/total:.1%})")
print(f"    Negative (label=0)  : {neg:,}  ({neg/total:.1%})")

if total < 20:
    raise ValueError(
        f"Too few labeled reviews ({total}) to train a meaningful model. "
        "Populate silver_reviews with at least 20 rated reviews."
    )


# ── 3. Stratified 80/20 train/test split ────────────────────────────────────

print("\n[2/6] Splitting data (stratified 80/20) …")
X_train, X_test, y_train, y_test = train_test_split(
    df_raw["review_text"],
    df_raw["label"],
    test_size=PARAMS["test_size"],
    random_state=PARAMS["random_state"],
    stratify=df_raw["label"],
)
print(f"    Train : {len(X_train):,} samples")
print(f"    Test  : {len(X_test):,} samples")


# ── 4. Build and train pipeline ─────────────────────────────────────────────

print("\n[3/6] Training TF-IDF + Logistic Regression pipeline …")
pipeline = Pipeline(
    [
        (
            "tfidf",
            TfidfVectorizer(
                max_features=PARAMS["max_features"],
                ngram_range=PARAMS["ngram_range"],
                sublinear_tf=True,
                strip_accents="unicode",
                analyzer="word",
                token_pattern=r"\b[a-zA-Z]{2,}\b",
            ),
        ),
        (
            "classifier",
            LogisticRegression(
                C=PARAMS["C"],
                solver=PARAMS["solver"],
                max_iter=PARAMS["max_iter"],
                class_weight=PARAMS["class_weight"],
                random_state=PARAMS["random_state"],
            ),
        ),
    ]
)
pipeline.fit(X_train, y_train)


# ── 5. Evaluate ─────────────────────────────────────────────────────────────

print("\n[4/6] Evaluating on held-out test set …")
y_pred = pipeline.predict(X_test)

acc  = accuracy_score(y_test, y_pred)
f1   = f1_score(y_test, y_pred, average="weighted", zero_division=0)
prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
rec  = recall_score(y_test, y_pred, average="weighted", zero_division=0)
cm   = confusion_matrix(y_test, y_pred)

print(f"    Accuracy  : {acc:.4f}")
print(f"    Precision : {prec:.4f}")
print(f"    Recall    : {rec:.4f}")
print(f"    F1-Score  : {f1:.4f}")
print(f"    Confusion Matrix:\n{cm}")


# ── 6. Log to MLflow & register model ───────────────────────────────────────

print("\n[5/6] Logging run and registering model in MLflow …")

# Use local mlflow.db if no tracking URI set
local_registry = PROJECT_ROOT / "mlflow.db"
tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "").strip()
if not tracking_uri and local_registry.is_file():
    tracking_uri = f"sqlite:///{local_registry.as_posix()}"
if tracking_uri:
    mlflow.set_tracking_uri(tracking_uri)

mlflow.set_experiment("Aislewise_Sentiment_Analysis")

# Log hyperparams with serialisable values
loggable_params = dict(PARAMS)
loggable_params["ngram_range"] = str(PARAMS["ngram_range"])

with mlflow.start_run(run_name="LogisticRegression_TFIDF_RealData"):
    mlflow.log_params(loggable_params)

    mlflow.log_metric("accuracy",  acc)
    mlflow.log_metric("f1_score",  f1)
    mlflow.log_metric("precision", prec)
    mlflow.log_metric("recall",    rec)
    mlflow.log_metric("train_samples", len(X_train))
    mlflow.log_metric("test_samples",  len(X_test))
    mlflow.log_metric("positive_ratio", pos / total)

    # Confusion matrix artifact
    with tempfile.TemporaryDirectory() as tmp_dir:
        fig, ax = plt.subplots(figsize=(5, 4))
        disp = ConfusionMatrixDisplay(
            confusion_matrix=cm,
            display_labels=["Negative (0)", "Positive (1)"],
        )
        disp.plot(ax=ax, colorbar=False, cmap="Blues")
        ax.set_title("Confusion Matrix – Aislewise_Sentiment_Model", fontsize=11)
        plt.tight_layout()
        cm_path = os.path.join(tmp_dir, "confusion_matrix.png")
        plt.savefig(cm_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        mlflow.log_artifact(cm_path, artifact_path="evaluation")

    # Infer signature from real data
    signature = infer_signature(X_train, pipeline.predict(X_train))

    mlflow.sklearn.log_model(
        sk_model=pipeline,
        artifact_path="sentiment_pipeline_model",
        registered_model_name=MODEL_NAME,
        signature=signature,
        input_example=X_train.iloc[:3].tolist(),
    )

print(f"\n[6/6] Done.")
print(f"    Model registered as : {MODEL_NAME}")
print(f"    Accuracy  : {acc:.4f}")
print(f"    F1-Score  : {f1:.4f}")
print("=" * 65)
print("Run `mlflow ui --backend-store-uri sqlite:///mlflow.db` to inspect.")