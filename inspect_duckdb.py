import duckdb

conn = duckdb.connect("warehouse.duckdb", read_only=True)

print("=== 1. SILVER REVIEWS COUNT & SENTIMENT ===")
print(conn.execute("""
    SELECT sentiment, COUNT(*) as count 
    FROM silver_reviews 
    GROUP BY sentiment;
""").df())

print("\n=== 2. GOLD DISCREPANCY FLAGS SUMMARY ===")
print(conn.execute("""
    SELECT flag, COUNT(*) as product_count 
    FROM gold_product_discrepancy_flags 
    GROUP BY flag;
""").df())

print("\n=== 3. TOP SCENARIO A PRODUCTS (High Rating, Bad Reviews) ===")
print(conn.execute("""
    SELECT product_id, total_reviews, avg_star_rating, negative_pct, flag
    FROM gold_product_discrepancy_flags
    WHERE flag = 'INVESTIGATE_SCENARIO_A'
    ORDER BY total_reviews DESC
    LIMIT 5;
""").df())

print("\n=== 4. TOP SCENARIO B PRODUCTS (Low Rating, Good Reviews) ===")
print(conn.execute("""
    SELECT product_id, total_reviews, avg_star_rating, positive_pct, flag
    FROM gold_product_discrepancy_flags
    WHERE flag = 'INVESTIGATE_SCENARIO_B'
    ORDER BY total_reviews DESC
    LIMIT 5;
""").df())

conn.close()