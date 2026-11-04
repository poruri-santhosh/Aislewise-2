import os
import json
import duckdb
import pandas as pd
from datetime import datetime

DUCKDB_PATH = "warehouse.duckdb"
OUTPUT_DIR = os.path.join("Scenario_A", "vendor_memos")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_vendor_memos():
    con = duckdb.connect(DUCKDB_PATH)

    print("=" * 65)
    print(" SCENARIO A: AUTOMATED VENDOR ACTION MEMO GENERATOR ")
    print("=" * 65)

    # 1. Fetch Top 5 Worst Scenario A Products based on Weighted Dissatisfaction Score
    query = """
        SELECT 
            i.product_id,
            COALESCE(p.title, 'Appliance Replacement Part / Accessory') as product_title,
            i.avg_star_rating,
            i.negative_pct,
            i.total_neg_reviews,
            i.total_complaint_upvotes,
            i.weighted_dissatisfaction_score
        FROM gold_scenario_a_impact_ranking i
        LEFT JOIN bronze_products p ON i.product_id = p.product_id
        ORDER BY i.weighted_dissatisfaction_score DESC
        LIMIT 5;
    """
    df_worst = con.execute(query).df()
    print(f"Generating Official Action Memos for Top {len(df_worst)} Offending Vendors...\n")

    memos_summary = []

    for idx, row in df_worst.iterrows():
        p_id = row["product_id"]
        title = row["product_title"]
        stars = row["avg_star_rating"]
        neg_pct = row["negative_pct"]
        neg_count = row["total_neg_reviews"]
        upvotes = row["total_complaint_upvotes"]

        # Fetch Top Root-Cause Driver
        rc_query = f"""
            SELECT root_cause, COUNT(*) as cnt
            FROM gold_scenario_a_root_causes
            WHERE product_id = '{p_id}'
            GROUP BY root_cause
            ORDER BY cnt DESC
            LIMIT 1;
        """
        rc_res = con.execute(rc_query).fetchone()
        primary_defect = rc_res[0] if rc_res else "Unspecified Mechanical / Material Failure"

        # Fetch Verified Customer Evidence Quotes
        quotes_query = f"""
            SELECT rating, title, text, helpful_vote, verified_purchase
            FROM silver_reviews
            WHERE product_id = '{p_id}' AND sentiment = 'negative'
            ORDER BY helpful_vote DESC, rating ASC
            LIMIT 3;
        """
        quotes = con.execute(quotes_query).fetchall()

        memo_filename = f"VENDOR_NOTICE_{p_id}.txt"
        memo_path = os.path.join(OUTPUT_DIR, memo_filename)
        current_date = datetime.now().strftime("%B %d, %Y")

        memo_content = f"""================================================================================
                    OFFICIAL VENDOR QUALITY AUDIT NOTICE
               Aislewise Automated Marketplace Intelligence System
================================================================================
DATE: {current_date}
RECIPIENT: Quality Assurance & Product Operations (Supplier of ASIN: {p_id})
PRODUCT TITLE: {title}
ASIN / SKU: {p_id}
AUDIT CLASSIFICATION: CRITICAL RATING DISCREPANCY (SCENARIO A - TRAP LISTING)
ACTION REQUIRED: CORRECTIVE ACTION PLAN (CAP) WITHIN 14 BUSINESS DAYS
================================================================================

1. EXECUTIVE AUDIT SUMMARY
--------------------------
Our algorithmic monitoring detected an acute discrepancy between your public
star rating and authentic post-purchase customer feedback:
  * Public Marketplace Rating  : ⭐ {stars:.2f} / 5.00 (Deceptively High)
  * Analyzed Negative Reviews   : 🔴 {neg_pct:.1f}% ({neg_count} recorded severe failures)
  * Customer Dissatisfaction Upvotes : {upvotes:.0f} helpful votes from other buyers
  * Dominant Root-Cause Driver  : [{primary_defect.upper()}]

CONCLUSION: Your public star rating does not reflect recent manufacturing quality. 
Initial ratings mask ongoing durability degradation.

2. VERIFIED CUSTOMER COMPLAINT EVIDENCE (FORENSIC LOG)
------------------------------------------------------
"""
        for q_idx, q in enumerate(quotes, 1):
            memo_content += f"""  [EVIDENCE RECORD #{q_idx}]
    - Assigned Stars : ⭐ {q[0]} / 5.0 (Verified Buyer: {q[4]})
    - Other Buyers Upvoted : {q[3]} Helpful Votes
    - Subject Line   : "{q[1]}"
    - Ground Truth Statement:
      "{q[2]}"
--------------------------------------------------------------------------------
"""

        memo_content += f"""
3. MANDATORY CORRECTIVE ACTIONS
-------------------------------
To maintain active listing eligibility on the catalog, you must submit:
  [ ] Batch Material Testing Certificate addressing [{primary_defect}].
  [ ] Dimension / Fitment Verification Report ensuring accurate specification.
  [ ] Remediation roadmap for inventory manufactured after recent quality decay.

Failure to respond within 14 business days will result in automated de-ranking 
and permanent placement under the "Misleading Quality Trap" quarantine segment.

ISSUED BY:
Aislewise Product Integrity & Discrepancy Forensic Engine
Contact: integrity-ops@aislewise.internal
================================================================================
"""
        # Save Memo File
        with open(memo_path, "w", encoding="utf-8") as f:
            f.write(memo_content)

        print(f"  [+] Generated Action Memo: {memo_path}")

        memos_summary.append({
            "product_id": p_id,
            "product_title": title,
            "public_star_rating": float(stars),
            "negative_review_pct": float(neg_pct),
            "primary_defect": primary_defect,
            "memo_file": memo_filename
        })

    # Save summary JSON
    summary_json_path = os.path.join(OUTPUT_DIR, "vendor_notices_index.json")
    with open(summary_json_path, "w", encoding="utf-8") as jf:
        json.dump(memos_summary, jf, indent=2)

    print(f"\n[✓] Saved Index: {summary_json_path}")
    con.close()
    print("=" * 65)
    print("Scenario A Vendor Action Memos successfully generated!")

if __name__ == "__main__":
    generate_vendor_memos()