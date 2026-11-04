
import os
import io
import csv
import pandas as pd
import psycopg2
from dotenv import load_dotenv


# ============================================================
# 1. CONFIGURATION
# ============================================================

# Load environment variables from .env
load_dotenv()

NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")

PRODUCTS_CSV = os.path.join(
    "data_postgresql",
    "products_table.csv"
)

REVIEWS_CSV = os.path.join(
    "data_postgresql",
    "reviews_table.csv"
)

BATCH_SIZE = 10000


# ============================================================
# 2. VALIDATE CONFIGURATION
# ============================================================

def validate_configuration():

    if not NEON_DATABASE_URL:
        raise ValueError(
            "NEON_DATABASE_URL not found. "
            "Check your .env file."
        )

    if not os.path.isfile(PRODUCTS_CSV):
        raise FileNotFoundError(
            f"Products CSV not found: {PRODUCTS_CSV}"
        )

    if not os.path.isfile(REVIEWS_CSV):
        raise FileNotFoundError(
            f"Reviews CSV not found: {REVIEWS_CSV}"
        )

    print("Configuration validated successfully.")


# ============================================================
# 3. DATABASE CONNECTION
# ============================================================

def connect_database():

    print("\nConnecting to Neon PostgreSQL...")

    conn = psycopg2.connect(
        NEON_DATABASE_URL,
        sslmode="require",
        connect_timeout=15
    )

    conn.autocommit = False

    print("Connected to Neon PostgreSQL successfully!")

    return conn


# ============================================================
# 4. CREATE DATABASE TABLES
# ============================================================

def create_tables(cursor):

    print("\nCreating database tables...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            title TEXT,
            main_category TEXT,
            average_rating NUMERIC(3,2),
            rating_number BIGINT,
            price NUMERIC(12,2),
            store TEXT
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            review_id TEXT PRIMARY KEY,
            product_id TEXT REFERENCES products(product_id),
            user_id TEXT,
            rating NUMERIC(2,1),
            title TEXT,
            text TEXT,
            timestamp BIGINT,
            verified_purchase BOOLEAN,
            helpful_vote INTEGER
        );
    """)

    print("Tables created or already exist.")


# ============================================================
# 5. GENERIC POSTGRESQL COPY FUNCTION
# ============================================================

def copy_from_dataframe(
    cursor,
    dataframe,
    table_name,
    columns
):
    """
    Bulk insert DataFrame records using PostgreSQL COPY.

    CSV format safely handles:
    - Commas
    - Quotes
    - Tabs
    - Newlines inside review text
    - NULL values
    """

    if dataframe.empty:
        return

    buffer = io.StringIO()

    dataframe[columns].to_csv(
        buffer,
        index=False,
        header=False,
        sep="\t",
        na_rep=r"\N",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n"
    )

    buffer.seek(0)

    column_names = ", ".join(
        f'"{column}"'
        for column in columns
    )

    copy_query = f"""
        COPY {table_name} ({column_names})
        FROM STDIN
        WITH (
            FORMAT CSV,
            DELIMITER E'\\t',
            NULL '\\N',
            QUOTE '"',
            ESCAPE '"'
        )
    """

    cursor.copy_expert(
        copy_query,
        buffer
    )


# ============================================================
# 6. LOAD PRODUCTS
# ============================================================

def load_products(cursor, conn):

    print("\n========== LOADING PRODUCTS ==========")

    product_columns = [
        "product_id",
        "title",
        "main_category",
        "average_rating",
        "rating_number",
        "price",
        "store"
    ]

    dataframe = pd.read_csv(PRODUCTS_CSV)

    missing_columns = set(product_columns) - set(dataframe.columns)

    if missing_columns:
        raise ValueError(
            f"Missing product CSV columns: {missing_columns}"
        )

    dataframe = dataframe[product_columns]

    # Remove duplicate product IDs
    dataframe = dataframe.drop_duplicates(
        subset=["product_id"],
        keep="first"
    )

    # Remove records without product IDs
    dataframe = dataframe.dropna(
        subset=["product_id"]
    )

    print(f"Products ready for import: {len(dataframe)}")

    copy_from_dataframe(
        cursor,
        dataframe,
        "products",
        product_columns
    )

    conn.commit()

    print("Products imported successfully!")


# ============================================================
# 7. LOAD REVIEWS IN BATCHES
# ============================================================

def load_reviews(cursor, conn):

    print("\n========== LOADING REVIEWS ==========")

    review_columns = [
        "review_id",
        "product_id",
        "user_id",
        "rating",
        "title",
        "text",
        "timestamp",
        "verified_purchase",
        "helpful_vote"
    ]

    total_inserted = 0

    # Read CSV in batches to reduce memory usage
    for batch_number, chunk in enumerate(
        pd.read_csv(
            REVIEWS_CSV,
            chunksize=BATCH_SIZE
        ),
        start=1
    ):

        missing_columns = (
            set(review_columns) - set(chunk.columns)
        )

        if missing_columns:
            raise ValueError(
                f"Missing review CSV columns: {missing_columns}"
            )

        chunk = chunk[review_columns]

        # Remove rows without review IDs
        chunk = chunk.dropna(
            subset=["review_id", "product_id"]
        )

        # Remove duplicates within this batch
        chunk = chunk.drop_duplicates(
            subset=["review_id"],
            keep="first"
        )

        copy_from_dataframe(
            cursor,
            chunk,
            "reviews",
            review_columns
        )

        conn.commit()

        total_inserted += len(chunk)

        print(
            f"Batch {batch_number}: "
            f"{len(chunk)} reviews imported. "
            f"Total: {total_inserted}"
        )

    print("\nReview import completed!")

    return total_inserted


# ============================================================
# 8. VERIFY DATABASE RECORDS
# ============================================================

def verify_database(cursor):

    print("\n========== DATABASE VERIFICATION ==========")

    cursor.execute("""
        SELECT COUNT(*)
        FROM products;
    """)

    product_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM reviews;
    """)

    review_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT product_id)
        FROM reviews;
    """)

    reviewed_products = cursor.fetchone()[0]

    cursor.execute("""
        SELECT
            product_id,
            title,
            average_rating
        FROM products
        LIMIT 5;
    """)

    sample_products = cursor.fetchall()

    print(f"\nTotal products: {product_count}")
    print(f"Total reviews: {review_count}")
    print(f"Products with reviews: {reviewed_products}")

    print("\nSample products:")

    for product in sample_products:
        print(product)

    print("\n============================================")


# ============================================================
# 9. MAIN EXECUTION
# ============================================================

def main():

    conn = None
    cursor = None

    try:

        # Validate files and environment variables
        validate_configuration()

        # Connect to Neon
        conn = connect_database()

        cursor = conn.cursor()

        # Create tables
        create_tables(cursor)
        conn.commit()

        # Import products first because reviews reference products
        load_products(cursor, conn)

        # Import reviews
        load_reviews(cursor, conn)

        # Verify imported data
        verify_database(cursor)

        print("\nSUCCESS: Aislewise PostgreSQL ingestion completed!")

    except Exception as error:

        if conn:
            conn.rollback()

        print("\nERROR: PostgreSQL ingestion failed.")
        print("Reason:", error)

        raise

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

        print("\nDatabase connection closed.")


# ============================================================
# 10. RUN SCRIPT
# ============================================================

if __name__ == "__main__":
    main()
