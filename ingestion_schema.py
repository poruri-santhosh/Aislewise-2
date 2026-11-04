import pandera.pandas as pa
from pandera.typing import Series
import pandas as pd
from typing import Optional

# 1. Define Data Contract / Schema
class IngestionSchema(pa.DataFrameModel):
    user_id: Series[str] = pa.Field(nullable=False)
    product_id: Series[str] = pa.Field(nullable=False)
    
    # Use pa.DateTime directly inside Series[...]
    timestamp: Series[pa.DateTime] = pa.Field(nullable=False)
    
    # Rating/Sentiment inputs
    rating: Series[float] = pa.Field(ge=1.0, le=5.0, nullable=True)
    review_text: Series[str] = pa.Field(nullable=True)
    
    # Spatial telemetry metrics
    dwell_time_seconds: Series[float] = pa.Field(ge=0.0, le=7200.0)  # max 2 hours
    aisle_id: Series[str] = pa.Field(nullable=False)
    cart_added: Series[bool] = pa.Field(nullable=False)

    class Config:
        strict = True  # Blocks unexpected extra columns
        coerce = True  # Converts compatible types automatically


# 2. Ingestion Validation Wrapper
def validate_incoming_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    try:
        validated_df = IngestionSchema.validate(df, lazy=True)
        print("Data Quality Check Passed: All schema constraints satisfied.")
        return validated_df
    except pa.errors.SchemaErrors as err:
        print("Data Quality Check Failed! Schema violations detected:")
        print(err.failure_cases[["column", "check", "failure_case", "index"]])
        return None


# 3. Quick Test Execution
if __name__ == "__main__":
    sample_data = pd.DataFrame({
        "user_id": ["U101", "U102", "U103"],
        "product_id": ["P501", "P502", "P503"],
        "timestamp": pd.to_datetime(
            ["2026-11-04 10:00:00", "2026-11-04 10:05:00", "2026-11-04 10:10:00"], 
            utc=True
        ),
        "rating": [4.5, 3.0, 5.0],
        "review_text": ["Great pathing", "Found quickly", "Smooth"],
        "dwell_time_seconds": [45.2, 120.0, 15.5],
        "aisle_id": ["A-12", "B-04", "C-01"],
        "cart_added": [True, False, True]
    })

    validated_df = validate_incoming_data(sample_data)