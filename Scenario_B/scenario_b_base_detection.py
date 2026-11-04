import os
import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

DUCKDB_PATH = "warehouse.duckdb"
OUTPUT_DIR = "Scenario_B"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_scenario_b_base():
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    sns.set_theme(style="whitegrid")

    print("=" * 65)
    print(" SCENARIO B - STEP 1: BASELINE DETECTION & SEGMENT FILTER ")
    print(" Criteria: Displayed Rating <= 3.0 AND Positive Sentiment >= 65%")
    print("=" * 65)

    # 1. Fetch baseline Scenario B items from Gold layer
    query = """
        SELECT 
            product_id,
            total_reviews,
            avg_star_rating,
            positive_pct,
            negative_pct,
            pos_count,
            neg_count
        FROM gold_product_discrepancy_flags
        WHERE flag = 'INVESTIGATE_SCENARIO_B'
        ORDER BY total_reviews DESC, positive_pct DESC;
    """
    df_b = con.execute(query).df()
    print(f"\nTotal Scenario B Products Detected: {len(df_b):,}")

    if df_b.empty:
        print("No products matched Scenario B criteria.")
        con.close()
        return

    # 2. Portfolio-level Stats for Scenario B
    avg_rating = df_b["avg_star_rating"].mean()
    avg_pos = df_b["positive_pct"].mean()
    avg_reviews = df_b["total_reviews"].mean()

    print("\nScenario B Segment Overview:")
    print(f"  * Average Displayed Rating : ⭐ {avg_rating:.2f} / 5.0")
    print(f"  * Average Positive Share   : 🟢 {avg_pos:.1f}%")
    print(f"  * Average Review Volume    : 📦 {avg_reviews:.1f} reviews per product")

    print("\nTop 5 Detected Products:")
    print(df_b.head(5).to_string(index=False))

    # 3. Visualizations with Simple Meaning Box
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))

    # Plot 1: Stars vs Positive Share
    sns.scatterplot(
        data=df_b, 
        x="avg_star_rating", 
        y="positive_pct", 
        color="#f39c12", 
        s=85, 
        alpha=0.9,
        ax=ax1
    )
    ax1.set_title("1. Displayed Stars vs. True Customer Happiness", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Average Star Rating (<= 3.0)")
    ax1.set_ylabel("Positive Review Share (%)")
    ax1.axhline(65, color="grey", linestyle="--", alpha=0.6)

    # Plot 2: Total Reviews Distribution (Sample Size View)
    sns.countplot(
        data=df_b, 
        x="total_reviews", 
        palette="YlOrBr", 
        ax=ax2
    )
    ax2.set_title("2. Review Count per Product (Sample Volume)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Total Reviews per Item")
    ax2.set_ylabel("Product Count")

    # Simple Meaning Box at the bottom
    takeaway = (
        "ARTHAM (Takeaway):\n"
        "• Ee products display rating thakkuva (<= 3.0 stars) unna kooda, reviews lo 65% nunchi 100% varaku positive maatalu unnai.\n"
        "• Graph 2 lo chusthe majority items ki kevalam 2 to 4 reviews matrame unnai (Sample Size Truncation).\n"
        "• Okkare 1-star ivvadam valla motham rating padipoina 'Hidden Gems' ivi. Ee products meeda deep check cheyali."
    )
    plt.figtext(
        0.5, -0.15, takeaway, wrap=True, horizontalalignment='center',
        fontsize=11, bbox=dict(boxstyle='round,pad=0.6', facecolor='#f8f9fa', edgecolor='#bdc3c7')
    )

    chart_file = os.path.join(OUTPUT_DIR, "chart_scenario_b_base.png")
    plt.tight_layout()
    plt.savefig(chart_file, dpi=300, bbox_inches='tight')
    print(f"\nSaved Baseline Chart: {chart_file}")

    con.close()
    print("=" * 65)
    print("Step 1 Complete! Ready for Deep Forensics.")

if __name__ == "__main__":
    run_scenario_b_base()