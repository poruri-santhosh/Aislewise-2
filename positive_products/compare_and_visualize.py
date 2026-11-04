import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

DUCKDB_PATH = "warehouse.duckdb"

def create_simple_charts():
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    sns.set_theme(style="whitegrid")

    # =========================================================================
    # GRAPH 1: OVERALL HEALTH (Sentiment Distribution & Discrepancies)
    # =========================================================================
    df_sentiment = con.execute("""
        SELECT sentiment, COUNT(*) as count 
        FROM silver_reviews 
        GROUP BY sentiment
    """).df()

    df_flags = con.execute("""
        SELECT flag, COUNT(*) as count 
        FROM gold_product_discrepancy_flags 
        GROUP BY flag
    """).df()

    # Simple Labels Mapping
    sentiment_map = {
        'positive': 'Happy / Positive (41k)',
        'negative': 'Angry / Negative (7k)',
        'neutral': 'Neutral / Mixed (1.6k)'
    }
    df_sentiment['simple_label'] = df_sentiment['sentiment'].map(sentiment_map)

    flag_map = {
        'NORMAL': 'Normal Products (Rating = Reviews)',
        'INVESTIGATE_SCENARIO_A': 'Trap Products (High Rating, Bad Reviews!)',
        'INVESTIGATE_SCENARIO_B': 'Hidden Gems (Low Rating, Good Reviews)'
    }
    df_flags['simple_label'] = df_flags['flag'].map(flag_map)

    fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Subplot 1: Customer Mood
    sns.barplot(data=df_sentiment, x='simple_label', y='count', ax=ax1, palette=['#2ecc71', '#e74c3c', '#95a5a6'])
    ax1.set_title("1. How Customers Feel Overall (50,000 Reviews)", fontsize=13, fontweight='bold')
    ax1.set_xlabel("")
    ax1.set_ylabel("Number of Reviews")

    # Subplot 2: Products Health
    sns.barplot(data=df_flags, x='simple_label', y='count', ax=ax2, palette=['#3498db', '#e74c3c', '#f39c12'])
    ax2.set_title("2. Products With Misleading Ratings", fontsize=13, fontweight='bold')
    ax2.set_xlabel("")
    ax2.set_ylabel("Number of Products")
    ax2.tick_params(axis='x', rotation=15)

    # Explanation text at the bottom
    meaning_text1 = (
        "ARTHAM (Takeaway):\n"
        "• Most reviews (82%) positive ga unnai, kaani 440 products lo oka 'Rating Trap' undi!\n"
        "• Ee 440 products ki 4+ Star rating unna kooda, lopala 35%+ mandi customers thiduthu negative reviews raasaru."
    )
    plt.figtext(0.5, -0.08, meaning_text1, wrap=True, horizontalalignment='center', 
                fontsize=11, bbox=dict(boxstyle='round,pad=0.7', facecolor='#f8f9fa', edgecolor='#bdc3c7'))

    plt.tight_layout()
    plt.savefig("simple_overview_chart.png", dpi=300, bbox_inches='tight')
    print("Saved: simple_overview_chart.png")

    # =========================================================================
    # GRAPH 2: COMPARISON (Positive Champions vs Scenario A Traps)
    # =========================================================================
    df_comp_scatter = con.execute("""
        SELECT 
            avg_star_rating,
            positive_pct,
            negative_pct,
            CASE 
                WHEN flag = 'INVESTIGATE_SCENARIO_A' THEN 'Dangerous Trap (High Stars, Many Complaints)'
                WHEN avg_star_rating >= 4.0 AND positive_pct >= 80.0 THEN 'Genuinely Good (High Stars & Loved)'
                WHEN flag = 'INVESTIGATE_SCENARIO_B' THEN 'Underrated (Low Stars, Good Words)'
                ELSE 'Normal Product'
            END as product_type
        FROM gold_product_discrepancy_flags
        WHERE total_reviews >= 3;
    """).df()

    df_bar_comp = con.execute("""
        SELECT 
            CASE 
                WHEN flag = 'INVESTIGATE_SCENARIO_A' THEN 'Dangerous Trap\n(Scenario A)'
                WHEN avg_star_rating >= 4.0 AND positive_pct >= 80.0 THEN 'Genuinely Good\n(Champions)'
                WHEN flag = 'INVESTIGATE_SCENARIO_B' THEN 'Underrated\n(Scenario B)'
                ELSE 'Normal'
            END as product_type,
            ROUND(AVG(negative_pct), 1) as avg_bad_review_pct
        FROM gold_product_discrepancy_flags
        GROUP BY 1
        ORDER BY avg_bad_review_pct DESC
    """).df()

    fig2, (bx1, bx2) = plt.subplots(1, 2, figsize=(16, 6))

    # Scatter Plot with easy names
    color_dict = {
        'Genuinely Good (High Stars & Loved)': '#2ecc71',
        'Dangerous Trap (High Stars, Many Complaints)': '#e74c3c',
        'Underrated (Low Stars, Good Words)': '#f39c12',
        'Normal Product': '#bdc3c7'
    }

    sns.scatterplot(
        data=df_comp_scatter,
        x="avg_star_rating",
        y="positive_pct",
        hue="product_type",
        palette=color_dict,
        alpha=0.7,
        s=60,
        ax=bx1
    )
    bx1.set_title("Customer Stars vs. True Review Happiness", fontsize=13, fontweight='bold')
    bx1.set_xlabel("Displayed Star Rating (1 to 5)")
    bx1.set_ylabel("True Happy Reviews %")
    bx1.legend(loc='lower left', fontsize=9)

    # Bar chart showing complaint share
    sns.barplot(
        data=df_bar_comp,
        x="product_type",
        y="avg_bad_review_pct",
        palette=['#c0392b', '#7f8c8d', '#d35400', '#27ae60'],
        ax=bx2
    )
    bx2.set_title("Average Complaint Rate (% of Bad Reviews)", fontsize=13, fontweight='bold')
    bx2.set_xlabel("")
    bx2.set_ylabel("Complaint Percentage (%)")

    # Explanation text at the bottom
    meaning_text2 = (
        "ARTHAM (Takeaway):\n"
        "• Red dots (Dangerous Traps): Ee items ki 4.0 paina stars unna, vatikosthunna reviews lo 80% negative text ae undi!\n"
        "• Green dots (Genuinely Good): Ee items ratings and reviews rendu consistent ga unnai (genuine quality).\n"
        "• Idi chusi business owners / buyers rating ni blind ga trust cheyakunda mosapokunda untaru."
    )
    plt.figtext(0.5, -0.09, meaning_text2, wrap=True, horizontalalignment='center', 
                fontsize=11, bbox=dict(boxstyle='round,pad=0.7', facecolor='#f8f9fa', edgecolor='#bdc3c7'))

    plt.tight_layout()
    plt.savefig("simple_comparison_chart.png", dpi=300, bbox_inches='tight')
    print("Saved: simple_comparison_chart.png")

    con.close()

if __name__ == "__main__":
    create_simple_charts()