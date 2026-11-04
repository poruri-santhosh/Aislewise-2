import math
from numbers import Real

import pandas as pd
import pandera.pandas as pa


SHOPPER_REVIEW_SCHEMA = pa.DataFrameSchema(
    {
        "customer_name": pa.Column(
            str,
            checks=pa.Check.str_length(min_value=1, max_value=120),
            nullable=False,
        ),
        "rating": pa.Column(int, checks=pa.Check.isin([1, 2, 3, 4, 5]), nullable=False),
        "review_text": pa.Column(
            str,
            checks=pa.Check.str_length(min_value=1, max_value=2000),
            nullable=False,
        ),
        "dwell_time_seconds": pa.Column(
            float,
            checks=[
                pa.Check.ge(0),
                pa.Check(lambda values: values.map(math.isfinite)),
            ],
            nullable=False,
            coerce=True,
        ),
    },
    strict=True,
)


def validate_shopper_review_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Submit feedback as a JSON object.")

    customer_name = payload.get("customer_name")
    review_text = payload.get("review_text")
    rating = payload.get("rating")
    dwell_time = payload.get("dwell_time_seconds")
    cart_items = payload.get("cart_items")

    if not isinstance(customer_name, str) or not isinstance(review_text, str):
        raise ValueError("Customer name and review text are required.")
    if isinstance(rating, bool) or not isinstance(rating, int):
        raise ValueError("Rating must be a whole number from 1 to 5.")
    if isinstance(dwell_time, bool) or not isinstance(dwell_time, Real):
        raise ValueError("Dwell time must be a non-negative number of seconds.")
    try:
        dwell_time_value = float(dwell_time)
    except OverflowError as error:
        raise ValueError("Dwell time must be a finite number of seconds.") from error
    if not math.isfinite(dwell_time_value):
        raise ValueError("Dwell time must be a finite number of seconds.")
    if not isinstance(cart_items, list) or not cart_items:
        raise ValueError("Add at least one grocery item before submitting feedback.")
    if any(not isinstance(item, str) for item in cart_items):
        raise ValueError("Cart contains an unknown grocery item.")
    if len(cart_items) > 4 or len(set(cart_items)) != len(cart_items):
        raise ValueError("Cart items must be a unique list of grocery item IDs.")
    if any(item not in {"milk", "bread", "coffee", "oats"} for item in cart_items):
        raise ValueError("Cart contains an unknown grocery item.")

    row = {
        "customer_name": customer_name.strip(),
        "rating": rating,
        "review_text": review_text.strip(),
        "dwell_time_seconds": dwell_time_value,
    }

    try:
        validated = SHOPPER_REVIEW_SCHEMA.validate(pd.DataFrame([row]), lazy=True)
    except pa.errors.SchemaErrors as error:
        raise ValueError(
            "Customer name, rating, review text, or dwell time is invalid."
        ) from error

    clean_row = validated.iloc[0]
    return {
        "customer_name": clean_row["customer_name"],
        "rating": int(clean_row["rating"]),
        "review_text": clean_row["review_text"],
        "dwell_time_seconds": float(clean_row["dwell_time_seconds"]),
        "cart_items": cart_items,
    }
