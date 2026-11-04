# Aislewise

**Product Review Intelligence** — a portfolio project for exploring customer feedback, finding gaps between star ratings and review sentiment, and inspecting product-level quality signals.

Aislewise has two deliberately separate user-facing applications:

- **Flask review website:** searches reviews and product metadata from PostgreSQL at request time.
- **Streamlit analytics dashboard:** explores prepared review and scenario tables in a local DuckDB warehouse snapshot.

The applications share the project’s review domain, but they do **not** share a live data connection. The Flask app queries PostgreSQL; the dashboard opens `warehouse.duckdb`. Dashboard refresh reruns queries against that DuckDB file—it does not synchronize PostgreSQL. This separation keeps the searchable website path independent from the analytics workflow and makes the checked-in snapshot usable without a database connection.

> **Data and privacy:** The analytics snapshot contains review text and reviewer identifiers. Before sharing or deploying this repository, confirm the source dataset’s terms, privacy obligations, and whether the committed snapshot is appropriate for the intended audience. Never commit database credentials or private environment files.

> **Scope:** Aislewise analyzes product reviews. It is not an online store and does not provide carts, wishlists, order management, checkout, or payment processing. Scenario classifications are investigative signals, not verified claims about products or sellers.

## At a glance

| Area | What it does | Data source |
|---|---|---|
| Review website | Search, filter, sort, and page through product reviews; display summary metrics | PostgreSQL (`products`, `reviews`) |
| Analytics dashboard | Explore rating/sentiment scenarios, inspect reviews by product ID, export the Scenario C list | `warehouse.duckdb` |
| Data generation | Stream a sample of UCSD Amazon Reviews 2023 data and match product metadata | Public compressed JSONL dataset |
| Sync and analysis | Add new PostgreSQL reviews to DuckDB, classify sentiment, and build product-level analysis tables | PostgreSQL → DuckDB |
| Optional Bronze ingestion | Copy PostgreSQL and MongoDB source data into raw DuckDB tables | PostgreSQL + MongoDB → `aislewise_warehouse.duckdb` |

## Features

### Flask review website

- Summary endpoint reports review count, reviewed product count, average rating, and verified-review count.
- Search across product IDs, product names, review titles, and review text.
- Filter by product ID, star rating, and verified-purchase status.
- Sort by newest, oldest, rating, or helpful votes.
- Paginate results in pages of 20, 50, or 100 reviews.
- Validate request values and use SQL parameters for user-provided search/filter values.
- Expose `/health`, `/api/summary`, and `/api/reviews` endpoints alongside the HTML page.

### Streamlit analytics dashboard

- Score warehouse reviews with the registered MLflow sentiment model and report processed-review totals, flagged-trap ratio, and average confidence.
- Filter results by minimum model confidence, price tier, and product category.
- Investigate **Scenario A: Rating traps**—high average star rating with a large share of negative review labels.
- Investigate **Scenario B: Hidden gems**—low average star rating with a large share of positive review labels.
- Investigate **Scenario C: Catalog lemons**—low average rating with a high share of negative review labels.
- View the existing scenario charts and the interactive vendor-notice index.
- Inspect a product’s classification and customer reviews by product ID.
- Download the Scenario C results as a CSV.

The dashboard reads DuckDB in read-only mode and scores reviews on demand with the registered model. Its optional 10-second rerun and manual refresh controls re-read the current local snapshot.

## System architecture

```mermaid
flowchart LR
    visitor["Visitor"] --> browser["Browser"]
    browser -->|HTML request| flask["Flask app<br/>app.py"]
    browser -->|JSON API request| flask
    flask -->|Read-only SQL<br/>DATABASE_URL| postgres[("PostgreSQL<br/>products + reviews")]
    flask -->|HTML / JSON| browser

    postgres -->|New review batches<br/>NEON_DATABASE_URL| sync["incremental_sync.py"]
    sync -->|Sentiment + aggregates| analytics[("warehouse.duckdb")]
    analytics --> dashboard["Streamlit dashboard<br/>streamlit/app.py"]
    dashboard -->|Read-only SQL| analytics

    source["UCSD Reviews 2023<br/>compressed JSONL"] --> generator["dataset_generation.py"]
    generator -->|CSV| pgload["load_to_postgres.py"]
    pgload --> postgres
    generator -->|JSONL| mongoload["load_to_mongodb.py<br/>(optional)"]
    mongoload --> mongo[("MongoDB<br/>(optional)")]
    postgres -.->|Raw source tables| bronze["ingest_to_duckdb.py<br/>(optional)"]
    mongo -.->|Raw product details| bronze
    bronze -.-> rawwarehouse[("aislewise_warehouse.duckdb<br/>Bronze only")]
```

