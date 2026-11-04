# sentiment_service.py
import os
import joblib

# Fast & Native Local Pipeline
LOCAL_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "sentiment_pipeline.pkl")

_pipeline = None

def get_pipeline():
    """పైప్‌లైన్‌ను ఒక్కసారే మెమరీలోకి లోడ్ చేసి క్యాష్ చేస్తుంది."""
    global _pipeline
    if _pipeline is None:
        if os.path.exists(LOCAL_MODEL_PATH):
            _pipeline = joblib.load(LOCAL_MODEL_PATH)
        else:
            # Fallback to MLflow registered model version 6
            import mlflow.pyfunc
            mlflow.set_tracking_uri("sqlite:///mlflow.db")
            _pipeline = mlflow.pyfunc.load_model("models:/Aislewise_Sentiment_Model/6")
    return _pipeline

def predict_sentiment(text: str, rating: float = None) -> str:
    """
    రివ్యూ టెక్స్ట్‌ని బట్టి 'positive' లేదా 'negative' ఇస్తుంది.
    టెక్స్ట్ లేకపోతే రేటింగ్ ఆధారంగా ఫాల్‌బ్యాక్ అవుతుంది.
    """
    if not text or not str(text).strip():
        if rating is not None:
            return "positive" if rating >= 4.0 else ("negative" if rating <= 2.0 else "neutral")
        return "neutral"

    try:
        model = get_pipeline()
        pred = model.predict([text])[0]
        return "positive" if int(pred) == 1 else "negative"
    except Exception as err:
        print(f"Prediction fallback due to error: {err}")
        if rating is not None:
            return "positive" if rating >= 4.0 else ("negative" if rating <= 2.0 else "neutral")
        return "neutral"