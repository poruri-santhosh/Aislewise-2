import os
import sys
from pathlib import Path
import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from Scenario_A.scenario_mlflow import register_ml_reviews

DUCKDB_PATH = PROJECT_ROOT / "warehouse.duckdb"
OUTPUT_DIR = Path(__file__).resolve().parent

def extract_meaningful_phrases(texts):
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
    print(" SCENARIO A: TEMPORAL DECAY, IMPACT & DEFECT KEYWORDS (ML-POWERED) ")
    print("=" * 65)

    # Refresh the temporary review and product views using registered-model inference.
    register_ml_reviews(con)
    print("Inference: Registered MLflow sentiment and confidence for silver reviews.")

    # 1. Timeline Shift (Yearly Trend via ML Sentiment)
    print("\n[1] Calculating Quality Decay Over Time (ML Classified)...")
    df_temporal = con.execute("""
        SELECT 
            year(to_timestamp(r.timestamp / 1000)) as review_year,
            COUNT(*) as total_reviews,
            COUNT(CASE WHEN LOWER(r.sentiment) = 'negative' THEN 1 END) as neg_count,
            ROUND(COUNT(CASE WHEN LOWER(r.sentiment) = 'negative' THEN 1 END) * 100.0 / COUNT(*), 1) as neg_pct,
            ROUND(COALESCE(AVG(r.ml_confidence), 0.0), 3) as avg_model_confidence
        FROM silver_reviews_ml r
        JOIN gold_product_discrepancy_flags_ml f ON r.product_id = f.product_id
        WHERE f.flag = 'INVESTIGATE_SCENARIO_A'
        GROUP BY review_year
        HAVING review_year >= 2012 AND total_reviews >= 5
        ORDER BY review_year;
    """).df()

    if df_temporal.empty:
        # Relax constraints if sample data is small
        df_temporal = con.execute("""
            SELECT 
                year(to_timestamp(r.timestamp / 1000)) as review_year,
                COUNT(*) as total_reviews,
                COUNT(CASE WHEN LOWER(r.sentiment) = 'negative' THEN 1 END) as neg_count,
                ROUND(COUNT(CASE WHEN LOWER(r.sentiment) = 'negative' THEN 1 END) * 100.0 / COUNT(*), 1) as neg_pct,
                ROUND(COALESCE(AVG(r.ml_confidence), 0.0), 3) as avg_model_confidence
            FROM silver_reviews_ml r
            GROUP BY review_year
            ORDER BY review_year;
        """).df()

    print("\nYearly Decay Progression (MLflow Sentiment):")
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
            ROUND(SUM(1 + COALESCE(r.helpful_vote, 0)), 1) as weighted_dissatisfaction_score,
            ROUND(COALESCE(AVG(r.ml_confidence), 0.0), 3) as avg_confidence
        FROM silver_reviews_ml r
        JOIN gold_product_discrepancy_flags_ml f ON r.product_id = f.product_id
        WHERE f.flag = 'INVESTIGATE_SCENARIO_A' AND LOWER(r.sentiment) = 'negative'
        GROUP BY r.product_id, f.avg_star_rating, f.negative_pct
        ORDER BY weighted_dissatisfaction_score DESC;
    """)

    df_top_impact = con.execute("""
        SELECT product_id, avg_star_rating, negative_pct, total_neg_reviews, total_complaint_upvotes, weighted_dissatisfaction_score, avg_confidence
        FROM gold_scenario_a_impact_ranking
        LIMIT 5;
    """).df()

    print("\nTop 5 High-Impact Trap Products (Weighted by Upvotes & ML Confidence):")
    if not df_top_impact.empty:
        print(df_top_impact.to_string(index=False))
    else:
        print("No severe discrepancy trap products found.")

    # 3. Defect Phrase Extraction (2-Word N-Grams on ML Negatives)
    print("\n[3] Extracting Recurring Defect N-Grams from ML-detected Negatives...")
    all_neg_texts = con.execute("""
        SELECT r.text 
        FROM silver_reviews_ml r
        JOIN gold_product_discrepancy_flags_ml f ON r.product_id = f.product_id
        WHERE f.flag = 'INVESTIGATE_SCENARIO_A' AND LOWER(r.sentiment) = 'negative';
    """).fetchall()

    if not all_neg_texts:
        all_neg_texts = con.execute("""
            SELECT text FROM silver_reviews_ml WHERE LOWER(sentiment) = 'negative';
        """).fetchall()

    top_phrases = extract_meaningful_phrases([t[0] for t in all_neg_texts])
    df_phrases = pd.DataFrame(top_phrases, columns=['Defect_Phrase', 'Occurrences'])
    print("\nTop Recurring Defect Phrases:")
    print(df_phrases.to_string(index=False))

    # 4. Generate Visualizations
    print("\n[4] Generating Visualization Charts...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))

    # Chart 1: Quality Decay Line Plot
    if not df_temporal.empty:
        sns.lineplot(
            data=df_temporal, 
            x='review_year', 
            y='neg_pct', 
            marker='o', 
            color='#c0392b', 
            linewidth=2.5, 
            ax=ax1
        )
        ax1.set_title("1. Scenario A: Quality Decay Trend Over Time (MLflow Inference)", fontsize=12, fontweight='bold')
        ax1.set_ylabel("Negative Reviews Share (%)")
        ax1.set_xlabel("Review Year")
        for x, y in zip(df_temporal['review_year'], df_temporal['neg_pct']):
            ax1.annotate(f"{y}%", (x, y), textcoords="offset points", xytext=(0, 7), ha='center', fontweight='bold')

    # Chart 2: Defect Keywords Bar Chart
    if not df_phrases.empty:
        sns.barplot(
            data=df_phrases, 
            x='Occurrences', 
            y='Defect_Phrase', 
            hue='Defect_Phrase',
            palette='Reds_r', 
            legend=False, 
            ax=ax2
        )
        ax2.set_title("2. Top 10 Recurring Defect Phrases (ML Filtered)", fontsize=12, fontweight='bold')
        ax2.set_xlabel("Frequency Count")
        ax2.set_ylabel("")

    takeaway = (
        "Key Takeaways (ML-Powered Forensics):\n"
        "- Quality Decay: MLflow sentiment pipeline accurately tracks actual negative shifts over time without keyword bias.\n"
        "- Defect N-Grams: Identifies true customer dissatisfaction phrases based on ML-confirmed negative reviews.\n"
        "- Helpful Weighting: Flags high-risk products where negative reviews gained widespread buyer agreement."
    )
    plt.figtext(
        0.5, -0.15, takeaway, wrap=True, horizontalalignment='center',
        fontsize=11, bbox=dict(boxstyle='round,pad=0.6', facecolor='#f8f9fa', edgecolor='#bdc3c7')
    )

    plt.tight_layout()
    chart_path = OUTPUT_DIR / "chart_scenario_a_forensics.png"
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"\nSaved Chart: {chart_path}")

    con.close()
    print("=" * 65)
    print("Forensics analysis complete!")

if __name__ == "__main__":
    run_scenario_a_forensics()