import pandas as pd
from ingestion_schema import validate_incoming_data

# Intentional corrupt/dirty records
dirty_data = pd.DataFrame({
    "user_id": ["U101", None, "U103"],                   # Violation: user_id cannot be null
    "product_id": ["P501", "P502", "P503"],
    "timestamp": pd.to_datetime(
        ["2026-11-04 10:00:00", "2026-11-04 10:05:00", "2026-11-04 10:10:00"], 
        utc=True
    ),
    "rating": [4.5, 7.5, 5.0],                            # Violation: rating cannot be > 5.0
    "review_text": ["Good", "Invalid rating", "Fast"],
    "dwell_time_seconds": [45.2, -10.0, 15.5],            # Violation: dwell time cannot be < 0.0
    "aisle_id": ["A-12", "B-04", "C-01"],
    "cart_added": [True, False, True],
    "hacked_field": ["bad_data_1", "bad_data_2", "bad_data_3"]  # Violation: Unexpected column
})

print("Running dirty data validation test...\n")
result = validate_incoming_data(dirty_data)

if result is None:
    print("\nTest Result: Pipeline protected! Bad records blocked before hitting DB/Model.")