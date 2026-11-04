"""Quick MLflow verification – checks v2 model metrics are non-zero."""
import mlflow
from mlflow.tracking import MlflowClient
from pathlib import Path

DB = Path("mlflow.db").resolve()
mlflow.set_tracking_uri(f"sqlite:///{DB.as_posix()}")
client = MlflowClient()

m = client.get_registered_model("Aislewise_Sentiment_Model")
print(f"Model: {m.name}, versions: {[v.version for v in m.latest_versions]}")

runs = client.search_runs("1", order_by=["start_time DESC"])
latest = runs[0]
print(f"Latest run: {latest.info.run_id}")
print(f"  accuracy  = {latest.data.metrics.get('accuracy', 'MISSING'):.4f}")
print(f"  f1_score  = {latest.data.metrics.get('f1_score', 'MISSING'):.4f}")
print(f"  precision = {latest.data.metrics.get('precision', 'MISSING'):.4f}")
print(f"  recall    = {latest.data.metrics.get('recall', 'MISSING'):.4f}")
print(f"  train_samples = {int(latest.data.metrics.get('train_samples', 0))}")

model = mlflow.sklearn.load_model("models:/Aislewise_Sentiment_Model/latest")
samples = [
    "This ice maker is excellent, works perfectly after 6 months",
    "Broken on arrival, terrible quality, do not buy",
    "Great product, easy installation, very happy",
]
preds = model.predict(samples)
proba = model.predict_proba(samples)
print("\nSanity inference check (new v2 model):")
for s, p, pr in zip(samples, preds, proba):
    label = "positive" if p == 1 else "negative"
    conf = max(pr)
    print(f"  [{label}, conf={conf:.3f}] {s[:60]}")