### Two data paths, two deployment targets

| Path | Runtime behavior | Deployment |
|---|---|---|
| Website | Flask serves the product review catalogue and shopper feedback API; browser-only JavaScript plans in-store routes. | Vercel Python function from root `app.py`; configure PostgreSQL. |
| Dashboard | Streamlit reads the checked-in `warehouse.duckdb` file. No PostgreSQL connection is required to view that snapshot. | Streamlit Community Cloud; app file `streamlit/app.py`. |

`DATABASE_URL` is used by the website. `NEON_DATABASE_URL` is used by the PostgreSQL loader/sync and optional Bronze ingestion scripts. These are configuration names, not values to put in source control.

## Data pipeline

The main analytics path is an offline/periodic pipeline. The website can continue to serve PostgreSQL data independently of whether the analytics snapshot has been refreshed.

```mermaid
flowchart TD
    A["UCSD review + product metadata JSONL.GZ"] --> B["dataset_generation.py<br/>stream and select up to 50,000 reviews"]
    B --> C["Match product metadata<br/>to selected product IDs"]
    C --> D["PostgreSQL CSV files"]
    C --> E["MongoDB JSONL files<br/>(optional)"]
    D --> F["load_to_postgres.py<br/>products first, then reviews"]
    F --> G[("PostgreSQL source tables")]
    G --> H["incremental_sync.py<br/>read new timestamp batches"]
    H --> I["Rule-based sentiment label"]
    I --> J[("DuckDB Silver: silver_reviews")]
    J --> K["Product aggregates + A/B flags"]
    K --> L[("DuckDB Gold scenario tables")]
    L --> M["Analysis scripts + Streamlit dashboard"]
    M --> N["Tables, charts, reports, CSV exports"]
```

### Pipeline stages

1. **Generate sample inputs (optional).** `dataset_generation.py` streams the Appliances category review and metadata files from the UCSD Amazon Reviews 2023 dataset. It selects up to 50,000 reviews with text, finds matching products, and writes PostgreSQL CSVs and MongoDB JSONL files.
2. **Load PostgreSQL (optional).** `load_to_postgres.py` creates the `products` and `reviews` tables and loads products before reviews. Review product IDs reference product rows. Do not assume rerunning the import is an upsert or reset operation.
3. **Load MongoDB (optional).** `load_to_mongodb.py` loads product details and raw reviews. **Warning:** it drops its destination collections before loading; only use it with a disposable database or after backing up data.
4. **Sync analytics reviews.** `incremental_sync.py` polls PostgreSQL in batches and uses a timestamp checkpoint to insert new reviews into `silver_reviews`. Scenario analysis and the Streamlit dashboard use the registered MLflow sentiment model to score review text and calculate confidence.
5. **Run analysis and inspect results.** Scenario scripts and analysis/export scripts use the DuckDB warehouse to produce additional scenario tables, investigations, and outputs. The Streamlit dashboard queries the prepared tables.
6. **Optional Bronze copy.** `ingest_to_duckdb.py` copies raw PostgreSQL products/reviews and MongoDB product details into `aislewise_warehouse.duckdb`. This is a separate Bronze-ingestion database, not the dashboard warehouse, and it does not build the dashboard’s Silver/Gold tables.

### Analytics layers

- **Bronze (optional):** raw PostgreSQL and MongoDB data copied into `aislewise_warehouse.duckdb` for ingestion exercises.
- **Silver:** review records with normalized fields and a derived `sentiment` label in `warehouse.duckdb`.
- **Gold:** product-level summaries, discrepancy flags, and scenario-specific analysis tables consumed by the dashboard and reports.

