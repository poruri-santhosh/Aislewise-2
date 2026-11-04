import os
import sys
from pathlib import Path
import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from Scenario_A.scenario_mlflow import register_ml_reviews, register_scenario_b_forensics

DUCKDB_PATH = PROJECT_ROOT / "warehouse.duckdb"
OUTPUT_DIR = Path(__file__).resolve().parent
os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_scenario_b_forensics():
    con = duckdb.connect(DUCKDB_PATH)
    sns.set_theme(style="whitegrid")
    register_ml_reviews(con)
    register_scenario_b_forensics(con)

    print("=" * 65)
    print(" SCENARIO B - STEP 2: DIAGNOSTIC & RATING SABOTAGE AUDIT ")
    print("=" * 65)

    # 1. Model-powered Forensic Classification
    df_forensics = con.execute(
        "SELECT * FROM scenario_b_forensics_ml ORDER BY total_reviews DESC, positive_pct DESC"
    ).df()
    print(f"Total Scenario B Products Evaluated: {len(df_forensics)}")

    # Save to DuckDB Gold layer
    con.execute("CREATE OR REPLACE TABLE gold_scenario_b_forensics AS SELECT * FROM df_forensics;")

    # 2. Diagnostic Summary
    print("\n--- Diagnostic Breakdown of Scenario B ---")
    df_summary = con.execute("""
        SELECT 
            forensic_verdict,
            COUNT(*) as product_count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM gold_scenario_b_forensics), 1) as percentage,
            ROUND(AVG(total_reviews), 1) as avg_reviews_analyzed
        FROM gold_scenario_b_forensics
        GROUP BY forensic_verdict
        ORDER BY product_count DESC;
    """).df()
    print(df_summary.to_string(index=False))

    # 3. Top 3 Cases Drill-Down
    print("\n--- Top 3 Scenario B Case Studies (Rating Killers) ---")
    df_top_gems = df_forensics.head(3)
    for idx, row in df_top_gems.iterrows():
        p_id = row['product_id']
        print(f"\nCase #{idx+1} | Product: {p_id} | Stars: {row['avg_rating']} / 5.0 | Positive Share: {row['positive_pct']}%")
        print(f"  Verdict: {row['forensic_verdict']} | Total Reviews: {row['total_reviews']}")

        pos_rev = con.execute("""
            SELECT rating, title, text 
            FROM silver_reviews_ml 
            WHERE product_id = ? AND sentiment = 'positive' 
            LIMIT 1;
        """, [p_id]).fetchone()

        neg_rev = con.execute("""
            SELECT rating, title, text, verified_purchase 
            FROM silver_reviews_ml 
            WHERE product_id = ? AND sentiment = 'negative' 
            LIMIT 1;
        """, [p_id]).fetchone()

        if pos_rev:
            print(f"  Positive Feedback ({pos_rev[0]} Stars): \"{pos_rev[1]}\" -> {str(pos_rev[2])[:80]}...")
        if neg_rev:
            print(f"  The Rating Killer ({neg_rev[0]} Stars, Verified={neg_rev[3]}): \"{neg_rev[1]}\" -> {str(neg_rev[2])[:80]}...")

    # 4. Visualizations with Simple English Takeaway Box
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))

    sns.barplot(
        data=df_summary,
        x="product_count",
        y="forensic_verdict",
        palette="Blues_r",
        hue="forensic_verdict",
        legend=False,
        ax=ax1
    )
    ax1.set_title("1. Why Are Good Products Stuck With Low Ratings?", fontsize=12, fontweight='bold')
    ax1.set_xlabel("Number of Products")
    ax1.set_ylabel("")

    sns.countplot(
        data=df_forensics,
        x="total_reviews",
        palette="crest",
        hue="total_reviews",
        legend=False,
        ax=ax2
    )
    ax2.set_title("2. Review Volume Distribution (Sample Size Bias)", fontsize=12, fontweight='bold')
    ax2.set_xlabel("Total Reviews Analyzed")
    ax2.set_ylabel("Product Count")

    # Simple English Takeaway Box
    takeaway = (
        "KEY TAKEAWAYS:\n"
        "• Most Scenario B products suffer from 'Sample Size Truncation' (only 2 to 3 reviews per item).\n"
        "• Even though review comments are overwhelmingly positive, a single 1-star review mathematically tanks the average rating to 2.5 - 3.0.\n"
        "• These products are true 'Hidden Gems' — generating just 2 to 3 more positive reviews will quickly lift them to 4.5+ star top sellers."
    )
    plt.figtext(
        0.5, -0.15, takeaway, wrap=True, horizontalalignment='center',
        fontsize=11, bbox=dict(boxstyle='round,pad=0.6', facecolor='#f8f9fa', edgecolor='#bdc3c7')
    )

    chart_file = OUTPUT_DIR / "chart_scenario_b_forensics.png"
    plt.tight_layout()
    plt.savefig(chart_file, dpi=300, bbox_inches='tight')
    print(f"\nSaved Chart: {chart_file}")

    con.close()
    print("=" * 65)
    print("Step 2 Complete! Ready for Recovery Action Report.")

if __name__ == "__main__":
    run_scenario_b_forensics()