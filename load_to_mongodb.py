
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, InsertOne
from tqdm import tqdm


# --------------------------------------------------
# 1. LOAD ENVIRONMENT VARIABLES
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE, override=True)

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError(
        "MONGO_URI not found. Check your .env file in the project root."
    )

print("Environment configuration:")
print(f".env exists: {ENV_FILE.exists()}")
print(f"Atlas URI: {MONGO_URI.startswith('mongodb+srv://')}")
print(f"Localhost URI: {'localhost' in MONGO_URI.lower()}")


# --------------------------------------------------
# 2. CONFIGURATION
# --------------------------------------------------

DB_NAME = "aislewise_db"

MONGO_DIR = BASE_DIR / "data_mongodb"

PRODUCTS_FILE = MONGO_DIR / "product_details_collection.jsonl"
REVIEWS_FILE = MONGO_DIR / "raw_reviews_collection.jsonl"

BATCH_SIZE = 5000


# --------------------------------------------------
# 3. LOAD JSONL IN BATCHES
# --------------------------------------------------

def load_jsonl_in_batches(collection, filepath, desc):

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    batch = []
    total_inserted = 0

    with open(filepath, "r", encoding="utf-8") as f:

        for line in tqdm(f, desc=desc):

            if not line.strip():
                continue

            doc = json.loads(line)

            batch.append(InsertOne(doc))

            if len(batch) >= BATCH_SIZE:

                result = collection.bulk_write(
                    batch,
                    ordered=False
                )

                total_inserted += result.inserted_count
                batch = []

        if batch:

            result = collection.bulk_write(
                batch,
                ordered=False
            )

            total_inserted += result.inserted_count

    print(
        f"Loaded {total_inserted} documents "
        f"into '{collection.name}'"
    )


# --------------------------------------------------
# 4. MAIN FUNCTION
# --------------------------------------------------

def main():

    print("\nConnecting to MongoDB Atlas...")

    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=10000
    )

    try:

        # Test connection before modifying collections
        client.admin.command("ping")

        print("MongoDB connection successful!")

        db = client[DB_NAME]

        prod_col = db["product_details"]
        rev_col = db["raw_reviews"]

        # WARNING: This deletes existing collection data.
        print("\nDropping existing collections if present...")

        prod_col.drop()
        rev_col.drop()

        # ------------------------------------------
        # PRODUCT DETAILS
        # ------------------------------------------

        print("\n========== LOADING PRODUCT DETAILS ==========")

        load_jsonl_in_batches(
            prod_col,
            PRODUCTS_FILE,
            "Products Progress"
        )

        # ------------------------------------------
        # RAW REVIEWS
        # ------------------------------------------

        print("\n========== LOADING RAW REVIEWS ==========")

        load_jsonl_in_batches(
            rev_col,
            REVIEWS_FILE,
            "Reviews Progress"
        )

        # ------------------------------------------
        # CREATE INDEXES
        # ------------------------------------------

        print("\nCreating indexes...")

        rev_col.create_index("product_id")
        rev_col.create_index("rating")

        prod_col.create_index("parent_asin")

        # ------------------------------------------
        # VERIFICATION
        # ------------------------------------------

        print("\n========== DATABASE VERIFICATION ==========")

        print(
            f"Total Products in Mongo: "
            f"{prod_col.count_documents({})}"
        )

        print(
            f"Total Reviews in Mongo: "
            f"{rev_col.count_documents({})}"
        )

        print("============================================")

        print("\nMongoDB ingestion completed successfully!")

    finally:

        client.close()


# --------------------------------------------------
# 5. EXECUTION
# --------------------------------------------------

if __name__ == "__main__":
    main()
