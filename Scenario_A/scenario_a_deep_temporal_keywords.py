import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import re

DUCKDB_PATH = "warehouse.duckdb"

def extract_meaningful_phrases(texts):
    # Common words to filter out
    custom_stops = {
        'the', 'and', 'to', 'a', 'of', 'it', 'is', 'i', 'this', 'that', 'in', 
        'was', 'for', 'my', 'with', 'but', 'on', 'have', 'be', 'they', 
        'so', 'you', 'very', 'at', 'had', 'as', 'are', 'from', 'we', 'an'
    }
    phrases = []
    for t in texts:
        words = re.findall(r'\b[a-z]{2,}\b', str(t).lower())
        filtered = [w for w in words if w not in custom_stops]
        for i in range(len(filtered) - 1):
            w1, w2 = filtered[i], filtered[i+1]
            if w1 != w2:
                phrases.append(f"{w1} {w2}")
    return Counter(phrases).most_common(10)

def run_scenario_a_forensics():
    con = duckdb.connect(DUCKDB_PATH)
    sns.set_theme(style="whitegrid")

    print("=" * 65)
    print(" SCENARIO A: TEMPORAL DECAY, IMPACT & DEFECT KEYWORDS AUDIT ")
    print("=" * 65)

    # 1. Timeline Shift (Yearly Trend)
    print("\n[1] Calculating Quality Decay Over Time...")
    df_temporal = con.execute("""
        SELECT 
            year(to_timestamp(r.timestamp / 1000)) as review_year,
            COUNT(*) as total_reviews,
            COUNT(CASE WHEN r.sentiment = 'negative' THEN 1 END) as neg_count,
            ROUND(COUNT(CASE WHEN r.sentiment = 'negative' THEN 1 END) * 100.0 / COUNT(*), 1) as neg_pct
        FROM silver_reviews r
        JOIN gold_product_discrepancy_flags f ON r.product_id = f.product_id
        WHERE f.flag = 'INVESTIGATE_SCENARIO_A'
        GROUP BY review_year
        HAVING review_year >= 2015 AND total_reviews >= 10
        ORDER BY review_year;
    """).df()

    print("\nYearly Decay Progression (Scenario A Products):")
    print(df_temporal.to_string(index=False))

    # 2. Helpful-Weighted Impact Ranking
    print("\n[2] Computing Helpful-Weighted Customer Dissatisfaction...")
    con.execute("""
        CREATE OR REPLACE TABLE gold_scenario_a_impact_ranking AS
        SELECT 
            r.product_id,
            f.avg_star_rating,
            f.negative_pct,
            COUNT(r.review_id) as total_neg_reviews,
            SUM(COALESCE(r.helpful_vote, 0)) as total_complaint_upvotes,
            ROUND(SUM(1 + COALESCE(r.helpful_vote, 0)), 1) as weighted_dissatisfaction_score
        FROM silver_reviews r
        JOIN gold_product_discrepancy_flags f ON r.product_id = f.product_id
        WHERE f.flag = 'INVESTIGATE_SCENARIO_A' AND r.sentiment = 'negative'
        GROUP BY r.product_id, f.avg_star_rating, f.negative_pct
        ORDER BY weighted_dissatisfaction_score DESC;
    """)

    df_top_impact = con.execute("""
        SELECT product_id, avg_star_rating, negative_pct, total_neg_reviews, total_complaint_upvotes, weighted_dissatisfaction_score
        FROM gold_scenario_a_impact_ranking
        LIMIT 5;
    """).df()
    print("\nTop 5 High-Impact Trap Products (Weighted by Upvotes):")
    print(df_top_impact.to_string(index=False))

    # 3. Defect Phrase Extraction (2-Word N-Grams)
    print("\n[3] Extracting Recurring Defect N-Grams...")
    all_neg_texts = con.execute("""
        SELECT r.text 
        FROM silver_reviews r
        JOIN gold_product_discrepancy_flags f ON r.product_id = f.product_id
        WHERE f.flag = 'INVESTIGATE_SCENARIO_A' AND r.sentiment = 'negative';
    """).fetchall()

    top_phrases = extract_meaningful_phrases([t[0] for t in all_neg_texts])
    df_phrases = pd.DataFrame(top_phrases, columns=['Defect_Phrase', 'Occurrences'])
    print("\nTop Recurring Defect Phrases:")
    print(df_phrases.to_string(index=False))

    # 4. Generate Visualizations
    print("\n[4] Generating Visualization Charts...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))

    # Chart 1: Quality Decay Line Plot
    sns.lineplot(
        data=df_temporal, 
        x='review_year', 
        y='neg_pct', 
        marker='o', 
        color='#c0392b', 
        linewidth=2.5, 
        ax=ax1
    )
    ax1.set_title("1. Scenario A: Quality Decay Trend Over Time", fontsize=12, fontweight='bold')
    ax1.set_ylabel("Negative Reviews Share (%)")
    ax1.set_xlabel("Review Year")
    for x, y in zip(df_temporal['review_year'], df_temporal['neg_pct']):
        ax1.annotate(f"{y}%", (x, y), textcoords="offset points", xytext=(0, 7), ha='center', fontweight='bold')

    # Chart 2: Defect Keywords Bar Chart
    sns.barplot(
        data=df_phrases, 
        x='Occurrences', 
        y='Defect_Phrase', 
        hue='Defect_Phrase',
        palette='Reds_r', 
        legend=False,
        ax=ax2
    )
    ax2.set_title("2. Top 10 Recurring Defect & Complaint Phrases", fontsize=12, fontweight='bold')
    ax2.set_xlabel("Frequency Count")
    ax2.set_ylabel("")

    takeaway = (
        "Key Takeaways:\n"
        "- Quality Decay: Shows whether customer complaints spiked in recent years or remained steady over time.\n"
        "- Defect N-Grams: Uncovers specific repeating phrases like 'did not', 'stopped working', or 'not fit'.\n"
        "- Helpful Weighting: Ranks products whose complaints received the highest upvotes from other buyers."
    )
    plt.figtext(
        0.5, -0.15, takeaway, wrap=True, horizontalalignment='center',
        fontsize=11, bbox=dict(boxstyle='round,pad=0.6', facecolor='#f8f9fa', edgecolor='#bdc3c7')
    )

    plt.tight_layout()
    plt.savefig("chart_scenario_a_forensics.png", dpi=300, bbox_inches='tight')
    print("Saved Chart: chart_scenario_a_forensics.png")

    con.close()
    print("=" * 65)
    print("Forensics analysis complete!")

if __name__ == "__main__":
    run_scenario_a_forensics()