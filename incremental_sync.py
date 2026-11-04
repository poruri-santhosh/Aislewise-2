import os
import time
import duckdb
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Neon PostgreSQL Connection URL (.env నుంచి లేదా డైరెక్ట్ గా)
PG_URL = os.getenv("NEON_DATABASE_URL")
DUCKDB_PATH = "warehouse.duckdb"
BATCH_SIZE = 5000  # ఒక్కో సైకిల్‌లో ప్రాసెస్ చేసే రికార్డుల సంఖ్య

def init_duckdb():
    """DuckDB లో కావాల్సిన టేబుల్స్ మరియు మెటాడేటాను ఇనిషియలైజ్ చేస్తుంది."""
    con = duckdb.connect(DUCKDB_PATH)
    
    # 1. Sync Checkpoint Table
    con.execute("""
        CREATE TABLE IF NOT EXISTS sync_metadata (
            key VARCHAR PRIMARY KEY,
            last_synced_timestamp BIGINT
        );
    """)
    con.execute("""
        INSERT OR IGNORE INTO sync_metadata VALUES ('reviews_high_watermark', 0);
    """)

    # 2. Silver Reviews Table
    con.execute("""
        CREATE TABLE IF NOT EXISTS silver_reviews (
            review_id VARCHAR PRIMARY KEY,
            product_id VARCHAR,
            user_id VARCHAR,
            rating DOUBLE,
            title VARCHAR,
            text VARCHAR,
            timestamp BIGINT,
            verified_purchase BOOLEAN,
            helpful_vote BIGINT,
            sentiment VARCHAR
        );
    """)

    # Fast indexing for queries
    con.execute("CREATE INDEX IF NOT EXISTS idx_silver_product ON silver_reviews(product_id);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_silver_sentiment ON silver_reviews(sentiment);")
    con.close()

def fast_sentiment_rule(rating, text):
    """
    Tier-1 Fast Filter: Rating & Keyword-based lightweight NLP
    """
    text_lower = str(text).lower() if text else ""
    negative_words = {"bad", "worst", "broken", "terrible", "waste", "poor", "damaged", "defective", "return", "useless", "cheap"}
    positive_words = {"good", "great", "excellent", "best", "love", "awesome", "perfect", "super", "works", "happy"}
    
    neg_score = sum(1 for w in negative_words if w in text_lower)
    pos_score = sum(1 for w in positive_words if w in text_lower)

    if rating <= 2.0 or neg_score > pos_score:
        return 'negative'
    elif rating >= 4.0 or pos_score > neg_score:
        return 'positive'
    else:
        return 'neutral'

