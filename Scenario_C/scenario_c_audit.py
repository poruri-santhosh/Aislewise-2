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
from Scenario_A.scenario_mlflow import register_ml_reviews

DUCKDB_PATH = PROJECT_ROOT / "warehouse.duckdb"
OUTPUT_DIR = Path(__file__).resolve().parent
os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_scenario_c_audit():
    con = duckdb.connect(DUCKDB_PATH)
    sns.set_theme(style="whitegrid")
    register_ml_reviews(con)

    print("=" * 65)
    print(" SCENARIO C: CONSISTENTLY POOR PRODUCTS (CATALOG PURGE AUDIT) ")
    print(" Criteria: Displayed Rating <= 2.5 AND Negative Share >= 60%")
    print("=" * 65)

    # 1. Fetch Scenario C Products
    query = """
        SELECT 
            f.product_id,
            COALESCE(p.title, 'Appliance Component / Accessory') as product_title,
            f.total_reviews,
            f.avg_star_rating,
            f.negative_pct,
            f.positive_pct,
            f.neg_count,
            f.pos_count,
            COALESCE(f.avg_ml_confidence, 1.0) AS avg_ml_confidence
        FROM gold_product_discrepancy_flags_ml f
        LEFT JOIN bronze_products p ON f.product_id = p.product_id
        WHERE f.avg_star_rating <= 2.5 AND f.negative_pct >= 60.0
        ORDER BY f.total_reviews DESC, f.negative_pct DESC;
    """
    df_lemons = con.execute(query).df()
    print(f"\nTotal Confirmed Lemon Products Flagged: {len(df_lemons):,}")

    # Save to Gold layer
    con.execute("CREATE OR REPLACE TABLE gold_scenario_c_catalog_purge AS SELECT * FROM df_lemons;")

    # 2. Portfolio-level Overview
    avg_stars = df_lemons["avg_star_rating"].mean()
    avg_neg = df_lemons["negative_pct"].mean()
    print(f"\nScenario C Portfolio Overview:")
    print(f"  * Average Star Score    : ⭐ {avg_stars:.2f} / 5.0")
    print(f"  * Average Negative Share: 🔴 {avg_neg:.1f}%")

    print("\nTop 5 Worst Performers:")
    print(df_lemons[["product_id", "total_reviews", "avg_star_rating", "negative_pct", "neg_count"]].head(5).to_string(index=False))

    # 3. Sample Case Evidence (Direct Severe Review Quotes)
    con.register("scenario_c_products", df_lemons[["product_id"]])
    complaints_query = """
        SELECT 
            r.product_id,
            r.rating,
            r.title,
            r.text,
            r.helpful_vote,
            COALESCE(r.ml_confidence, 1.0) AS ml_confidence
        FROM silver_reviews_ml AS r
        INNER JOIN scenario_c_products AS p ON r.product_id = p.product_id
        WHERE r.sentiment = 'negative'
        ORDER BY r.helpful_vote DESC, r.rating ASC
        LIMIT 3;
    """
    df_complaints = con.execute(complaints_query).df()

    print("\n--- Sample Critical Complaints on Lemon Products ---")
    for idx, row in df_complaints.iterrows():
        print(f"\nCase #{idx+1} | Product: {row['product_id']} | Stars: {row['rating']} | Upvotes: {row['helpful_vote']}")
        print(f"  Title   : {row['title']}")
        print(f"  Snippet : \"{str(row['text'])[:110]}...\"")

    # 4. Generate De-listing Purge Report (Text)
    report_file = os.path.join(OUTPUT_DIR, "scenario_c_purge_report.txt")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("================================================================================\n")
        f.write("      AISLEWISE CATALOG PURGE RECOMMENDATION: SCENARIO C (LEMONS)       \n")
        f.write("================================================================================\n")
        f.write(f"Total Confirmed Lemon Products Flagged: {len(df_lemons)}\n")
        f.write("Action Required: Immediate de-ranking, buy-box removal, or vendor termination.\n")
        f.write("================================================================================\n\n")

        for _, row in df_lemons.iterrows():
            f.write(f"PRODUCT ID: {row['product_id']}\n")
            f.write(f"  - Title          : {row['product_title']}\n")
            f.write(f"  - Score          : ⭐ {row['avg_star_rating']:.2f} / 5.0 | Negative Share: 🔴 {row['negative_pct']:.1f}%\n")
            f.write(f"  - Review Volume  : {row['total_reviews']} total ({row['neg_count']} severe complaints)\n")
            f.write(f"  - Action Status  : RECOMMENDED FOR CATALOG REMOVAL\n")
            f.write("-" * 80 + "\n")

    print(f"\nSaved De-listing Report: {report_file}")

    # 5. Visualizations
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))

    # Plot 1: Stars vs Negative %
    sns.scatterplot(
        data=df_lemons, 
        x="avg_star_rating", 
        y="negative_pct", 
        color="#8e44ad", 
        s=85, 
        alpha=0.9, 
        ax=ax1
    )
    ax1.set_title("1. Star Rating vs. Negative Review % (Confirmed Lemons)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Average Star Rating (<= 2.5)")
    ax1.set_ylabel("Negative Reviews Share (%)")

    # Plot 2: Total Reviews Distribution
    sns.countplot(
        data=df_lemons, 
        x="total_reviews", 
        palette="Purples_r", 
        hue="total_reviews",
        legend=False,
        ax=ax2
    )
    ax2.set_title("2. Review Count Distribution of Defective Items", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Total Review Sample Count")
    ax2.set_ylabel("Product Count")

    # English Takeaway Box
    takeaway = (
        "KEY TAKEAWAYS:\n"
        "• Total Alignment: Scenario C items show perfect alignment between low star ratings and severe negative review text.\n"
        "• High Return Rate Risk: These products represent consistent design or material failure rather than statistical noise.\n"
        "• Merchandising Action: Immediate de-listing or suppression from organic search results to protect platform trust."
    )
    plt.figtext(
        0.5, -0.15, takeaway, wrap=True, horizontalalignment='center',
        fontsize=11, bbox=dict(boxstyle='round,pad=0.6', facecolor='#f8f9fa', edgecolor='#bdc3c7')
    )

    chart_file = os.path.join(OUTPUT_DIR, "chart_scenario_c_audit.png")
    plt.tight_layout()
    plt.savefig(chart_file, dpi=300, bbox_inches='tight')
    print(f"Saved Chart: {chart_file}")

    con.close()
    print("=" * 65)
    print("Scenario C Audit Complete!")

if __name__ == "__main__":
    run_scenario_c_audit()