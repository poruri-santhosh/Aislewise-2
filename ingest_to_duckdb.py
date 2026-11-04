import os
import duckdb
import psycopg2
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

PG_URL = os.getenv("NEON_DATABASE_URL")
MONGO_URI = os.getenv("MONGO_URI")
DUCKDB_PATH = "aislewise_warehouse.duckdb"

print("=== STARTING DUCKDB BRONZE INGESTION ===")

# DuckDB Warehouse Connect చేయడం
con = duckdb.connect(DUCKDB_PATH)

# ----------------------------------------------------
# 1. EXTRACT FROM POSTGRESQL (NEON) -> DUCKDB BRONZE
# ----------------------------------------------------
print("\n[1/3] Extracting data from PostgreSQL (Neon)...")
pg_conn = psycopg2.connect(PG_URL)

# Products from Postgres
print("Fetching PostgreSQL products...")
df_pg_products = pd.read_sql("SELECT * FROM products;", pg_conn)
con.execute("CREATE OR REPLACE TABLE bronze_pg_products AS SELECT * FROM df_pg_products;")
print(f" Loaded {len(df_pg_products)} records into 'bronze_pg_products'")

# Reviews from Postgres
print("Fetching PostgreSQL reviews...")
df_pg_reviews = pd.read_sql("SELECT * FROM reviews;", pg_conn)
con.execute("CREATE OR REPLACE TABLE bronze_pg_reviews AS SELECT * FROM df_pg_reviews;")
print(f" Loaded {len(df_pg_reviews)} records into 'bronze_pg_reviews'")

pg_conn.close()

# ----------------------------------------------------
# 2. EXTRACT FROM MONGODB ATLAS -> DUCKDB BRONZE
# ----------------------------------------------------
print("\n[2/3] Extracting data from MongoDB Atlas...")
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["aislewise_db"]

# Product details from Mongo (Metadata, Features, Specs)
print("Fetching MongoDB product_details collection...")
mongo_docs = list(mongo_db["product_details"].find({}, {
    "_id": 0,
    "product_id": 1,
    "features": 1,
    "description": 1,
    "details": 1,
    "images": 1,
    "categories": 1
}))

# Normalize nested structures as string/json for DuckDB Bronze
df_mongo = pd.DataFrame(mongo_docs)
# Nested lists/dicts ని స్ట్రింగ్/JSON ఫార్మాట్‌గా మారుస్తున్నాం
for col in ["features", "description", "details", "images", "categories"]:
    if col in df_mongo.columns:
        df_mongo[col] = df_mongo[col].astype(str)

con.execute("CREATE OR REPLACE TABLE bronze_mongo_details AS SELECT * FROM df_mongo;")
print(f" Loaded {len(df_mongo)} records into 'bronze_mongo_details'")

mongo_client.close()

# ----------------------------------------------------
# 3. VERIFICATION QUERY IN DUCKDB
# ----------------------------------------------------
print("\n[3/3] Verifying DuckDB Bronze Tables:")
tables_summary = con.execute("""
    SELECT 'bronze_pg_products' AS table_name, COUNT(*) AS row_count FROM bronze_pg_products
    UNION ALL
    SELECT 'bronze_pg_reviews', COUNT(*) FROM bronze_pg_reviews
    UNION ALL
    SELECT 'bronze_mongo_details', COUNT(*) FROM bronze_mongo_details;
""").fetchall()

for name, count in tables_summary:
    print(f" - {name}: {count} rows")

con.close()
print("\nBronze Layer setup completed successfully in DuckDB!")