def run_sync_cycle():
    """PostgreSQL నుండి కొత్త రికార్డులను మాత్రమే తెచ్చి DuckDB లో అప్‌డేట్ చేస్తుంది."""
    # 1. Get current checkpoint
    con_duck = duckdb.connect(DUCKDB_PATH)
    res = con_duck.execute("SELECT last_synced_timestamp FROM sync_metadata WHERE key = 'reviews_high_watermark'").fetchone()
    last_timestamp = res[0] if res else 0
    con_duck.close()

    # 2. Fetch only NEW records from PostgreSQL
    conn_pg = psycopg2.connect(PG_URL)
    cur_pg = conn_pg.cursor()
    cur_pg.execute("""
        SELECT review_id, product_id, user_id, rating, title, text, timestamp, verified_purchase, helpful_vote
        FROM reviews
        WHERE timestamp > %s
        ORDER BY timestamp ASC
        LIMIT %s;
    """, (last_timestamp, BATCH_SIZE))
    new_rows = cur_pg.fetchall()
    cur_pg.close()
    conn_pg.close()

    if not new_rows:
        return 0

    # 3. Transform & Tag Sentiment
    con_duck = duckdb.connect(DUCKDB_PATH)
    max_ts = last_timestamp

    records_to_insert = []
    for r in new_rows:
        rev_id, prod_id, u_id, rating, title, text, ts, verified, helpful = r
        sentiment = fast_sentiment_rule(float(rating) if rating is not None else 3.0, text)
        records_to_insert.append((
            str(rev_id),
            str(prod_id),
            str(u_id),
            float(rating) if rating is not None else 0.0,
            str(title) if title else "",
            str(text) if text else "",
            int(ts) if ts is not None else 0,
            bool(verified),
            int(helpful) if helpful is not None else 0,
            sentiment
        ))
        if ts and ts > max_ts:
            max_ts = ts

    # 4. Insert into Silver Table
    con_duck.executemany("""
        INSERT OR IGNORE INTO silver_reviews 
        (review_id, product_id, user_id, rating, title, text, timestamp, verified_purchase, helpful_vote, sentiment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, records_to_insert)

    # 5. Refresh Gold Aggregations & Discrepancy Flags
    _build_gold_flags(con_duck)

    # 6. Save updated checkpoint
    con_duck.execute("""
        UPDATE sync_metadata 
        SET last_synced_timestamp = ? 
        WHERE key = 'reviews_high_watermark';
    """, (max_ts,))
    
    con_duck.close()
    return len(records_to_insert)

def _build_gold_flags(con_duck):
    """
    Rebuild gold_product_discrepancy_flags from scratch using silver_reviews.

    Flag logic (matches scenario_mlflow.py runtime thresholds):
      INVESTIGATE_SCENARIO_A : avg_star_rating >= 4.0 AND negative_pct >= 35.0
      INVESTIGATE_SCENARIO_B : avg_star_rating <= 3.0 AND positive_pct >= 65.0
      INVESTIGATE_SCENARIO_C : avg_star_rating <= 2.5 AND negative_pct >= 60.0
      NORMAL                 : everything else

    avg_ml_confidence is stored as NULL because the incremental-sync worker uses
    keyword-based sentiment (fast_sentiment_rule), not the MLflow model.  The
    Streamlit dashboard and scenario scripts override this column at runtime via
    COALESCE(avg_ml_confidence, 1.0) on the ML-scored temp table.
    """
    con_duck.execute("""
        CREATE OR REPLACE TABLE gold_product_discrepancy_flags AS
        WITH stats AS (
            SELECT
                product_id,
                COUNT(*)                                                    AS total_reviews,
                AVG(rating)                                                 AS avg_star_rating,
                COUNT(CASE WHEN sentiment = 'negative' THEN 1 END)          AS neg_count,
                COUNT(CASE WHEN sentiment = 'positive' THEN 1 END)          AS pos_count,
                COUNT(CASE WHEN sentiment = 'neutral'  THEN 1 END)          AS neu_count,
                ROUND(COUNT(CASE WHEN sentiment = 'negative' THEN 1 END) * 100.0 / COUNT(*), 2) AS negative_pct,
                ROUND(COUNT(CASE WHEN sentiment = 'positive' THEN 1 END) * 100.0 / COUNT(*), 2) AS positive_pct
            FROM silver_reviews
            GROUP BY product_id
        )
        SELECT
            product_id,
            total_reviews,
            ROUND(avg_star_rating, 2)        AS avg_star_rating,
            neg_count,
            pos_count,
            neu_count,
            negative_pct,
            positive_pct,
            -- avg_ml_confidence is NULL here; filled at runtime by ML scoring
            CAST(NULL AS DOUBLE)             AS avg_ml_confidence,
            CASE
                WHEN avg_star_rating >= 4.0 AND negative_pct >= 35.0
                    THEN 'INVESTIGATE_SCENARIO_A'
                WHEN avg_star_rating <= 3.0 AND positive_pct >= 65.0
                    THEN 'INVESTIGATE_SCENARIO_B'
                WHEN avg_star_rating <= 2.5 AND negative_pct >= 60.0
                    THEN 'INVESTIGATE_SCENARIO_C'
                ELSE 'NORMAL'
            END AS flag
        FROM stats
    """)


if __name__ == "__main__":
    init_duckdb()
    print("DuckDB Tables initialized.")
    print("Incremental Sync Worker started! Polling Postgres every 10s...")

    while True:
        try:
            count = run_sync_cycle()
            if count > 0:
                print(f"[Sync] Ingested & Processed {count} reviews into DuckDB!")
            else:
                # కొత్త రికార్డులు లేకపోతే 10 సెకన్లు నిరీక్షిస్తుంది
                time.sleep(10)
        except Exception as e:
            print(f"[Sync Error] {e}")
            time.sleep(10)