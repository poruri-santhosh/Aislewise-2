CREATE TABLE IF NOT EXISTS shopper_feedback (
    id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL
        CHECK (char_length(btrim(customer_name)) BETWEEN 1 AND 120),
    rating SMALLINT NOT NULL
        CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT NOT NULL
        CHECK (char_length(btrim(review_text)) BETWEEN 1 AND 2000),
    sentiment TEXT NOT NULL
        CHECK (sentiment IN ('positive', 'negative')),
    dwell_time_seconds DOUBLE PRECISION NOT NULL
        CHECK (dwell_time_seconds >= 0),
    cart_items JSONB NOT NULL
        CHECK (jsonb_typeof(cart_items) = 'array'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
