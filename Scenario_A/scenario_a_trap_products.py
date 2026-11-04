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

def run_scenario_a():
    con = duckdb.connect(DUCKDB_PATH)
    sns.set_theme(style="whitegrid")
    register_ml_reviews(con)

    print("==================================================")
    print(" SCENARIO A: DANGEROUS TRAP PRODUCTS (AUDIT) ")
    print("==================================================")

    # 1. Scenario A Analysis Query
    query = """
        SELECT 
            product_id,
            total_reviews,
            avg_star_rating,
            negative_pct,
            positive_pct,
            neg_count,
            pos_count
        FROM gold_product_discrepancy_flags_ml
        WHERE avg_star_rating >= 4.0 AND negative_pct >= 35.0
        ORDER BY total_reviews DESC, negative_pct DESC;
    """
    df_a = con.execute(query).df()
    print(f"Total Scenario A Products Found: {len(df_a)}")
    print("\nTop 5 Scenario A Items:")
    print(df_a.head(5).to_string(index=False))

    # 2. Visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))

    # Scatter of Star vs Neg %
    sns.scatterplot(
        data=df_a, 
        x="avg_star_rating", 
        y="negative_pct", 
        color="#e74c3c", 
        s=70, 
        alpha=0.8, 
        ax=ax1
    )
    ax1.set_title("Scenario A: Displayed Stars vs. Actual Negative %", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Average Star Rating (4.0 - 5.0)")
    ax1.set_ylabel("Negative Reviews Share (%)")

    # Negative % Distribution
    sns.histplot(df_a["negative_pct"], bins=15, kde=True, color="#c0392b", ax=ax2)
    ax2.set_title("Distribution of Negative Review % in Trap Products", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Negative Review %")
    ax2.set_ylabel("Product Count")

    # Meaning Box
    takeaway = (
        "ARTHAM (Takeaway):\n"
        "• Ee products chudaniki 4 to 5 stars untayi, kaani konna tarvata customers 35% nunchi 80% varaku negative ga raasaru.\n"
        "• Ivvi customers ni mosam chese 'Rating Traps'. Ee category paina deep product quality check cheyyali."
    )
    plt.figtext(0.5, -0.12, takeaway, wrap=True, horizontalalignment='center',
                fontsize=11, bbox=dict(boxstyle='round,pad=0.6', facecolor='#f8f9fa', edgecolor='#bdc3c7'))

    plt.tight_layout()
    chart_path = OUTPUT_DIR / "chart_scenario_a.png"
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"\nVisualization saved to: {chart_path}")
    con.close()

if __name__ == "__main__":
    run_scenario_a()