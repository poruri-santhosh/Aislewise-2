import os
import duckdb
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

DUCKDB_PATH = "warehouse.duckdb"

MONGO_URI = os.getenv("MONGO_URI", "YOUR_ACTUAL_MONGODB_URI_HERE")
DB_NAME = "aislewise_db"
COLLECTION_NAME = "product_details"

def sync_products():
    print("=" * 65)
    print("      MONGODB ATLAS TO DUCKDB SYNC ENGINE      ")
    print("=" * 65)

    print("1. Connecting to MongoDB Atlas with TLS bypass...")
    client = MongoClient(
        MONGO_URI,
        tls=True,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=15000
    )
    
    db = client[DB_NAME]
    col = db[COLLECTION_NAME]

    doc_count = col.count_documents({})
    print(f"Found {doc_count:,} documents in collection '{COLLECTION_NAME}'")

    if doc_count == 0:
        print("Collection is empty! Check DB or Collection name.")
        client.close()
        return

    print("2. Fetching records from MongoDB...")
    # ప్రొజెక్షన్ లేకుండా లేదా సురక్షితంగా రికార్డులు లాగడం
    cursor = col.find({}, {
        "product_id": 1, 
        "parent_asin": 1, 
        "_id": 1, 
        "title": 1, 
        "price": 1, 
        "average_rating": 1
    })
    data = list(cursor)

    df = pd.DataFrame(data)

    # 1. Product ID mapping
    if "product_id" not in df.columns:
        if "parent_asin" in df.columns:
            df["product_id"] = df["parent_asin"]
        elif "_id" in df.columns:
            df["product_id"] = df["_id"]

    # 2. Safe check for missing columns (KeyError రాకుండా డిఫాల్ట్ చేయడం)
    for col_name in ["title", "price", "average_rating"]:
        if col_name not in df.columns:
            df[col_name] = None

    # 3. Data type conversions
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["average_rating"] = pd.to_numeric(df["average_rating"], errors="coerce")
    df["title"] = df["title"].fillna("").astype(str)

    target_cols = ["product_id", "title", "price", "average_rating"]
    df_clean = df[target_cols].drop_duplicates(subset=["product_id"])

    print("3. Inserting into DuckDB 'bronze_products'...")
    con = duckdb.connect(DUCKDB_PATH)
    con.execute("CREATE OR REPLACE TABLE bronze_products AS SELECT * FROM df_clean;")

    total = con.execute("SELECT COUNT(*) FROM bronze_products;").fetchone()[0]
    print(f"Success! bronze_products table has {total:,} rows.")

    sample = con.execute("SELECT * FROM bronze_products LIMIT 5;").df()
    print("\nSample Preview in DuckDB:")
    print(sample.to_string(index=False))

    con.close()
    client.close()
    print("=" * 65)

if __name__ == "__main__":
    sync_products()