import mlflow
from mlflow.tracking import MlflowClient

# MLflow ట్రాకింగ్ సెటప్
mlflow.set_tracking_uri("sqlite:///mlflow.db")
client = MlflowClient()

model_name = "Aislewise_Sentiment_Model"

# 1. రిజిస్టర్డ్ మోడల్ లేకపోతే క్రియేట్ చేయడం
try:
    client.create_registered_model(model_name)
    print(f"Registered model '{model_name}' created.")
except Exception:
    print(f"Model '{model_name}' already exists in registry.")

# 2. లేటెస్ట్ రన్ నుంచి మోడల్ URI ని రిజిస్టర్ చేయడం
# (మీ దగ్గర ఉన్న రన్ ఆర్టిఫాక్ట్ పాత్ లేదా రన్ ఐడీ)
runs = client.search_runs(experiment_ids=["1"], order_by=["start_time DESC"], max_results=1)

if runs:
    latest_run_id = runs[0].info.run_id
    model_uri = f"runs:/{latest_run_id}/model"
    print(f"Registering model from run: {latest_run_id}")
    
    mv = client.create_model_version(
        name=model_name,
        source=f"{runs[0].info.artifact_uri}/model",
        run_id=latest_run_id
    )
    print(f"Model version {mv.version} registered successfully and marked ready!")
else:
    print("No runs found in experiment '1'. Please check your mlflow.db.")