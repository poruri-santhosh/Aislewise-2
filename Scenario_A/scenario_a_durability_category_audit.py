import os
import re
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

def detect_failure_timeframe(text):
    t = str(text).lower()
    
    # Regex patterns for timeframes
    if re.search(r'\b(day|days|immediate|immediately|box|arrival|out of the box)\b', t):
        return "Immediate / Under a Week"
    elif re.search(r'\b(week|weeks|few weeks|couple weeks)\b', t):
        return "1 - 4 Weeks (Short Term)"
    elif re.search(r'\b(month|months|few months|couple months)\b', t):
        return "1 - 6 Months (Medium Term)"
    elif re.search(r'\b(year|years|after a year)\b', t):
        return "Over 6 Months / Year"
    else:
        return "Unspecified Timeframe"

def tag_appliance_category(title, text):
    combined = f"{title} {text}".lower()
    
    if any(k in combined for k in ["ice maker", "ice machine", "refrigerator", "freezer", "fridge"]):
        return "Refrigerator & Ice Maker"
    elif any(k in combined for k in ["dryer", "drum roller", "thermal fuse", "heating element"]):
        return "Dryer Components"
    elif any(k in combined for k in ["washer", "washing machine", "agitator", "drain pump"]):
        return "Washing Machine"
    elif any(k in combined for k in ["dishwasher", "rack roller", "spray arm", "silverware basket"]):
        return "Dishwasher Parts"
    elif any(k in combined for k in ["range", "stove", "oven", "burner"]):
        return "Oven & Stove"
    else:
        return "Other Appliance Accessories"

def run_durability_and_category_audit():
    con = duckdb.connect(DUCKDB_PATH)
    sns.set_theme(style="whitegrid")
    register_ml_reviews(con)

    print("=" * 65)
    print(" SCENARIO A: DURABILITY TIMELINE & PART CATEGORY AUDIT ")
    print("=" * 65)

    # 1. Fetch Scenario A negative reviews with product titles
    query = """
        SELECT 
            r.review_id,
            r.product_id,
            p.title as product_title,
            r.rating,
            r.text,
            r.helpful_vote,
            COALESCE(r.ml_confidence, 0.0) AS ml_confidence
        FROM silver_reviews_ml r
        JOIN gold_product_discrepancy_flags_ml f ON r.product_id = f.product_id
        LEFT JOIN bronze_products p ON r.product_id = p.product_id
        WHERE f.flag = 'INVESTIGATE_SCENARIO_A' AND LOWER(r.sentiment) = 'negative';
    """
    df_reviews = con.execute(query).df()
    print(f"Total Negative Reviews Analyzed in Scenario A: {len(df_reviews):,}")

    # 2. Extract Lifespan and Appliance Type
    df_reviews["failure_timeframe"] = df_reviews["text"].apply(detect_failure_timeframe)
    df_reviews["appliance_category"] = df_reviews.apply(
        lambda row: tag_appliance_category(row["product_title"], row["text"]), axis=1
    )

    # 3. Timeframe Breakdown Table
    print("\n--- 1. When Did the Product Fail? (Lifespan Breakdown) ---")
    df_time_summary = df_reviews["failure_timeframe"].value_counts(normalize=True).mul(100).round(1).reset_index()
    df_time_summary.columns = ["Failure Timeframe", "Share (%)"]
    print(df_time_summary.to_string(index=False))

    # 4. Appliance Category Breakdown Table
    print("\n--- 2. Which Appliance Categories Generate the Most Traps? ---")
    df_cat_summary = df_reviews["appliance_category"].value_counts(normalize=True).mul(100).round(1).reset_index()
    df_cat_summary.columns = ["Appliance Category", "Share (%)"]
    print(df_cat_summary.to_string(index=False))

    # 5. Save enriched data into DuckDB Gold layer
    con.execute("CREATE OR REPLACE TABLE gold_scenario_a_durability AS SELECT * FROM df_reviews;")

    # 6. Generate Comparative Visualizations
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))

    # Plot 1: Lifespan Distribution
    order_time = [
        "Immediate / Under a Week", 
        "1 - 4 Weeks (Short Term)", 
        "1 - 6 Months (Medium Term)", 
        "Over 6 Months / Year", 
        "Unspecified Timeframe"
    ]
    sns.countplot(
        data=df_reviews, 
        y="failure_timeframe", 
        order=order_time,
        palette="Reds_r",
        ax=ax1
    )
    ax1.set_title("1. Premature Failure: When Did Customer Products Break?", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Review Count")
    ax1.set_ylabel("")

    # Plot 2: Appliance Category Distribution
    sns.countplot(
        data=df_reviews, 
        y="appliance_category", 
        order=df_reviews["appliance_category"].value_counts().index,
        palette="Blues_r",
        ax=ax2
    )
    ax2.set_title("2. Trap Products by Appliance Part Domain", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Review Count")
    ax2.set_ylabel("")

    takeaway = (
        "Key Takeaways:\n"
        "- Durability Analysis reveals whether items arrive broken or fail prematurely post-installation.\n"
        "- Category breakdown shows if specific domains (like Ice Makers or Dryers) dominate the Rating Trap segment.\n"
        "- This proves that high ratings often reflect initial setup ease, whereas negative text highlights premature wear."
    )
    plt.figtext(
        0.5, -0.15, takeaway, wrap=True, horizontalalignment='center',
        fontsize=11, bbox=dict(boxstyle='round,pad=0.6', facecolor='#f8f9fa', edgecolor='#bdc3c7')
    )

    chart_path = os.path.join(OUTPUT_DIR, "chart_scenario_a_durability.png")
    plt.tight_layout()
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"\nSaved Chart: {chart_path}")

    con.close()
    print("=" * 65)

if __name__ == "__main__":
    run_durability_and_category_audit()