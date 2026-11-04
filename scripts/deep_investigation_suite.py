import duckdb
import pandas as pd
import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if PROJECT_ROOT.name == "scripts":
    PROJECT_ROOT = PROJECT_ROOT.parent
DUCKDB_PATH = PROJECT_ROOT / "warehouse.duckdb"

def classify_root_cause(text, title=""):
    full_text = f"{title} {text}".lower()

    delivery_words = ["delivery", "shipping", "shipped", "arrived late", "delayed", "courier", "transit", "lost", "tracking"]
    packaging_words = ["packaging", "package", "box crushed", "box damaged", "torn", "seal broken", "poorly packed"]
    fit_words = ["fit", "fitting", "dimension", "size", "too small", "too big", "lid", "loose", "tight"]
    quality_words = ["broken", "defect", "defective", "stopped working", "cheap", "malfunction", "cracked", "died", "failed", "leaking", "noisy", "burn", "melted"]

    if any(w in full_text for w in delivery_words):
        return "Delivery & Shipping"
    elif any(w in full_text for w in packaging_words):
        return "Packaging Issues"
    elif any(w in full_text for w in fit_words):
        return "Size & Compatibility"
    elif any(w in full_text for w in quality_words):
        return "Core Quality & Defect"
    else:
        return "General Dissatisfaction"

def run_deep_suite():
    con = duckdb.connect(DUCKDB_PATH)
    print("=" * 65)
    print("       AISLEWISE DEEP ROOT-CAUSE & FORENSIC AUDIT SUITE       ")
    print("=" * 65)

    # -------------------------------------------------------------
    # 1. ROOT-CAUSE AUDIT (Scenario A Negative Reviews)
    # -------------------------------------------------------------
    print("\n[1] Running Root-Cause Classifier on Scenario A Products...")
    df_scenario_a_reviews = con.execute("""
        SELECT 
            r.review_id,
            r.product_id,
            r.rating,
            r.title,
            r.text,
            r.verified_purchase,
            r.timestamp
        FROM silver_reviews r
        JOIN gold_product_discrepancy_flags f ON r.product_id = f.product_id
        WHERE f.flag = 'INVESTIGATE_SCENARIO_A' AND r.sentiment = 'negative';
    """).df()

    df_scenario_a_reviews["root_cause"] = df_scenario_a_reviews.apply(
        lambda row: classify_root_cause(row["text"], row["title"]), axis=1
    )

    con.execute("CREATE OR REPLACE TABLE gold_scenario_a_root_causes AS SELECT * FROM df_scenario_a_reviews;")

    # Root Cause Summary
    print("\n--- Root-Cause Breakdown (% of complaints) ---")
    df_rc_summary = con.execute("""
        SELECT 
            root_cause, 
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM gold_scenario_a_root_causes), 2) as percentage
        FROM gold_scenario_a_root_causes
        GROUP BY root_cause
        ORDER BY count DESC;
    """).df()
    print(df_rc_summary.to_string(index=False))

    # -------------------------------------------------------------
    # 2. VERIFIED VS UNVERIFIED AUDIT (Review Manipulation Detection)
    # -------------------------------------------------------------
    print("\n" + "=" * 65)
    print("[2] Running Review Authenticity Audit (Verified vs Unverified)...")
    df_auth_audit = con.execute("""
        SELECT 
            f.flag,
            r.verified_purchase,
            COUNT(*) as review_count,
            ROUND(AVG(r.rating), 2) as avg_rating,
            ROUND(COUNT(CASE WHEN r.sentiment = 'positive' THEN 1 END) * 100.0 / COUNT(*), 1) as positive_pct,
            ROUND(COUNT(CASE WHEN r.sentiment = 'negative' THEN 1 END) * 100.0 / COUNT(*), 1) as negative_pct
        FROM silver_reviews r
        JOIN gold_product_discrepancy_flags f ON r.product_id = f.product_id
        WHERE f.flag IN ('INVESTIGATE_SCENARIO_A', 'INVESTIGATE_SCENARIO_B')
        GROUP BY f.flag, r.verified_purchase
        ORDER BY f.flag, r.verified_purchase DESC;
    """).df()
    print(df_auth_audit.to_string(index=False))

    # -------------------------------------------------------------
    # 3. TOP DEFECTIVE PRODUCTS AUDIT (Specific Failure Profiles)
    # -------------------------------------------------------------
    print("\n" + "=" * 65)
    print("[3] Top Products by Dominant Failure Root-Cause...")
    con.execute("""
        CREATE OR REPLACE TABLE gold_product_primary_failure AS
        WITH ranked_causes AS (
            SELECT 
                product_id,
                root_cause,
                COUNT(*) as cause_count,
                ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY COUNT(*) DESC) as rn
            FROM gold_scenario_a_root_causes
            GROUP BY product_id, root_cause
        )
        SELECT 
            f.product_id,
            f.avg_star_rating,
            f.negative_pct,
            r.root_cause as primary_complaint_driver,
            r.cause_count as primary_complaint_count
        FROM gold_product_discrepancy_flags f
        JOIN ranked_causes r ON f.product_id = r.product_id
        WHERE r.rn = 1 AND f.total_reviews >= 5
        ORDER BY f.negative_pct DESC
        LIMIT 10;
    """)

    df_primary_failures = con.execute("SELECT * FROM gold_product_primary_failure;").df()
    print(df_primary_failures.to_string(index=False))

    con.close()
    print("\n" + "=" * 65)
    print("Deep Forensic Investigation Completed Successfully!")

if __name__ == "__main__":
    run_deep_suite()