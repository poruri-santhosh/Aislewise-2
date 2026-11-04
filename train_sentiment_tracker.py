import os
import duckdb
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import mlflow
import mlflow.sklearn

DUCKDB_PATH = "warehouse.duckdb"
MLFLOW_TRACKING_URI = "sqlite:///mlflow.db"
MODEL_REGISTRY_NAME = "Aislewise_Sentiment_Model"

def run_training_pipeline():
    print("=" * 65)
    print(" AISLEWISE SENTIMENT MODEL - NATIVE FAST TRAINING & REGISTRATION ")
    print("=" * 65)

    # 1. Load Data from DuckDB
    print("\n[1/5] Loading labeled review dataset from DuckDB...")
    if not os.path.exists(DUCKDB_PATH):
        raise FileNotFoundError(f"Database not found at {DUCKDB_PATH}")

    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    query = """
        SELECT 
            text AS review_text,
            CASE WHEN rating >= 4.0 THEN 1 ELSE 0 END AS label
        FROM silver_reviews
        WHERE text IS NOT NULL AND length(text) >= 10
    """
    df = con.execute(query).df()
    con.close()

    total_samples = len(df)
    pos_samples = (df["label"] == 1).sum()
    neg_samples = (df["label"] == 0).sum()
    print(f"  * Total Samples Loaded : {total_samples:,}")
    print(f"  * Positive Samples (1) : {pos_samples:,} ({pos_samples/total_samples*100:.1f}%)")
    print(f"  * Negative Samples (0) : {neg_samples:,} ({neg_samples/total_samples*100:.1f}%)")

    # 2. Train / Test Split
    print("\n[2/5] Performing Stratified Train/Test Split (80/20)...")
    X_train, X_test, y_train, y_test = train_test_split(
        df["review_text"],
        df["label"],
        test_size=0.20,
        random_state=42,
        stratify=df["label"]
    )
    print(f"  * Train set: {len(X_train):,} samples")
    print(f"  * Test set : {len(X_test):,} samples")

    # 3. Model Pipeline Definition & Fitting
    print("\n[3/5] Fitting TF-IDF Vectorizer + Logistic Regression...")
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            sublinear_tf=True
        )),
        ("clf", LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            solver="liblinear",
            random_state=42
        ))
    ])
    pipeline.fit(X_train, y_train)

    # 4. Evaluation
    print("\n[4/5] Evaluating performance on held-out test data...")
    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)

    print(f"  * Accuracy  : {acc:.4f}")
    print(f"  * Precision : {prec:.4f}")
    print(f"  * Recall    : {rec:.4f}")
    print(f"  * F1-Score  : {f1:.4f}")
    print("  * Confusion Matrix:")
    print(cm)

    # 5. Local Artifact Dump & Fast MLflow Logging
    print("\n[5/5] Saving Native Model Artifacts...")
    os.makedirs("models", exist_ok=True)
    local_pkl_path = os.path.join("models", "sentiment_pipeline.pkl")
    joblib.dump(pipeline, local_pkl_path)
    print(f"  * Saved local artifact to: {local_pkl_path}")

    # Log to MLflow with EXPLICIT dependencies (prevents Windows file scanning hang)
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("Aislewise_Review_Intelligence")

    with mlflow.start_run() as run:
        # Log Metrics & Parameters
        mlflow.log_params({
            "max_features": 5000,
            "ngram_range": "(1, 2)",
            "class_weight": "balanced",
            "solver": "liblinear"
        })
        mlflow.log_metrics({
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
            "f1_score": f1
        })

        # By passing pip_requirements explicitly, MLflow skips inspecting system metadata
        mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="model",
            registered_model_name=MODEL_REGISTRY_NAME,
            pip_requirements=[
                "scikit-learn>=1.6.0",
                "pandas>=2.0.0",
                "numpy>=1.24.0"
            ]
        )
        print(f"  * MLflow Run logged successfully! Run ID: {run.info.run_id}")

    # Final Verification
    print("\n" + "=" * 65)
    print(" VERIFICATION: INFERENCE SMOKE TEST ")
    print("=" * 65)
    test_cases = [
        "Excellent product. I absolutely love it!",
        "The product is okay, nothing special.",
        "Very poor quality. Completely disappointed and broke on first day."
    ]
    for text in test_cases:
        pred_label = pipeline.predict([text])[0]
        label_text = "POSITIVE (1)" if pred_label == 1 else "NEGATIVE (0)"
        print(f"  Input: \"{text}\"")
        print(f"  Result: {label_text}\n")

    print("Retraining & Registration Completed Successfully!")

if __name__ == "__main__":
    run_training_pipeline()