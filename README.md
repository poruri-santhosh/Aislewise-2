# Aislewise

**Product Intelligence & Shopper Navigation** is a retail review analytics project built with Flask, PostgreSQL, DuckDB, Streamlit, and scikit-learn. It combines a searchable product-review website with an analytics dashboard and an interactive in-store route planner.

[![Storefront on Vercel](https://img.shields.io/badge/Vercel-Storefront-black?style=for-the-badge&logo=vercel)](https://productreviewintelligence.vercel.app/)
[![Analytics on Streamlit](https://img.shields.io/badge/Streamlit-Analytics%20Dashboard-FF4B4B?style=for-the-badge&logo=streamlit)](https://aislewise-2-4iv34qn38dgv3q7npfggyv.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)

## Live applications

- **Storefront and shopper navigation:** [productreviewintelligence.vercel.app](https://productreviewintelligence.vercel.app/)
- **Analytics dashboard:** [Aislewise on Streamlit Community Cloud](https://aislewise-2-4iv34qn38dgv3q7npfggyv.streamlit.app/)

The website and dashboard are separate applications with separate data paths. The Flask website reads product reviews from PostgreSQL and can save shopper feedback after its database migration is applied. The Streamlit dashboard reads the DuckDB warehouse snapshot; refreshing the dashboard does not synchronize PostgreSQL.

## Features

### Product Intelligence

- Search, filter, sort, and paginate product reviews.
- View product and review summary metrics from PostgreSQL.
- Use the `/health`, `/api/summary`, and `/api/reviews` endpoints.
- Review shopper feedback and sentiment labels when the feedback table is available.

### Shopper Navigation

- Browse a small grocery catalogue with aisle and price details.
- Add products to a live cart.
- Plan a multi-stop route through the SVG store map using client-side A* pathfinding and a nearest-neighbor stop-order heuristic.
- Submit an in-store review after shopping. The Flask API validates the payload with Pandera, scores its text with the packaged scikit-learn pipeline, and stores it in PostgreSQL.

The frontend is plain HTML, CSS, and JavaScript. It has no React dependency or npm build step.

### Analytics dashboard

- Explore the Scenario A, B, and C analyses and their existing charts.
- Filter ML-scored reviews by confidence, product category, and price tier.
- Review model sentiment and confidence alongside product-level signals.
- Inspect investigation results and export supported dashboard data.

The Streamlit app uses DuckDB for analytics and the project’s MLflow sentiment-model workflow for scoring. The Flask deployment uses the exported `models/sentiment_pipeline.pkl` artifact through joblib, avoiding the need to ship the full MLflow stack in its serverless function.

## Architecture

```mermaid
flowchart LR
    shopper["Shopper / analyst"] --> browser["HTML, CSS, vanilla JavaScript"]
    browser -->|"Pages and JSON APIs"| flask["Flask app<br/>Vercel"]
    flask -->|"Read reviews; save feedback"| pg[("PostgreSQL")]
    flask -->|"Sentiment prediction"| model["scikit-learn pipeline<br/>models/sentiment_pipeline.pkl"]
    flask --> browser

    pg -->|"Scheduled / manual sync"| sync["incremental_sync.py"]
    sync --> warehouse[("warehouse.duckdb")]
    warehouse --> analysis["Scenario scripts and MLflow scoring"]
    analysis --> dashboard["Streamlit dashboard"]
    dashboard -->|"Read-only analytics queries"| warehouse

    source["Review dataset files"] --> ingestion["Dataset and ingestion scripts"]
    ingestion --> pg
```

### Data stores

| Store | Purpose | Used by |
|---|---|---|
| PostgreSQL | Product catalogue, product reviews, and (after migration) shopper feedback | Flask website and data-loading scripts |
| `warehouse.duckdb` | Analytics snapshot and scenario tables | Streamlit dashboard and analysis scripts |
| `aislewise_warehouse.duckdb` | Optional raw/Bronze ingestion exercises | DuckDB ingestion scripts |
| MLflow tracking data | Local model registry and scenario model workflows | Local analytics and dashboard workflows |

The PostgreSQL database and DuckDB files are not automatically synchronized. Refresh the warehouse through the data pipeline before expecting new PostgreSQL data to appear in the dashboard.

## Sentiment and scenario analysis

The repository includes an exported scikit-learn sentiment pipeline for the Flask feedback endpoint. The analytics workflows can load the registered `Aislewise_Sentiment_Model` through MLflow and score review text with predictions and confidence values.

Scenario flags are analytical signals for further inspection, not proof of product defects or seller misconduct. Review source data and relevant reviews before acting on a flagged result. Thresholds and available outputs are maintained by the scenario scripts and their prepared warehouse tables.

## Getting started locally

### Prerequisites

- Python 3.12 or newer.
- PostgreSQL for the Flask site and PostgreSQL data workflows.
- The repository’s `warehouse.duckdb` for the Streamlit dashboard.
- Docker Compose (optional).
- MongoDB only for optional MongoDB ingestion scripts.

### 1. Create a virtual environment

```powershell
git clone https://github.com/poruri-santhosh/Aislewise-2.git
cd Aislewise-2
python -m venv .venv
.venv\Scripts\Activate.ps1
```

On macOS or Linux, activate with:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

Install the Flask application dependencies:

```bash
python -m pip install -r requirements.txt
```

For analytics scripts, Streamlit, and tests:

```bash
python -m pip install -r requirements-analysis.txt -r requirements-dev.txt -r streamlit/requirements.txt
```

### 3. Configure PostgreSQL

Copy `.env.example` to `.env` and set your database URL:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
```

The application also accepts `NEON_DATABASE_URL` as a fallback. Keep real credentials in local or hosting-provider environment settings; never commit them.

### 4. Start the Flask website

```bash
python app.py
```

Open <http://127.0.0.1:5000>. Useful endpoints:

| Endpoint | Purpose |
|---|---|
| `/` | Product Intelligence and Shopper Navigation |
| `/health` | Check PostgreSQL connectivity |
| `/api/summary` | Review summary metrics |
| `/api/reviews?page=1&page_size=20` | Paginated product reviews |
| `/api/shopper-reviews` | Read submitted shopper feedback |

### 5. Enable shopper feedback storage

Before using shopper feedback, apply the idempotent migration to the PostgreSQL database configured for the app:

```text
migrations/001_create_shopper_feedback.sql
```

For example, run the SQL in your database provider’s SQL editor. The application database role needs permission to read and insert into `shopper_feedback`. Until the migration has been applied, shopper-feedback requests return an initialization error; product catalogue functionality is separate.

### 6. Start the Streamlit dashboard

From the repository root, open another terminal and run:

```bash
python -m streamlit run streamlit/app.py
```

The dashboard uses `warehouse.duckdb` by default. Override the location with `AISLEWISE_WAREHOUSE_PATH` if needed.

### Optional: run the dashboard with Docker

The Compose service starts Streamlit and mounts the DuckDB warehouse and scenario directories:

```powershell
docker compose up --build
```

Open <http://localhost:8501>. Stop it with `docker compose down`.

## Data and analysis workflows

These scripts can load, transform, or write data. Check their configuration and target database before running them.

```bash
# Generate sample CSV/JSONL files from the configured review dataset
python dataset_generation.py

# Load generated product/review data into PostgreSQL
python load_to_postgres.py

# Optional MongoDB load (inspect the script before using a non-disposable target)
python load_to_mongodb.py

# Optional raw/Bronze ingestion
python ingest_to_duckdb.py

# Sync PostgreSQL reviews to the DuckDB analytics warehouse
python incremental_sync.py

# Run analysis and scenario scripts
python run_analysis.py
python Scenario_A/scenario_a_trap_products.py
python Scenario_B/scenario_b_base_detection.py
python Scenario_B/scenario_b_deep_forensics.py
python Scenario_C/scenario_c_audit.py
```

Some scripts continuously poll for new records; stop them with `Ctrl+C`. Scenario scripts can update warehouse tables and overwrite their existing chart or report outputs.

## Deployment

### Flask website on Vercel

1. Import this GitHub repository into Vercel and keep the project root at the repository root.
2. Set `DATABASE_URL` (or `NEON_DATABASE_URL`) in the Vercel project environment.
3. Ensure the PostgreSQL schema, including `shopper_feedback`, is ready before enabling shopper feedback.
4. Deploy and verify `/`, `/health`, `/api/summary`, and `/api/reviews`.

The root `app.py` is the Flask entry point. `vercel.json` includes the templates and exported sentiment pipeline in the function bundle. The Vercel deployment does not run the Streamlit dashboard or use the local DuckDB warehouse.

### Streamlit Community Cloud

1. Connect the GitHub repository to Streamlit Community Cloud.
2. Select branch `main` and app file `streamlit/app.py`.
3. Make sure `warehouse.duckdb` is available to the deployment.
4. Deploy with the dependencies in `streamlit/requirements.txt`.

To publish refreshed analytics, update and validate the DuckDB snapshot, then commit the intended snapshot or provide it through your chosen deployment storage workflow. A dashboard rerun alone does not pull new PostgreSQL data.

## Tests

Install test and dashboard dependencies, then run:

```bash
python -m pip install -r requirements-dev.txt -r streamlit/requirements.txt
python -m pytest -q
```

Tests that require a live PostgreSQL database need the appropriate local environment variable. Avoid pointing tests at production unless they are explicitly designed to be read-only.

## Repository layout

```text
Aislewise/
├── api/                         # Vercel API entry point
├── migrations/                  # PostgreSQL migrations
├── models/                      # Exported sentiment pipeline
├── public/static/               # Storefront CSS and JavaScript
├── Scenario_A/                  # Scenario A analysis and charts
├── Scenario_B/                  # Scenario B analysis and charts
├── Scenario_C/                  # Scenario C analysis and charts
├── streamlit/                   # Analytics dashboard and dependencies
├── templates/                   # Flask HTML templates
├── tests/                       # Application and dashboard tests
├── app.py                       # Flask website and REST API
├── shopper_review_schema.py     # Pandera feedback validation
├── sentiment_service.py         # Sentiment inference helpers
├── warehouse.duckdb             # Dashboard analytics snapshot
├── requirements.txt             # Flask/Vercel dependencies
├── requirements-analysis.txt    # Data and analysis dependencies
└── README.md
```

## Operational and data-use notes

- The PostgreSQL site and DuckDB dashboard can show data from different refresh times.
- The analytics snapshot contains review data; verify dataset terms, privacy obligations, and repository visibility before publishing or redistributing it.
- The MongoDB loader and other ingestion scripts may modify or replace destination data. Inspect their behavior and back up important data first.
- Shopper names and feedback text may be displayed in the application after submission. Inform users and follow applicable privacy requirements.
- Model predictions and scenario flags can be wrong. Treat them as review leads, not verified claims.

## Author

**Poruri Jayakara Santhosh Vardhan** — AI/ML and full-stack engineering.
