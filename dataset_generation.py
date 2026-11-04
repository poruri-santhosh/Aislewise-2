
import os
import json
import gzip
import urllib.request
import urllib.error
import pandas as pd
from tqdm import tqdm


# ============================================================
# 1. CONFIGURATION
# ============================================================

TARGET_REVIEWS = 50000
CATEGORY = "Appliances"

POSTGRES_DIR = "data_postgresql"
MONGO_DIR = "data_mongodb"

os.makedirs(POSTGRES_DIR, exist_ok=True)
os.makedirs(MONGO_DIR, exist_ok=True)

# Official UCSD dataset URLs
REVIEWS_URL = (
    "https://mcauleylab.ucsd.edu/"
    "public_datasets/data/amazon_2023/raw/"
    "review_categories/Appliances.jsonl.gz"
)

META_URL = (
    "https://mcauleylab.ucsd.edu/"
    "public_datasets/data/amazon_2023/raw/"
    "meta_categories/meta_Appliances.jsonl.gz"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def stream_jsonl_gz(url, description):
    """
    Stream a compressed JSONL file directly from its URL.
    Does not download the complete file to local storage.
    """

    request = urllib.request.Request(
        url,
        headers=HEADERS
    )

    try:
        response = urllib.request.urlopen(
            request,
            timeout=60
        )

        print(f"\nConnected to: {response.geturl()}")
        print(f"HTTP status: {response.status}")
        print(f"Content type: {response.headers.get('Content-Type')}")

        with response:
            with gzip.GzipFile(fileobj=response) as gz:

                for line_number, line in enumerate(gz, start=1):

                    if not line.strip():
                        continue

                    try:
                        item = json.loads(
                            line.decode("utf-8")
                        )
                        yield item

                    except (json.JSONDecodeError, UnicodeDecodeError) as error:
                        print(
                            f"Skipping invalid JSON at line "
                            f"{line_number}: {error}"
                        )

    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"HTTP error {error.code}: {error.reason}\n"
            f"URL: {url}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Network error: {error.reason}\n"
            f"Check your internet connection and URL."
        ) from error

    except (gzip.BadGzipFile, EOFError) as error:
        raise RuntimeError(
            f"The server response is not a valid complete gzip stream.\n"
            f"URL: {url}\n"
            f"Original error: {error}"
        ) from error


def safe_float(value):
    try:
        if value is None or str(value).strip() == "":
            return None

        cleaned = (
            str(value)
            .replace("$", "")
            .replace(",", "")
            .strip()
        )

        return float(cleaned)

    except (ValueError, TypeError):
        return None


def safe_int(value):
    try:
        return int(value) if value is not None else 0
    except (ValueError, TypeError):
        return 0


def save_jsonl(filepath, records):
    with open(filepath, "w", encoding="utf-8") as file:
        for record in records:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str
                ) + "\n"
            )


# ============================================================
# 3. EXTRACT REVIEWS
# ============================================================

print("=" * 65)
print(f"STEP 1: STREAMING {TARGET_REVIEWS} {CATEGORY} REVIEWS")
print("=" * 65)

raw_reviews = []
selected_product_ids = set()

review_stream = stream_jsonl_gz(
    REVIEWS_URL,
    "Reviews"
)

with tqdm(
    total=TARGET_REVIEWS,
    desc="Collecting reviews"
) as progress:

    for item in review_stream:

        review_text = item.get("text")
        parent_asin = item.get("parent_asin")

        if not review_text or not parent_asin:
            continue

        item["review_id"] = f"rev_{len(raw_reviews) + 1}"

        raw_reviews.append(item)
        selected_product_ids.add(parent_asin)

        progress.update(1)

        if len(raw_reviews) >= TARGET_REVIEWS:
            break


print("\nReview extraction completed.")
print(f"Total reviews collected: {len(raw_reviews)}")
print(f"Unique product IDs: {len(selected_product_ids)}")


if not raw_reviews:
    raise RuntimeError(
        "No reviews were collected. Check the dataset URL and response."
    )


# ============================================================
# 4. EXTRACT MATCHING PRODUCT METADATA
# ============================================================

print("\n" + "=" * 65)
print("STEP 2: MATCHING PRODUCT METADATA")
print("=" * 65)

raw_metadata = []
found_product_ids = set()

metadata_stream = stream_jsonl_gz(
    META_URL,
    "Metadata"
)

