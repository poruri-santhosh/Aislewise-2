import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

DUCKDB_PATH = "warehouse.duckdb"

def run_manipulation_and_price_audit():
    con = duckdb.connect(DUCKDB_PATH)
    sns.set_theme(style="whitegrid")

    print("=" * 65)
    print(" 1. TIME BURST & REVIEW MANIPULATION DETECTION ")
    print("=" * 65)

    # Convert epoch timestamp to date and find daily spikes per product
    con.execute("""
        CREATE OR REPLACE TABLE gold_review_daily_velocity AS
        SELECT 
            product_id,
            strftime(to_timestamp(timestamp / 1000), '%Y-%m-%d') as review_date,
            COUNT(*) as reviews_in_day,
            COUNT(CASE WHEN sentiment = 'positive' THEN 1 END) as pos_in_day,
            COUNT(CASE WHEN sentiment = 'negative' THEN 1 END) as neg_in_day
        FROM silver_reviews
        GROUP BY product_id, review_date;
    """)

    # Find products with unnatural spikes (e.g. >= 5 reviews on a single day)
    df_spikes = con.execute("""
        SELECT 
            product_id, 
            review_date, 
            reviews_in_day, 
            pos_in_day, 
            neg_in_day
        FROM gold_review_daily_velocity
        WHERE reviews_in_day >= 4
        ORDER BY reviews_in_day DESC
        LIMIT 10;
    """).df()

    print("\nSuspicious Review Spikes (Potential Review Injection / Bombing):")
    if not df_spikes.empty:
        print(df_spikes.to_string(index=False))
    else:
        print("No unnatural daily velocity spikes found (Reviews are naturally distributed).")

    print("\n" + "=" * 65)
    print(" 2. PRICE VS. DEFECT RATE AUDIT ")
    print("=" * 65)

    # Join with Bronze products to get price
    df_price_defect = con.execute("""
        SELECT 
            f.product_id,
            p.price,
            f.avg_star_rating,
            f.negative_pct,
            f.flag
        FROM gold_product_discrepancy_flags f
        JOIN bronze_products p ON f.product_id = p.product_id
        WHERE p.price IS NOT NULL AND p.price > 0
        ORDER BY p.price DESC;
    """).df()

    if not df_price_defect.empty:
        # Segment into price tiers
        df_price_defect["price_tier"] = pd.qcut(df_price_defect["price"], q=3, labels=["Budget", "Mid-Range", "Premium"])
        
        df_tier_summary = df_price_defect.groupby("price_tier", observed=False).agg(
            total_items=("product_id", "count"),
            avg_price=("price", "mean"),
            avg_neg_share=("negative_pct", "mean"),
            trap_items=("flag", lambda x: (x == "INVESTIGATE_SCENARIO_A").sum())
        ).reset_index()

        print("\nPrice Tier vs. Quality Failure Summary:")
        print(df_tier_summary.to_string(index=False))

        # Visualization
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))

        sns.barplot(
            data=df_tier_summary, 
            x="price_tier", 
            y="avg_neg_share", 
            hue="price_tier", 
            palette="mako", 
            legend=False, 
            ax=ax1
        )
        ax1.set_title("Average Negative Review % by Price Tier", fontsize=12, fontweight="bold")
        ax1.set_ylabel("Negative Reviews %")
        ax1.set_xlabel("")

        sns.barplot(
            data=df_tier_summary, 
            x="price_tier", 
            y="trap_items", 
            hue="price_tier", 
            palette="rocket", 
            legend=False, 
            ax=ax2
        )
        ax2.set_title("Total Rating Trap Items by Price Tier", fontsize=12, fontweight="bold")
        ax2.set_ylabel("Number of Scenario A Items")
        ax2.set_xlabel("")

        takeaway = (
            "ARTHAM (Takeaway):\n"
            "• Ee analysis dwara price ekkuva unna premium products lo kuda defects/rating traps unnaya leda budget items lone unnaya anedi telustundi.\n"
            "• Idi marketplace vendor evaluation mariyu catalog pricing strategy ki chala help authundi."
        )
        plt.figtext(0.5, -0.15, takeaway, wrap=True, horizontalalignment='center',
                    fontsize=11, bbox=dict(boxstyle='round,pad=0.6', facecolor='#f8f9fa', edgecolor='#bdc3c7'))

        plt.tight_layout()
        plt.savefig("chart_price_vs_defects.png", dpi=300, bbox_inches='tight')
        print("\nSaved Chart: chart_price_vs_defects.png")

    con.close()
    print("=" * 65)
    print("Audit finished successfully!")

if __name__ == "__main__":
    run_manipulation_and_price_audit()