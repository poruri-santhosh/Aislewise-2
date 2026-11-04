"""
One-time backfill: rebuilds gold_product_discrepancy_flags in warehouse.duckdb
with the Scenario C flag and avg_ml_confidence column added.
Run once after updating incremental_sync.py.
"""
import sys
sys.path.insert(0, ".")

import duckdb
from incremental_sync import _build_gold_flags

print("Rebuilding gold_product_discrepancy_flags with Scenario C + avg_ml_confidence ...")
con = duckdb.connect("warehouse.duckdb")
_build_gold_flags(con)
con.close()

# Verify
con = duckdb.connect("warehouse.duckdb", read_only=True)
result = con.execute("""
    SELECT flag, COUNT(*) AS product_count
    FROM gold_product_discrepancy_flags
    GROUP BY flag
    ORDER BY product_count DESC
""").fetchall()

print("Gold flags after backfill:")
for row in result:
    print(f"  {row[0]}: {row[1]:,}")

cols = con.execute("DESCRIBE gold_product_discrepancy_flags").fetchall()
print("Columns:", [c[0] for c in cols])

sc_c = con.execute("""
    SELECT COUNT(*) FROM gold_product_discrepancy_flags
    WHERE flag = 'INVESTIGATE_SCENARIO_C'
""").fetchone()[0]
print(f"Scenario C flagged products: {sc_c:,}")

con.close()
print("Done.")