The exact tables produced by analysis scripts can depend on which scripts have been run. The dashboard snapshot must contain the tables its panels query.

## Scenario rules and sentiment

The current rule thresholds are:

| Scenario | Investigative rule |
|---|---|
| **A — Rating traps** | Average product rating ≥ 4.0 and negative review share ≥ 35%. |
| **B — Hidden gems** | Average product rating ≤ 3.0 and positive review share ≥ 65%. |
| **C — Catalog lemons** | Average product rating ≤ 2.5 and negative review share ≥ 60%. |

`incremental_sync.py` currently stores its legacy sentiment label in `silver_reviews`. The scenario scripts and dashboard independently use `Aislewise_Sentiment_Model` and its prediction confidence for their ML-scored results. Model output remains an investigative signal—not a verified judgment of customer intent—so review the underlying text before making a business decision.

## Repository map

```text
Aislewise/
├── app.py                       # Flask website, PostgreSQL connection, and JSON API
├── shopper_review_schema.py     # Pandera contract for shopper feedback
├── migrations/
│   └── 001_create_shopper_feedback.sql
├── templates/
│   └── index.html               # Website HTML
├── public/
│   └── static/
│       ├── css/styles.css       # Responsive product and shopper styles
│       └── js/reviews.js        # Catalogue, cart, SVG map, and A* routing
├── streamlit/
│   ├── app.py                   # Streamlit review-analysis dashboard
│   └── requirements.txt         # Dashboard dependencies
├── .streamlit/
│   └── config.toml              # Shared Streamlit theme
├── tests/
│   ├── test_app.py              # Website and API tests
│   └── test_streamlit_app.py    # Dashboard startup test
├── Scenario_A/                  # Rating-trap investigations and supplier notices
├── Scenario_B/                  # Hidden-gem investigations
├── Scenario_C/                  # Poor-rating product audits
├── scripts/                     # Root-level investigation scripts
├── reports/                     # Generated root-level reports
├── visuals/                     # Generated root-level charts
├── warehouse.duckdb             # Dashboard's 50,000-review analytics snapshot
├── aislewise_warehouse.duckdb   # Local Bronze-ingestion database, if generated
├── dataset_generation.py        # Fetch reviews and matching product metadata
├── load_to_postgres.py          # Load generated CSVs into PostgreSQL
├── load_to_mongodb.py           # Optional MongoDB loader
├── ingest_to_duckdb.py          # Copy PostgreSQL/MongoDB data to Bronze tables
├── incremental_sync.py          # Sync PostgreSQL reviews to DuckDB and classify
├── run_analysis.py              # Portfolio summaries and overview chart
├── export_analysis.py           # Export selected summaries to CSV and JSON
├── organize_project.py          # Preview/apply root-level file organization
├── requirements.txt             # Flask, Pandera, scikit-learn, and model dependencies
├── requirements-analysis.txt    # Data and analysis dependencies
├── requirements-dev.txt         # Test dependencies
├── vercel.json                  # Vercel Flask function settings
└── README.md
```

## Getting started locally

### Requirements

- Python 3.10+ (CI currently tests with Python 3.12).
- PostgreSQL for the Flask website and PostgreSQL ingestion/sync scripts.
- `warehouse.duckdb` at the repository root for the dashboard. It is included in this repository’s snapshot workflow.
- MongoDB only if you intend to run the optional MongoDB load or Bronze-ingestion steps.

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/poruri-santhosh/Aislewise-2.git
cd Aislewise-2
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use `.venv\Scripts\python.exe` directly.

### 2. Install dependencies

For the Flask website:

```bash
python -m pip install -r requirements.txt
```

For analysis, dashboard, and tests:

```bash
python -m pip install -r requirements-analysis.txt -r requirements-dev.txt -r streamlit/requirements.txt
```

### 3. Configure PostgreSQL (website and data scripts)

