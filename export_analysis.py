import os
import duckdb
import pandas as pd
import json

DUCKDB_PATH = "warehouse.duckdb"
EXPORT_DIR = "analytics_exports"

os.makedirs(EXPORT_DIR, exist_ok=True)

def export_all_analysis():
    print(f"Connecting to {DUCKDB_PATH}...")
    con = duckdb.connect(DUCKDB_PATH, read_only=True)

    # 1. Export Discrepancy Flags (Gold Layer Summary)
    print("Exporting Gold Discrepancy Flags...")
    df_flags = con.execute("""
        SELECT 
            product_id,
            total_reviews,
            avg_star_rating,
            negative_pct,
            positive_pct,
            neg_count,
            pos_count,
            neu_count,
            flag
        FROM gold_product_discrepancy_flags
        ORDER BY total_reviews DESC, negative_pct DESC;
    """).df()
    df_flags.to_csv(os.path.join(EXPORT_DIR, "gold_discrepancy_flags.csv"), index=False)

    # 2. Export Scenario A Flagged Only (High Rating, Bad Reviews)
    print("Exporting Scenario A Focus List...")
    df_scenario_a = df_flags[df_flags["flag"] == "INVESTIGATE_SCENARIO_A"]
    df_scenario_a.to_csv(os.path.join(EXPORT_DIR, "scenario_a_products.csv"), index=False)

    # 3. Export Scenario B Flagged Only (Low Rating, Good Reviews)
    print("Exporting Scenario B Focus List...")
    df_scenario_b = df_flags[df_flags["flag"] == "INVESTIGATE_SCENARIO_B"]
    df_scenario_b.to_csv(os.path.join(EXPORT_DIR, "scenario_b_products.csv"), index=False)

    # 4. Export Overall KPI Summary Metrics as JSON
    print("Exporting High-Level KPI Summary (JSON)...")
    total_reviews = con.execute("SELECT COUNT(*) FROM silver_reviews;").fetchone()[0]
    total_products = con.execute("SELECT COUNT(DISTINCT product_id) FROM silver_reviews;").fetchone()[0]
    avg_rating = float(con.execute("SELECT AVG(rating) FROM silver_reviews;").fetchone()[0])
    
    sentiment_counts = con.execute("""
        SELECT sentiment, COUNT(*) 
        FROM silver_reviews 
        GROUP BY sentiment;
    """).fetchall()
    
    flag_counts = con.execute("""
        SELECT flag, COUNT(*) 
        FROM gold_product_discrepancy_flags 
        GROUP BY flag;
    """).fetchall()

    kpi_summary = {
        "total_reviews": total_reviews,
        "total_products": total_products,
        "portfolio_average_rating": round(avg_rating, 2),
        "sentiment_distribution": {s[0]: s[1] for s in sentiment_counts},
        "discrepancy_counts": {f[0]: f[1] for f in flag_counts}
    }

    with open(os.path.join(EXPORT_DIR, "portfolio_kpi_summary.json"), "w", encoding="utf-8") as f:
        json.dump(kpi_summary, f, indent=4)

    con.close()
    
    print("\nAll analysis files exported successfully!")
    print(f"Check folder: {EXPORT_DIR}/")
    print("  - gold_discrepancy_flags.csv")
    print("  - scenario_a_products.csv")
    print("  - scenario_b_products.csv")
    print("  - portfolio_kpi_summary.json")

if __name__ == "__main__":
    export_all_analysis()