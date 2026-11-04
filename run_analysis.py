import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

DUCKDB_PATH = "warehouse.duckdb"

def run_portfolio_analysis():
    conn = duckdb.connect(DUCKDB_PATH, read_only=True)
    
    print("=" * 65)
    print("      AISLEWISE PRODUCT INTELLIGENCE & DISCREPANCY AUDIT     ")
    print("=" * 65)

    # 1. Overall Portfolio Metrics
    total_reviews = conn.execute("SELECT COUNT(*) FROM silver_reviews;").fetchone()[0]
    total_products = conn.execute("SELECT COUNT(DISTINCT product_id) FROM silver_reviews;").fetchone()[0]
    avg_rating = conn.execute("SELECT ROUND(AVG(rating), 2) FROM silver_reviews;").fetchone()[0]
    
    print("\n[STEP 1: OVERALL PORTFOLIO METRICS]")
    print(f"Total Analyzed Reviews : {total_reviews:,}")
    print(f"Total Unique Products  : {total_products:,}")
    print(f"Average Star Rating    : {avg_rating} / 5.0")

    # Sentiment distribution
    df_sentiment = conn.execute("""
        SELECT 
            sentiment, 
            COUNT(*) AS count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM silver_reviews), 2) AS percentage
        FROM silver_reviews
        GROUP BY sentiment
        ORDER BY count DESC;
    """).df()
    print("\nGlobal Sentiment Breakdown:")
    print(df_sentiment.to_string(index=False))

    # 2. Discrepancy Breakdown (Scenario A vs Scenario B)
    print("\n" + "=" * 65)
    print("[STEP 2: RATING DISCREPANCY AUDIT (GOLD LAYER)]")
    df_flags = conn.execute("""
        SELECT 
            flag, 
            COUNT(*) AS product_count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM gold_product_discrepancy_flags), 2) AS pct_of_products
        FROM gold_product_discrepancy_flags
        GROUP BY flag
        ORDER BY product_count DESC;
    """).df()
    print(df_flags.to_string(index=False))

    # 3. Top Scenario A Products (High Rating, but High Negative Reviews)
    print("\n" + "=" * 65)
    print("[STEP 3: TOP 5 SCENARIO A PRODUCTS (High Rating >= 4.0, Negative >= 35%)]")
    df_scenario_a = conn.execute("""
        SELECT 
            product_id,
            total_reviews,
            avg_star_rating,
            negative_pct,
            neg_count,
            pos_count
        FROM gold_product_discrepancy_flags
        WHERE flag = 'INVESTIGATE_SCENARIO_A'
        ORDER BY total_reviews DESC, negative_pct DESC
        LIMIT 5;
    """).df()
    print(df_scenario_a.to_string(index=False))

    # 4. Top Scenario B Products (Low Rating <= 3.0, but High Positive Reviews)
    print("\n" + "=" * 65)
    print("[STEP 4: TOP 5 SCENARIO B PRODUCTS (Low Rating <= 3.0, Positive >= 65%)]")
    df_scenario_b = conn.execute("""
        SELECT 
            product_id,
            total_reviews,
            avg_star_rating,
            positive_pct,
            pos_count,
            neg_count
        FROM gold_product_discrepancy_flags
        WHERE flag = 'INVESTIGATE_SCENARIO_B'
        ORDER BY total_reviews DESC, positive_pct DESC
        LIMIT 5;
    """).df()
    print(df_scenario_b.to_string(index=False))

    # 5. Deep Evidence Inspection on Top Scenario A Product
    if not df_scenario_a.empty:
        sample_prod_id = df_scenario_a.iloc[0]["product_id"]
        print("\n" + "=" * 65)
        print(f"[STEP 5: DRILL-DOWN INVESTIGATION ON PRODUCT: {sample_prod_id}]")
        
        sample_reviews = conn.execute(f"""
            SELECT rating, title, text 
            FROM silver_reviews
            WHERE product_id = '{sample_prod_id}' AND sentiment = 'negative'
            LIMIT 3;
        """).fetchall()

        print(f"Extracted Customer Complaint Evidence for {sample_prod_id}:")
        for idx, r in enumerate(sample_reviews, 1):
            print(f"\n  Evidence #{idx}: [{r[0]} Stars] '{r[1]}'")
            print(f"  Snippet: {r[2][:160]}...")

    # 6. Generate Analytical Plots
    print("\n" + "=" * 65)
    print("Generating Analytical Visualizations...")
    
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Plot 1: Sentiment Split
    sns.barplot(data=df_sentiment, x="sentiment", y="count", ax=axes[0], palette="viridis")
    axes[0].set_title("Overall Sentiment Distribution (50,000 Reviews)", fontsize=12, fontweight="bold")
    axes[0].set_ylabel("Review Count")

    # Plot 2: Discrepancy Flags Split
    sns.barplot(data=df_flags, x="flag", y="product_count", ax=axes[1], palette="magma")
    axes[1].set_title("Product Catalog Health & Anomaly Triage", fontsize=12, fontweight="bold")
    axes[1].set_ylabel("Product Count")
    axes[1].tick_params(axis='x', rotation=15)

    plt.tight_layout()
    plt.savefig("analytics_overview.png", dpi=300)
    print("Saved Chart: analytics_overview.png")

    conn.close()
    print("=" * 65)
    print("Analysis finished successfully!")

if __name__ == "__main__":
    run_portfolio_analysis()