Create a local `.env` file in the project root (do not commit it):

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
NEON_DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
```

Use the SSL-enabled URL supplied by your PostgreSQL provider. The website defaults to SSL for non-local hosts; `DATABASE_SSLMODE` can override that behavior. The website accepts `DATABASE_URL` or, as a fallback, `NEON_DATABASE_URL`. Never paste real credentials into this README, source code, or a public issue.

### 4. Start the website

```bash
python app.py
```

Open <http://127.0.0.1:5000>. Useful endpoints:

| URL | Purpose |
|---|---|
| `/` | Review search website |
| `/health` | Check PostgreSQL connectivity |
| `/api/summary` | Summary counts and average rating |
| `/api/reviews?page=1&page_size=20` | First review page |
| `/api/reviews?q=ice&rating=5` | Search text and filter to five stars |

The HTML can load while the database is unavailable; database-backed endpoints return an error until configuration and source tables are ready.

### 5. Start the dashboard

From the repository root, in another terminal:

```bash
python -m streamlit run streamlit/app.py
```

The dashboard opens in your browser and reads `warehouse.duckdb`. It does not need PostgreSQL to display the checked-in snapshot.

### Run the analytics dashboard with Docker

The Compose service runs the Streamlit entry point at `streamlit/app.py`. It mounts the local DuckDB warehouse, MLflow registry database/artifacts, and scenario folders into the container. Keep those data and model files available alongside `docker-compose.yml`.

```powershell
docker compose up --build
```

Open <http://localhost:8501>. To stop the service, run `docker compose down`. The Docker image excludes private environment files and local database/model artifacts; Compose supplies the warehouse and model mounts at runtime.

## Optional: create or refresh the data

Run data-loading steps only when you intend to create or change data. They are not required to run the website against an existing PostgreSQL database or view the existing dashboard snapshot.

```bash
# Generate CSV/JSONL inputs from the public dataset
python dataset_generation.py

# Load PostgreSQL products and reviews (verify target database first)
python load_to_postgres.py

# Optional MongoDB load (destination collections are dropped before import)
python load_to_mongodb.py

# Optional raw Bronze copy; needs PostgreSQL and MongoDB configuration
python ingest_to_duckdb.py

# Incrementally sync PostgreSQL reviews to warehouse.duckdb; runs continuously
python incremental_sync.py
```

`incremental_sync.py` polls every 10 seconds when no new rows are found. Stop it with `Ctrl+C` before copying or replacing `warehouse.duckdb`. Once its required DuckDB inputs exist, run the analysis scripts from the repository root:

```bash
python run_analysis.py
python scripts/deep_investigation_suite.py
python Scenario_A/scenario_a_trap_products.py
python Scenario_B/scenario_b_base_detection.py
python Scenario_B/scenario_b_deep_forensics.py
python Scenario_C/scenario_c_audit.py
python export_analysis.py
```

Scripts can update DuckDB tables and create reports/charts/exports. Check each script’s output and the generated files before publishing refreshed artifacts.

## Deployment

### Flask website on Vercel

Vercel serves the Flask website/API only; it does not host the Streamlit dashboard or read the local DuckDB snapshot for website requests.

The website includes two client-side modes. **Product Intelligence** keeps the PostgreSQL product-review catalogue and displays recent shopper feedback with its MLflow sentiment badge. **Shopper Navigation** uses a vanilla JavaScript cart, an SVG floorplan, A* routing, and a nearest-neighbor multi-stop heuristic. It does not need React, npm, or a frontend build step.

Shopper feedback is stored separately from product reviews because it rates the in-store trip rather than an individual product. Before accepting feedback, create the `shopper_feedback` table by running `migrations/001_create_shopper_feedback.sql` in the PostgreSQL database. The application database role needs `SELECT` and `INSERT` access to that table. The submission API validates non-empty customer name and review text, integer rating 1–5, and non-negative dwell time with Pandera before running model inference or inserting a row.

The Vercel submission endpoint loads the exported scikit-learn pipeline at `models/sentiment_pipeline.pkl` with joblib. This keeps inference available without packaging the large MLflow runtime into the serverless function. Refresh this artifact from the latest registered `Aislewise_Sentiment_Model` before deploying a newly trained version. The local `mlflow.db` and `mlruns/` directories are excluded from Git and Vercel uploads. If the PostgreSQL migration is missing, the feedback form shows an explicit error and does not report a successful save.

**Privacy:** submitted customer names and feedback text are visible in Product Intelligence. Make sure users are informed before they submit, and confirm the PostgreSQL, model-registry, and dataset access policies before publishing the site.

### 1. Push the project to GitHub

Create a GitHub repository for this project. A private repository is recommended because the DuckDB snapshot contains the full review records. Then, from the project root:

```powershell
git status --short
git remote add origin https://github.com/YOUR-USERNAME/Aislewise.git
git add .
git commit -m "Prepare Aislewise deployment"
git push -u origin main
```

If the project already has an `origin` remote, update it with `git remote set-url origin https://github.com/YOUR-USERNAME/Aislewise.git` instead of adding it again.