with tqdm(desc="Finding matching products") as progress:

    for item in metadata_stream:

        product_id = item.get("parent_asin")

        if (
            product_id in selected_product_ids
            and product_id not in found_product_ids
        ):

            raw_metadata.append(item)
            found_product_ids.add(product_id)

            progress.update(1)

        # Stop once all selected product IDs are matched.
        if len(found_product_ids) == len(selected_product_ids):
            break


missing_product_ids = (
    selected_product_ids - found_product_ids
)

print("\nMetadata matching completed.")
print(f"Matched products: {len(raw_metadata)}")
print(f"Unmatched product IDs: {len(missing_product_ids)}")


# ============================================================
# 5. EXPORT PRODUCT DATA FOR POSTGRESQL
# ============================================================

print("\n" + "=" * 65)
print("STEP 3: EXPORTING POSTGRESQL CSV FILES")
print("=" * 65)

pg_products = []

for product in raw_metadata:

    pg_products.append({

        "product_id": product.get("parent_asin"),

        "title": product.get("title"),

        "main_category": product.get("main_category"),

        "average_rating": safe_float(
            product.get("average_rating")
        ),

        "rating_number": safe_int(
            product.get("rating_number")
        ),

        "price": safe_float(
            product.get("price")
        ),

        "store": product.get("store")

    })


pg_reviews = []

for review in raw_reviews:

    pg_reviews.append({

        "review_id": review.get("review_id"),

        "product_id": review.get("parent_asin"),

        "user_id": review.get("user_id"),

        "rating": safe_float(
            review.get("rating")
        ),

        "title": review.get("title"),

        "text": review.get("text"),

        "timestamp": review.get("timestamp"),

        "verified_purchase": review.get(
            "verified_purchase"
        ),

        "helpful_vote": safe_int(
            review.get("helpful_vote")
        )

    })


products_csv = os.path.join(
    POSTGRES_DIR,
    "products_table.csv"
)

reviews_csv = os.path.join(
    POSTGRES_DIR,
    "reviews_table.csv"
)

pd.DataFrame(pg_products).to_csv(
    products_csv,
    index=False,
    encoding="utf-8-sig"
)

pd.DataFrame(pg_reviews).to_csv(
    reviews_csv,
    index=False,
    encoding="utf-8-sig"
)

print(f"Saved: {products_csv}")
print(f"Saved: {reviews_csv}")


# ============================================================
# 6. EXPORT PRODUCT DATA FOR MONGODB
# ============================================================

print("\n" + "=" * 65)
print("STEP 4: EXPORTING MONGODB JSONL FILES")
print("=" * 65)


product_details = []

for product in raw_metadata:

    product_details.append({

        "_id": product.get("parent_asin"),

        "product_id": product.get("parent_asin"),

        "title": product.get("title"),

        "features": product.get("features", []),

        "description": product.get("description", []),

        "details": product.get("details"),

        "images": product.get("images"),

        "videos": product.get("videos"),

        "categories": product.get("categories", []),

        "bought_together": product.get("bought_together")

    })


raw_review_documents = []

for review in raw_reviews:

    raw_review_documents.append({

        "_id": review.get("review_id"),

        "review_id": review.get("review_id"),

        "product_id": review.get("parent_asin"),

        "user_id": review.get("user_id"),

        "rating": review.get("rating"),

        "title": review.get("title"),

        "text": review.get("text"),

        "images": review.get("images", []),

        "timestamp": review.get("timestamp"),

        "verified_purchase": review.get("verified_purchase"),

        "helpful_vote": review.get("helpful_vote")

    })


product_jsonl = os.path.join(
    MONGO_DIR,
    "product_details_collection.jsonl"
)

reviews_jsonl = os.path.join(
    MONGO_DIR,
    "raw_reviews_collection.jsonl"
)

save_jsonl(product_jsonl, product_details)
save_jsonl(reviews_jsonl, raw_review_documents)

print(f"Saved: {product_jsonl}")
print(f"Saved: {reviews_jsonl}")


# ============================================================
# 7. FINAL SUMMARY
# ============================================================

print("\n" + "=" * 65)
print("DATASET GENERATION COMPLETED")
print("=" * 65)

print(f"Category: {CATEGORY}")
print(f"Reviews collected: {len(raw_reviews)}")
print(f"Products matched: {len(raw_metadata)}")
print(f"Unmatched products: {len(missing_product_ids)}")

print("\nPostgreSQL files:")
print(f"  {products_csv}")
print(f"  {reviews_csv}")

print("\nMongoDB files:")
print(f"  {product_jsonl}")
print(f"  {reviews_jsonl}")

print("\nAll exports are ready!")
