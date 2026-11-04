import sys
from pathlib import Path
import duckdb
import pandas as pd
import json
import matplotlib.pyplot as plt
import seaborn as sns
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from Scenario_A.scenario_mlflow import register_ml_reviews

DUCKDB_PATH = PROJECT_ROOT / "warehouse.duckdb"
OUTPUT_DIR = Path(__file__).resolve().parent
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Threshold Configuration
MIN_RATING = 4.0
MIN_NEG_PCT = 50.0  # 50% kante ekkuva negative reviews unteనే pick chestundi
MIN_REVIEWS = 3

def classify_complaint_severity(rating, sentiment):
    if sentiment == "negative" and rating <= 1.0:
        return "CRITICAL"
    return "HIGH"

def tag_issue_category(sentiment):
    return "Model-Classified Negative Experience" if sentiment == "negative" else "Other Experience"

def run_threshold_complaint_analysis():
    con = duckdb.connect(DUCKDB_PATH)
    sns.set_theme(style="whitegrid")
    register_ml_reviews(con)

    print("=" * 65)
    print(" SCENARIO A: THRESHOLD FILTER & DIRECT COMPLAINT REPORT ENGINE ")
    print(f" Thresholds: Rating >= {MIN_RATING} | Negative >= {MIN_NEG_PCT}% | Min Reviews >= {MIN_REVIEWS}")
    print("=" * 65)

    # 1. Filter High-Risk Products
    filter_query = f"""
        SELECT 
            product_id,
            total_reviews,
            avg_star_rating,
            negative_pct,
            neg_count,
            pos_count
        FROM gold_product_discrepancy_flags_ml
        WHERE avg_star_rating >= {MIN_RATING}
          AND negative_pct >= {MIN_NEG_PCT}
          AND total_reviews >= {MIN_REVIEWS}
        ORDER BY total_reviews DESC, negative_pct DESC;
    """
    df_severe_products = con.execute(filter_query).df()
    print(f"\nFiltered Severe Trap Products: {len(df_severe_products)}")
    print(df_severe_products.head(5).to_string(index=False))

    # 2. Extract Reviews and Convert to Direct Complaints
    con.register("severe_scenario_a_products", df_severe_products[["product_id"]])
    reviews_query = """
        SELECT 
            r.product_id,
            r.review_id,
            r.rating,
            r.title,
            r.text,
            r.verified_purchase,
            r.helpful_vote,
            r.sentiment,
            COALESCE(r.ml_confidence, 0.0) AS ml_confidence
        FROM silver_reviews_ml AS r
        INNER JOIN severe_scenario_a_products AS p
            ON r.product_id = p.product_id
        WHERE r.sentiment = 'negative'
        ORDER BY r.helpful_vote DESC, r.rating ASC;
    """
    if df_severe_products.empty:
        df_complaints_raw = pd.DataFrame(
            columns=[
                "product_id", "review_id", "rating", "title", "text",
                "verified_purchase", "helpful_vote", "sentiment", "ml_confidence",
            ]
        )
    else:
        df_complaints_raw = con.execute(reviews_query).df()

    complaints_list = []
    for _, row in df_complaints_raw.iterrows():
        severity = classify_complaint_severity(row["rating"], row["sentiment"])
        category = tag_issue_category(row["sentiment"])
        complaints_list.append({
            "product_id": row["product_id"],
            "review_id": row["review_id"],
            "assigned_rating": float(row["rating"]),
            "complaint_severity": severity,
            "issue_category": category,
            "complaint_title": str(row["title"]),
            "complaint_statement": str(row["text"]),
            "verified_buyer": bool(row["verified_purchase"]),
            "helpful_upvotes": int(row["helpful_vote"]) if pd.notnull(row["helpful_vote"]) else 0
        })

    complaint_columns = [
        "product_id", "review_id", "assigned_rating", "complaint_severity",
        "issue_category", "complaint_title", "complaint_statement",
        "verified_buyer", "helpful_upvotes",
    ]
    df_complaints = pd.DataFrame(complaints_list, columns=complaint_columns)

    # 3. Save to DuckDB Gold Layer
    con.execute("CREATE OR REPLACE TABLE gold_scenario_a_severe_complaints AS SELECT * FROM df_complaints;")

    # 4. Save Human-Readable Text Report
    report_file_txt = OUTPUT_DIR / "scenario_a_complaints_report.txt"
    with open(report_file_txt, "w", encoding="utf-8") as f:
        f.write("====================================================================\n")
        f.write("       AISLEWISE FORENSIC REPORT: SEVERE SCENARIO A COMPLAINTS       \n")
        f.write(f"  Generated Threshold: Rating >= {MIN_RATING} | Neg % >= {MIN_NEG_PCT}% | Min Reviews >= {MIN_REVIEWS}\n")
        f.write(f"  Total Severe Products Flagged: {len(df_severe_products)}\n")
        f.write(f"  Total Converted Customer Complaints: {len(df_complaints)}\n")
        f.write("====================================================================\n\n")

        for p_id in df_severe_products["product_id"]:
            p_meta = df_severe_products[df_severe_products["product_id"] == p_id].iloc[0]
            p_comps = df_complaints[df_complaints["product_id"] == p_id]

            f.write(f"PRODUCT ID: {p_id}\n")
            f.write(f"  - Displayed Star Rating: {p_meta['avg_star_rating']} / 5.0 (High Star Illusion)\n")
            f.write(f"  - Actual Negative Reviews: {p_meta['negative_pct']}% ({p_meta['neg_count']} out of {p_meta['total_reviews']} reviews)\n")
            f.write("  - Customer Evidence & Complaints Log:\n")

            for idx, c in enumerate(p_comps.to_dict(orient="records"), 1):
                f.write(f"    [{idx}] Severity: {c['complaint_severity']} | Issue: {c['issue_category']} | Stars: {c['assigned_rating']}\n")
                f.write(f"        Verified: {c['verified_buyer']} | Title: {c['complaint_title']}\n")
                f.write(f"        Complaint: \"{c['complaint_statement']}\"\n")
            f.write("-" * 68 + "\n\n")

    # 5. Save Structured JSON Report
    report_file_json = OUTPUT_DIR / "scenario_a_complaints_report.json"
    with open(report_file_json, "w", encoding="utf-8") as jf:
        json.dump(complaints_list, jf, indent=2)

    print(f"\nSaved Reports:")
    print(f"  - Text Log : {report_file_txt}")
    print(f"  - JSON Data: {report_file_json}")

    # 6. Visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))

    # Chart 1: Issue Categories Breakdown
    sns.countplot(
        data=df_complaints,
        x="issue_category",
        hue="issue_category",
        palette="Reds_r",
        legend=False,
        ax=ax1
    )
    ax1.set_title("1. What Are Customers Complaining About?", fontsize=12, fontweight="bold")
    ax1.set_xlabel("")
    ax1.set_ylabel("Complaint Count")
    ax1.tick_params(axis='x', rotation=15)

    # Chart 2: Severity Distribution
    sns.countplot(
        data=df_complaints,
        x="complaint_severity",
        hue="complaint_severity",
        palette={"CRITICAL": "#c0392b", "HIGH": "#e67e22"},
        legend=False,
        ax=ax2
    )
    ax2.set_title("2. Complaint Severity Breakdown", fontsize=12, fontweight="bold")
    ax2.set_xlabel("")
    ax2.set_ylabel("Count")

    takeaway = (
        "ARTHAM (Takeaway):\n"
        f"• Threshold filter dwara Display Rating >= {MIN_RATING} unna kooda 50%+ negative reviews unna extreme products ni filter chesam.\n"
        "• MLflow negative sentiment tho classify ayina reviews direct complaints ga convert cheyabaddayi.\n"
        "• Ee data file ('scenario_a_complaints_report.txt') vendor audit and quality assurance team ki direct action report ga panikosthundi."
    )
    plt.figtext(0.5, -0.15, takeaway, wrap=True, horizontalalignment='center',
                fontsize=11, bbox=dict(boxstyle='round,pad=0.6', facecolor='#f8f9fa', edgecolor='#bdc3c7'))

    plt.tight_layout()
    chart_path = OUTPUT_DIR / "chart_scenario_a_complaints.png"
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"Saved Chart: {chart_path}")

    con.close()
    print("=" * 65)
    print("Execution completed successfully!")

if __name__ == "__main__":
    run_threshold_complaint_analysis()