Before pushing, make sure `.env`, `.streamlit/secrets.toml`, `.vercel/`, `aislewise_warehouse.duckdb`, and generated CSV files are not tracked. `.env.example` contains placeholders only and is safe to share.

### 2. Import the repository in Vercel

1. In Vercel, choose **Add New → Project**.
2. Import the GitHub repository.
3. Keep the project root set to the repository root.
4. Add `DATABASE_URL` under the Vercel project's Environment Variables for the environments you want to deploy.
5. Use the SSL-enabled PostgreSQL URL. Do not add a connection URL to `vercel.json` or commit it to GitHub.
6. Deploy the project.

Vercel detects the root `app.py` as the Flask app. Templates are included in the serverless function and assets under `public/` are served statically. Configure `DATABASE_URL` (or `NEON_DATABASE_URL`) in Vercel project settings. Apply `migrations/001_create_shopper_feedback.sql` to that PostgreSQL database before shopper feedback can be listed or submitted. The sentiment pipeline artifact is bundled from `models/sentiment_pipeline.pkl`.

### 3. Verify the Vercel deployment

After deployment, visit:

- `/` to check the review website.
- `/health` to check the PostgreSQL connection.
- `/api/summary` to check live PostgreSQL totals.

The website uses serverless requests. It does not require the local DuckDB files.

### Streamlit Community Cloud

1. Connect the repository in Streamlit Community Cloud.
2. Select branch `main` and app file `streamlit/app.py`.
3. Deploy with `warehouse.duckdb` included in the repository.

The dashboard uses `streamlit/requirements.txt` and `.streamlit/config.toml`. Updating its data means refreshing the DuckDB snapshot, testing it, then committing and deploying that snapshot. A dashboard rerun alone does not fetch PostgreSQL data.

## Tests and continuous integration

GitHub Actions runs the test suite on pushes and pull requests using Python 3.12:

```bash
python -m pip install -r requirements-dev.txt -r streamlit/requirements.txt
python -m pytest -q
```

Tests cover the website, static assets, API behavior and filtering/pagination, Pandera validation and shopper submission behavior, invalid input and missing database configuration, and dashboard startup. Live PostgreSQL checks are skipped when the relevant database URL is not configured. Do not add production database credentials to CI unless you intentionally want tests to access that database.

## Operational notes and limitations

- PostgreSQL website data and the committed DuckDB dashboard snapshot can be at different points in time.
- The dashboard refresh controls re-query the local snapshot; they do not sync PostgreSQL into DuckDB.
- The incremental sync uses a timestamp checkpoint and is intended as a simple project pipeline, not a fully managed production CDC system.
- The sentiment classifier is a heuristic and scenario flags can be false positives or false negatives.
- Re-running the initial PostgreSQL import is not a general-purpose upsert/reset process; inspect the target before loading.
- The MongoDB loader drops target collections before import. Back up or use a disposable database.
- The optional Bronze database is distinct from the analytics warehouse used by Streamlit.
- Treat recommendations, supplier notices, and catalog lists as review leads that require human verification.

## License and dataset

Review the repository’s license and the UCSD Amazon Reviews 2023 dataset terms before reusing or redistributing the code or review data. The presence of data in this repository does not establish that it may be republished for every purpose.
