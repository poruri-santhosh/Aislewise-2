# Aislewise: Product Intelligence & Shopper Navigation Platform

[![Live Storefront](https://img.shields.io/badge/Vercel-Storefront%20%26%20Navigation-black?style=for-the-badge&logo=vercel)](https://productreviewintelligence.vercel.app/)
[![Live BI Dashboard](https://img.shields.io/badge/Streamlit-Analytics%20Dashboard-FF4B4B?style=for-the-badge&logo=streamlit)](https://aislewise-2-4iv34qn38dgv3q7npfggyv.streamlit.app/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Database Architecture](https://img.shields.io/badge/Architecture-PostgreSQL%20%7C%20DuckDB-orange?style=for-the-badge)](https://duckdb.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green?style=for-the-badge)](#license)

> **A dual-engine retail intelligence system uniting real-time customer in-store interactions with offline product review forensics.**  
> Aislewise pairs a zero-framework, client-side A* pathfinding grocery storefront with an OLAP-driven analytical engine for automated product quality triage, defect taxonomy classification, and review audit forensics.

---

## 📑 Table of Contents

- [1. Executive System Overview](#1-executive-system-overview)
- [2. Live Deployments & Endpoints](#2-live-deployments--endpoints)
- [3. System Architecture & High-Level Topology](#3-system-architecture--high-level-topology)
- [4. Dual-Engine Data Separation Architecture](#4-dual-engine-data-separation-architecture)
- [5. Schema Design Diagrams (OLTP vs OLAP)](#5-schema-design-diagrams-oltp-vs-olap)
  - [5.1 PostgreSQL (OLTP) Relational Data Model](#51-postgresql-oltp-relational-data-model)
  - [5.2 DuckDB Medallion Warehouse (OLAP) Gold Layer Schemas](#52-duckdb-medallion-warehouse-olap-gold-layer-schemas)
- [6. End-to-End Data Pipeline Flowchart](#6-end-to-end-data-pipeline-flowchart)
- [7. Machine Learning Sentiment & Inference Engine](#7-machine-learning-sentiment--inference-engine)
- [8. Smart Shopper Navigation & Pathfinding Architecture](#8-smart-shopper-navigation--pathfinding-architecture)
- [9. Master Discrepancy & Catalog Intelligence Report](#9-master-discrepancy--catalog-intelligence-report)
  - [9.1 Catalog Baseline Metrics](#91-catalog-baseline-metrics)
  - [9.2 Scenario A: Rating Traps Deep Forensic Analysis](#92-scenario-a-rating-traps-deep-forensic-analysis)
  - [9.3 Scenario B: Hidden Gems & Bayesian Recovery Roadmap](#93-scenario-b-hidden-gems--bayesian-recovery-roadmap)
  - [9.4 Scenario C: Catalog Lemons & Purge Quarantine](#94-scenario-c-catalog-lemons--purge-quarantine)
  - [9.5 Master Comparative Matrix (Scenario A vs B vs C)](#95-master-comparative-matrix-scenario-a-vs-b-vs-c)
- [10. Step-by-Step Local Development Setup](#10-step-by-step-local-development-setup)
- [11. Data Pipeline Execution Guide](#11-data-pipeline-execution-guide)
- [12. API Reference & Contract Specifications](#12-api-reference--contract-specifications)
- [13. Production Deployment Guide (Vercel + Streamlit)](#13-production-deployment-guide-vercel--streamlit)
- [14. Automated Testing Suite](#14-automated-testing-suite)
- [15. Operational Guardrails & Security Policies](#15-operational-guardrails--security-policies)
- [16. Repository Structure](#16-repository-structure)
- [17. Author & Acknowledgements](#17-author--acknowledgements)

---

## 1. Executive System Overview

Aislewise addresses two critical operational bottlenecks in modern retail grocery and e-commerce ecosystems:

1. **Rating-Review Sentiment Divergence:** Traditional 5-star rating mechanisms allow low-quality, defect-prone products to maintain deceptively high averages through historical volume inertia or review manipulation, misleading consumers and inflating return rates.
2. **In-Store Shopping Friction:** Physical store navigation lacks spatial awareness, causing unnecessary backtracking, lost dwell time, and checkout cart abandonment.

Aislewise solves both through an integrated dual-engine architecture:
- **Client Layer:** Zero-dependency vanilla HTML5/CSS/JavaScript with an in-browser SVG A* coordinate graph for dynamic multi-stop pathfinding and checkout telemetry capture.
- **Transactional Layer (OLTP):** Vercel Serverless Python Flask API streaming verified shopper feedback and telemetry into Neon Serverless PostgreSQL.
- **Analytical Layer (OLAP):** DuckDB Medallion warehouse executing vectorized columnar queries, scikit-learn NLP sentiment audits, and scenario anomaly classification for Executive BI reporting in Streamlit.

---

## 2. Live Deployments & Endpoints

| Component | Platform | URL | Purpose |
| :--- | :--- | :--- | :--- |
| **Storefront & Navigation** | Vercel Serverless | [productreviewintelligence.vercel.app](https://productreviewintelligence.vercel.app/) | Interactive retail storefront, dynamic A* pathfinding, and customer review ingestion |
| **Executive BI Forensics** | Streamlit Community Cloud | [aislewise-2-4iv34qn38dgv3q7npfggyv.streamlit.app](https://aislewise-2-4iv34qn38dgv3q7npfggyv.streamlit.app/) | Deep OLAP forensics, Scenario A/B/C filters, Bayesian recovery, defect Pareto distributions |
| **Source Repository** | GitHub | [github.com/poruri-santhosh/Aislewise-2](https://github.com/poruri-santhosh/Aislewise-2) | Canonical repository, migrations, ETL scripts, and analytical test suites |

---

## 3. System Architecture & High-Level Topology

```
+----------------------------------------------------------------------------------------------------+
|                                    AISLEWISE SYSTEM TOPOLOGY                                       |
+----------------------------------------------------------------------------------------------------+

       CLIENT LAYER                              APPLICATION ENGINE                        DATA STORAGE
       ============                              ==================                        ============

  +---------------------+                     +-----------------------+               +---------------------+
  |   In-Store Client   | === HTTP POST ====> |    Flask 3.1 REST     | === SQL ====> |   Neon Serverless   |
  | (A* Engine + SVG)   | <=== JSON/HTML ==== |  (Vercel Serverless)  |               |     PostgreSQL      |
  +---------------------+                     +-----------------------+               +---------------------+
             |                                            |                                      |
       Client Navigation                           Pandera Schema                                |
       Dwell & Cart Data                            Verification                                 |
             |                                            |                                 Batch Sync
             v                                            v                            (incremental_sync.py)
  +---------------------+                     +-----------------------+                          |
  |  Executive Analyst  | <== WebSocket ===== |    Streamlit Cloud    |                          v
  |  (Scenario Audits)  | === UI Events ====> |   Analytics Dashboard | <== Relational == +---------------------+
  +---------------------+                     +-----------------------+       Query   |   DuckDB Snapshot   |
                                                          |                           | (warehouse.duckdb)  |
                                                Joblib Native Pipeline                +---------------------+
                                                          |                                      ^
                                                          v                                      |
                                              +-----------------------+                          |
                                              | Scikit-Learn Pipeline | =========================+
                                              | (Inference & Scoring) |     Scenario Flags A, B, C
                                              +-----------------------+
```

### High-Level Component Interactions

```mermaid
flowchart TD
    subgraph ClientLayer ["Client & In-Store Experience"]
        Shopper["Shopper Browser / Mobile"]
        Analyst["Executive Analyst UI"]
    end

    subgraph StorefrontService ["Flask Web & REST Service (Vercel)"]
        FlaskAPI["Flask 3.1 Web Application"]
        PanderaValidator["Pandera Contract Validator"]
        JoblibInference["Lightweight Scikit-Learn Inference Engine"]
    end

    subgraph OLTP ["Transactional Store (OLTP)"]
        NeonPostgres[("Neon Serverless PostgreSQL")]
    end

    subgraph BatchETL ["ETL & Synchronization Layer"]
        SyncEngine["incremental_sync.py Orchestrator"]
    end

    subgraph OLAP ["Analytical Warehouse (OLAP)"]
        DuckDBWarehouse[("warehouse.duckdb (Medallion Gold)")]
        MLflowRegistry["MLflow Model Artifacts & Tracking"]
    end

    subgraph DashboardService ["Business Intelligence (Streamlit Cloud)"]
        StreamlitApp["Streamlit Forensics Dashboard"]
        ScenarioA["Scenario A: Trap Discovery"]
        ScenarioB["Scenario B: Gem Recovery"]
        ScenarioC["Scenario C: Lemon Purge"]
    end

    Shopper -->|Search & SVG Navigation| FlaskAPI
    Shopper -->|POST /api/shopper-reviews| PanderaValidator
    PanderaValidator --> JoblibInference
    JoblibInference -->|Write Review & Sentiment| NeonPostgres
    NeonPostgres -->|Change Data Extraction| SyncEngine
    SyncEngine -->|Columnar Transformation| DuckDBWarehouse
    MLflowRegistry -.->|Model Registry Calibration| DuckDBWarehouse
    DuckDBWarehouse --> StreamlitApp
    StreamlitApp --> ScenarioA
    StreamlitApp --> ScenarioB
    StreamlitApp --> ScenarioC
    Analyst --> StreamlitApp
```

---

## 4. Dual-Engine Data Separation Architecture

A fundamental architectural principle of Aislewise is the **strict isolation of OLTP (Online Transaction Processing) from OLAP (Online Analytical Processing)**:

```
[Storefront Shoppers]                   [Executive BI Analysts]
         │                                         │
         ▼                                         ▼
┌───────────────────┐                     ┌───────────────────┐
│ Neon PostgreSQL   │                     │  DuckDB Warehouse │
│ (Transactional)   │                     │  (Columnar OLAP)  │
└─────────┬─────────┘                     └─────────▲─────────┘
          │                                         │
          │         ┌─────────────────────┐         │
          └────────►│ incremental_sync.py ├─────────┘
                    │ Batch Synchronizer  │
                    └─────────────────────┘
```

> ⚠️ **Key Operational Rule:**  
> Writes to the PostgreSQL database (such as user-submitted reviews, feedback ratings, and cart dwell telemetry) do **not** automatically trigger recalculations in DuckDB. Analytical snapshots are refreshed deterministically via `incremental_sync.py` and downstream scenario modules to preserve sub-millisecond query performance for analytics without imposing write lock contention on production checkout paths.

---

## 5. Schema Design Diagrams (OLTP vs OLAP)

### 5.1 PostgreSQL (OLTP) Relational Data Model

Neon Serverless PostgreSQL manages the canonical operational state, enforced via declarative SQL migrations:

```mermaid
erDiagram
    PRODUCTS ||--o{ REVIEWS : "receives"
    PRODUCTS ||--o{ SHOPPER_FEEDBACK : "collects"
    
    PRODUCTS {
        varchar(64) asin PK "Amazon Standard Identification Number"
        text title "Catalog item description"
        varchar(64) category "Department category"
        decimal price "Current retail listing price"
        decimal average_rating "Marketplace rolling average star score"
        integer rating_number "Cumulative customer review count"
        timestamp updated_at "Row modification timestamp"
    }

    REVIEWS {
        varchar(64) review_id PK "Unique hash identifier"
        varchar(64) asin FK "Associated product key"
        decimal rating "Customer assigned star score (1.0 - 5.0)"
        text title "Review headline"
        text text "Review narrative body text"
        boolean verified_purchase "Anti-sabotage purchase flag"
        integer helpful_vote "Upvote agreement count"
        timestamp review_timestamp "Review publication datetime"
    }

    SHOPPER_FEEDBACK {
        serial id PK "Surrogate autoincrementing ID"
        varchar(64) asin FK "Product reference identifier"
        integer rating "Shopper rating score (1 to 5)"
        text review_text "Submitted shopper feedback string"
        varchar(32) sentiment_label "Model prediction (POSITIVE / NEGATIVE)"
        decimal sentiment_confidence "Classification probability score"
        integer dwell_time_seconds "Physical aisle dwell duration"
        boolean added_to_cart "In-store cart conversion flag"
        timestamp created_at "Telemetry submission timestamp"
    }
```

### 5.2 DuckDB Medallion Warehouse (OLAP) Gold Layer Schemas

DuckDB organizes processed analytical intelligence into specialized read-optimized Gold tables:

```mermaid
classDiagram
    class GoldProductDiscrepancyFlags {
        +VARCHAR asin [PK]
        +VARCHAR title
        +FLOAT marketplace_rating
        +INTEGER total_reviews
        +FLOAT positive_sentiment_share
        +FLOAT negative_sentiment_share
        +VARCHAR scenario_classification ("TRAP"|"GEM"|"LEMON"|"NOMINAL")
        +FLOAT discrepancy_magnitude
    }

    class GoldScenarioARootCauses {
        +VARCHAR asin [FK]
        +VARCHAR defect_category ("CORE_DEFECT"|"FITMENT_FLAW"|"LOGISTICS")
        +INTEGER complaint_count
        +FLOAT percentage_share
        +VARCHAR sample_customer_quote
        +BOOLEAN verified_buyer_majority
    }

    class GoldScenarioAImpactRanking {
        +VARCHAR asin [FK]
        +INTEGER helpful_votes_aggregate
        +INTEGER total_negative_reviews
        +FLOAT weighted_dissatisfaction_score
        +INTEGER quarantine_priority_tier
        +BOOLEAN vendor_notice_issued
    }

    class GoldScenarioBRecoveryPlan {
        +VARCHAR asin [FK]
        +FLOAT current_display_rating
        +INTEGER current_review_count
        +INTEGER reviews_needed_for_4_stars
        +VARCHAR recovery_feasibility ("EASY"|"MEDIUM"|"HARD")
        +VARCHAR primary_suppression_cause
    }

    class GoldScenarioCCatalogPurge {
        +VARCHAR asin [FK]
        +FLOAT contradiction_factor
        +FLOAT negative_review_share
        +VARCHAR purge_recommendation ("BUYBOX_DEACTIVATE"|"INDEX_EXCLUDE")
        +TIMESTAMP flag_timestamp
    }

    GoldProductDiscrepancyFlags <|-- GoldScenarioARootCauses : filters
    GoldProductDiscrepancyFlags <|-- GoldScenarioAImpactRanking : ranks
    GoldProductDiscrepancyFlags <|-- GoldScenarioBRecoveryPlan : targets
    GoldProductDiscrepancyFlags <|-- GoldScenarioCCatalogPurge : isolates
```

---

## 6. End-to-End Data Pipeline Flowchart

The data pipeline transitions raw product reviews into prioritized operational interventions:

```mermaid
flowchart TD
    subgraph S1 ["Stage 1: Ingestion & Validation"]
        InRaw["Amazon Appliances Review Corpus (50,000 Records)"]
        InStore["In-Store Shopper Live Feedback"]
        PanderaContract["Pandera Schema Validation\n(shopper_review_schema.py)"]
        PostgresOLTP[("Neon PostgreSQL DB\n(shopper_feedback, products, reviews)")]
    end

    subgraph S2 ["Stage 2: ETL & Convergence"]
        SyncScript["incremental_sync.py\n(CDC & Upsert Engine)"]
        DuckDBRaw[("aislewise_warehouse.duckdb\n(Bronze Ingestion Store)")]
        DuckDBWarehouse[("warehouse.duckdb\n(Silver & Gold Layer)")]
    end

    subgraph S3 ["Stage 3: Machine Learning & Forensics"]
        ScikitPipeline["Sentiment Pipeline\n(sentiment_service.py)"]
        ScenarioA["Scenario A Engine:\nTrap Discovery & Defect NLP"]
        ScenarioB["Scenario B Engine:\nSample Truncation & Bayesian Recovery"]
        ScenarioC["Scenario C Engine:\nCatalog Lemon & Alignment Purge"]
    end

    subgraph S4 ["Stage 4: Operational Action & BI Surfacing"]
        StreamlitBI["Streamlit BI Dashboard\n(Executive KPI Reports)"]
        VendorNotices["Automated Vendor Corrective Action Notices\n(VENDOR_NOTICE_*.txt)"]
        StoreNavigation["A* Pathfinding Storefront App\n(Real-Time Wayfinding)"]
    end

    InRaw --> PostgresOLTP
    InStore --> PanderaContract --> PostgresOLTP
    PostgresOLTP --> SyncScript
    SyncScript --> DuckDBRaw --> DuckDBWarehouse
    DuckDBWarehouse --> ScikitPipeline
    ScikitPipeline --> ScenarioA
    ScikitPipeline --> ScenarioB
    ScikitPipeline --> ScenarioC
    ScenarioA --> DuckDBWarehouse
    ScenarioB --> DuckDBWarehouse
    ScenarioC --> DuckDBWarehouse
    DuckDBWarehouse --> StreamlitBI
    ScenarioA --> VendorNotices
    PostgresOLTP --> StoreNavigation
```

---

## 7. Machine Learning Sentiment & Inference Engine

### Model Pipeline Architecture

Aislewise leverages a serialized scikit-learn pipeline deployed with native Python `joblib` deserialization:

```mermaid
flowchart LR
    A["Raw Customer Review Body"] --> B["Regex Cleaner & Lowercase Normalizer"]
    B --> C["TF-IDF Vectorizer\n(Sublinear TF, N-Gram Range 1-2)"]
    C --> D["Calibrated Linear Classifier\n(Logistic Regression with L2 Regularization)"]
    D --> E["Polarity Output\n(POSITIVE / NEGATIVE)"]
    D --> F["Predictive Confidence Score\n(Softmax Probability \in [0.0, 1.0])"]
```

### Serverless Optimization
- **Zero Heavy MLflow Runtime on Vercel:** While MLflow coordinates training, parameter tuning, and model registries offline, production Vercel inference uses a stripped `models/sentiment_pipeline.pkl` (~4.8 MB), keeping cold-start times under 180ms.
- **Out-of-Vocabulary (OOV) Guardrails:** If review text contains non-standard characters, emojis, or insufficient token density, the system triggers a fallback heuristic grounded in verified star rating bounds ($Rating \ge 4 \implies POSITIVE, \le 2 \implies NEGATIVE$).

---

## 8. Smart Shopper Navigation & Pathfinding Architecture

Aislewise incorporates a zero-build client-side grocery wayfinding engine built directly with SVG coordinate grids and vanilla JavaScript:

```
+----------------------------------------------------------------------------------------------------+
|                                 STORE NAVIGATION TOPOLOGY & WAYFINDING                             |
+----------------------------------------------------------------------------------------------------+

     [ENTRANCE] (Node 0,0)
         |
         v
    [AISLE 1: Produce] ---------> [AISLE 2: Bakery] ---------> [AISLE 3: Dairy]
         |                                |                               |
         |    (Nearest-Neighbor)          |    (A* Pathfinding)           |
         +------------------------------> [CART ITEM #1]                  |
                                                  |                       |
                                                  v                       v
    [AISLE 6: Frozen] <---------- [AISLE 5: Meats] <---------- [AISLE 4: Pantry]
         |
         v
    [CHECKOUT LANES] (Node 10,10)
```

```mermaid
sequenceDiagram
    autonumber
    actor Shopper
    participant UI as SVG Storefront UI
    participant NN as Nearest-Neighbor Engine
    participant AStar as A* Graph Pathfinding
    participant Telemetry as Telemetry Tracker

    Shopper->>UI: Selects 5 Cart Items across Aisles
    UI->>NN: Submits Cartesian Coordinates of Target Shelves
    Note over NN: Computes Traveling Salesperson (TSP) heuristic<br/>orders stops to minimize total Euclidean distance
    NN-->>UI: Returns Ordered Stop Sequence [Stop 1, Stop 2... Stop 5]
    loop For each adjacent stop in sequence
        UI->>AStar: Compute shortest traversal avoiding aisle racks
        Note over AStar: f(n) = g(n) + h(n)<br/>Heuristic h(n) = Manhattan distance to next shelf
        AStar-->>UI: Returns Polyline Waypoints [(x1,y1), (x2,y2)...]
    end
    UI->>Shopper: Renders animated SVG route overlay
    Shopper->>Telemetry: Dwell Time & Cart Item Collection Events
    Telemetry->>UI: Triggers POST /api/shopper-reviews with Telemetry payload
```

---

## 9. Master Discrepancy & Catalog Intelligence Report

*Domain: Amazon Appliances Catalog (Audited Medallion DuckDB Gold Layer)*

### 9.1 Catalog Baseline Metrics

| Metric Dimension | Quantified Value | Operational Context |
| :--- | :--- | :--- |
| **Total Ingested Reviews** | **50,000** | Amazon Appliances Historical Review Corpus |
| **Total Unique Matched Products** | **15,641 SKUs** | Distinct catalog ASIN / Parent ASIN records |
| **Average Global Star Rating** | **4.21 / 5.00** | Inflated marketplace display baseline |
| **Scenario A (Rating Traps)** | **440 SKUs (2.81%)** | Public Stars $\ge 4.0$ yet Negative Sentiment Share $\ge 35\%$ |
| **Scenario B (Hidden Gems)** | **174 SKUs (1.11%)** | Public Stars $\le 3.0$ yet Positive Sentiment Share $\ge 65\%$ |
| **Scenario C (Catalog Lemons)** | **1,481 SKUs (9.47%)** | Public Stars $\le 2.5$ and Negative Sentiment Share $\ge 60\%$ |
| **Aligned / Nominal Catalog** | **13,546 SKUs (86.61%)** | Standard parity between rating and review polarity |

```
                       CATALOG SEGMENTATION BREAKDOWN
                       ==============================
                       
    [Nominal / Aligned Products]  ████████████████████████████████ 86.61% (13,546 SKUs)
    [Scenario C: Catalog Lemons]   ███▌ 9.47% (1,481 SKUs)
    [Scenario A: Rating Traps]     █ 2.81% (440 SKUs)
    [Scenario B: Hidden Gems]      ▌ 1.11% (174 SKUs)
```

---

### 9.2 Scenario A: Rating Traps Deep Forensic Analysis

*Definition: Deceptively High Display Rating ($\ge 4.0\star$) masking severe negative feedback ($\ge 35\%$ Negative Sentiment).*

#### The Two Anomaly Sub-Cohorts
1. **Severe Traps ($\ge 50\%$ Negative Share):** **162 Products** — Acute deception risk; immediately scheduled for quarantine.
2. **Moderate Traps ($35\% - 49.9\%$ Negative Share):** **278 Products** — Progressive quality decay.

#### Root-Cause Defect Taxonomy (497 Verified Negative Reviews Audited)
A critical audit was conducted to differentiate between third-party logistics transit damage and actual manufacturing failure:

```
                           ROOT CAUSE DEFECT PARETO
                           ========================

  Core Product Defect        [██████████████████████████████] 48.89% (243 complaints)
  Size & Fitment Flaws       [██████████████] 23.54% (117 complaints)
  General Material Quality   [████████████] 20.72% (103 complaints)
  Carrier Shipping Failures  [███] 5.23% (26 complaints)
  Packaging Seal Failures    [█] 1.61% (8 complaints)
```

$$\text{Combined Manufacturing \& Specification Flaws} = 48.89\% + 23.54\% = \mathbf{72.43\%}$$

> 💡 **Forensic Finding:** Less than 6% of negative feedback is attributable to shipping logistics. Nearly three-quarters (72.43%) of all negative sentiment stems from manufacturing defects, component fatigue, or incorrect dimension specifications.

#### Buyer Verification & Anti-Sabotage Validation
* **Verified Purchase Ratio:** **67.3% (694 reviews)** across inspected trap SKUs.
* **Audit Takeaway:** The negative sentiment is **not** competitor review bombing; it originates from real paying customers who attempted appliance installation.

#### Historical Quality Decay (2015 – 2023)
Tracking historical negative sentiment share reveals that high average ratings are relics of ancient volume, masking severe recent manufacturing decay:

```
  Cohort Year   Negative Share (%)   Operational Status
  --------------------------------------------------------------------------
  2015–2017     63.0%                Stable baseline failure rate
  2018          55.7%                Optimal quality control
  2019          63.5%                Pre-pandemic variance
  2020          69.5%                Supply-chain material substitution phase
  2022          75.8% (PEAK)         Critical manufacturing failure
```

#### Appliance Category Risk Distribution
1. **Refrigerator & Ice Maker Components:** **27.6%**
2. **Washing Machine Parts:** **22.9%**
3. **Appliance Accessories & Adapters:** **18.7%**
4. **Dryer Rollers & Thermal Fuses:** **17.5%**
5. **Oven & Stove Burners:** **13.1%**
6. **Dishwasher Pumps:** **0.2%**

#### Social Proof Multiplier
Single negative reviews with high social agreement drastically amplify customer churn:
* **Product `B07JJQR94P` (⭐ 4.0 Display):** Contained a single 1-star warning with **74 Helpful Upvotes**, exposing a burning terminal harness defect.
* **Remediation Executed:** Automated Vendor Action Notices (`VENDOR_NOTICE_[ASIN].txt`) dispatched demanding a mandatory 14-day Corrective Action Plan.

---

### 9.3 Scenario B: Hidden Gems & Bayesian Recovery Roadmap

*Definition: Display Star Rating is Artificially Low ($\le 3.0\star$) despite overwhelming customer praise ($\ge 65\%$ Positive Sentiment).*

#### Diagnostic Results (174 Products Evaluated)
* **Average Display Rating:** ⭐ **2.98 / 5.00**
* **Average Positive Review Share:** 🟢 **88.4%**

| Forensic Verdict | Product Count | Share (%) | Mean Reviews | Root Cause Explanation |
| :--- | :--- | :--- | :--- | :--- |
| **Sample Size Truncation** | **172** | **98.85%** | **1.2** | Low review volume ($N \in [1, 3]$). A single outlier 1-star review mathematically collapses the mean. |
| **Suspected Review Bombing** | **1** | **0.57%** | **3.0** | Unverified account (`Verified=False`) posted a malicious 1-star review overriding verified 5-stars. |
| **Polarized Opinions** | **1** | **0.57%** | **4.0** | Extreme bi-modal distribution (1-star vs 5-stars, rating variance $\ge 2.0$). |

#### Bayesian Star Recovery Mathematics
To compute the exact number of consecutive 5-star reviews ($X$) needed to restore an underrated product's display rating to the discovery threshold of $\ge 4.0\star$:

$$X = \left\lceil \frac{4.0 \cdot N - \sum_{i=1}^{N} R_i}{5.0 - 4.0} \right\rceil = \left\lceil 4.0 \cdot N - \sum_{i=1}^{N} R_i \right\rceil$$

```
                        RECOVERY EFFORT DISTRIBUTION
                        ============================
                        
    EASY (< 3 Reviews Needed)       [██████████████████████████████] 96.5% (168 SKUs)
    MEDIUM (3 - 5 Reviews Needed)   [█] 2.9% (5 SKUs)
    HARD (> 5 Reviews Needed)       [ ] 0.6% (1 SKU)
```

* **Immediate High-Value Targets:**
  * Products `B095RGB1WT` and `B09PL5HHQJ` require **only 1 additional 5-star review** to cross into $\ge 4.0\star$ visibility.
  * Products `B01DKC2GQ0`, `B00Q9EJ45S`, and `B0C8TR1SWY` require **only 2 additional 5-star reviews**.
* **Merchandising Action:** Deploy automated post-purchase review request sequences to buyers of these 174 high-quality SKUs to eliminate sample truncation without product redesigns.

---

### 9.4 Scenario C: Catalog Lemons & Purge Quarantine

*Definition: Confirmed Failures where both public rating and text feedback are severely negative ($\text{Stars} \le 2.5$ and $\text{Negative Sentiment} \ge 60\%$).*

* **Total Confirmed Lemons:** **1,481 Products (9.47% of analyzed catalog)**
* **Average Display Score:** ⭐ **1.31 / 5.00**
* **Average Negative Review Share:** 🔴 **99.1%**
* **Contradiction Factor:** **0.0%** (Absolute consensus between star rating and customer dissatisfaction).

#### Critical Complaint Audit Examples
* **`B07QQDZQ66` (Refrigerator - 65 Upvotes):** *"I hate almost every feature of the refrigerator... bought through local big box store... complete disaster."*
* **`B001GPUH5G` (Appliance Part - 65 Upvotes):** *"This item is a con job, akin to fuel line magnets... does not perform as advertised."*
* **`B07KYCPLS5` (Mini Fridge - 60 Upvotes):** *"NO CUSTOMER SERVICE. Worked 2 months, then frosted up and ruined contents."*

#### Operational Remediation
- Immediate Buy-Box deactivation across all 1,481 SKUs.
- Suppression from in-store grocery pathfinding search indices.
- Vendor account warning dispatched to prevent repeat catalog re-listing.

---

### 9.5 Master Comparative Matrix (Scenario A vs B vs C)

| Analytical Dimension | Scenario A (Rating Traps) | Scenario B (Hidden Gems) | Scenario C (Catalog Lemons) |
| :--- | :--- | :--- | :--- |
| **Marketplace Stars** | High ($\ge 4.0\star$) | Low ($\le 3.0\star$) | Low ($\le 2.5\star$) |
| **Review Text Sentiment** | Highly Negative ($\ge 35\%$) | Overwhelmingly Positive ($\ge 65\%$) | Consistently Negative ($\ge 60\%$) |
| **Identified SKUs** | **440 (2.81%)** | **174 (1.11%)** | **1,481 (9.47%)** |
| **Average Display Rating** | **4.24 / 5.00** | **2.98 / 5.00** | **1.31 / 5.00** |
| **Discrepancy Nature** | Concealed Product Quality Decay | Sample Size Truncation Variance | Zero Discrepancy (Confirmed Broken) |
| **Primary Root Cause** | Mechanical Defect (48.9%) & Fit (23.5%) | Review volume scarcity ($N \le 3$) | Critical engineering failure & zero support |
| **Social Proof Risk** | High (Single warning up to 74 upvotes) | High (Buried 5-star verified praise) | Extreme (Fraud warnings up to 65 upvotes) |
| **Executive Action** | Vendor Notice Memo & Quarantine | Review Acceleration Campaigns | Permanent Catalog Purge & Index Deletion |

---

## 10. Step-by-Step Local Development Setup

### System Prerequisites
Ensure you have installed:
- **Python:** Version 3.12 or newer (`python --version`)
- **PostgreSQL Database:** Accessible local instance or Neon Serverless PostgreSQL connection URL
- **Git:** Version control client
- **Node.js & npm:** (Optional, only if modifying local build configurations)
- **Docker & Docker Compose:** (Optional, for containerized execution)

---

### Step 1: Clone Repository & Isolate Environment

```bash
# 1. Clone the canonical repository
git clone https://github.com/poruri-santhosh/Aislewise-2.git
cd Aislewise-2

# 2. Create isolated Python 3.12 virtual environment
python -m venv .venv

# 3. Activate virtual environment
# On Linux / macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Windows (Command Prompt):
.venv\Scripts\activate.bat
```

---

### Step 2: Install Dependency Tiers

```bash
# 1. Upgrade pip, wheel, and setuptools
python -m pip install --upgrade pip setuptools wheel

# 2. Install base web runtime requirements (Flask, Pandera, Joblib, psycopg2)
python -m pip install -r requirements.txt

# 3. Install analytical, test, and Streamlit dependencies
python -m pip install -r requirements-analysis.txt -r requirements-dev.txt -r streamlit/requirements.txt
```

---

### Step 3: Configure Environment Credentials

Create a `.env` file in the repository root:

```bash
cp .env.example .env
```

Edit `.env` with your database credentials:

```dotenv
# Neon Serverless PostgreSQL Connection String
DATABASE_URL="postgresql://user:password@ep-sample-host.region.neon.tech/aislewise?sslmode=require"

# Fallback alias supported by Flask API
NEON_DATABASE_URL="postgresql://user:password@ep-sample-host.region.neon.tech/aislewise?sslmode=require"

# Optional: Path override for local DuckDB OLAP snapshot
AISLEWISE_WAREHOUSE_PATH="warehouse.duckdb"

# Server configuration
FLASK_ENV="development"
FLASK_PORT=5000
```

---

### Step 4: Execute Database DDL Migrations

Initialize the required `shopper_feedback` schema in PostgreSQL:

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv

load_dotenv()
conn_str = os.getenv('DATABASE_URL') or os.getenv('NEON_DATABASE_URL')
if not conn_str:
    raise ValueError('Missing DATABASE_URL in environment!')

with psycopg2.connect(conn_str) as conn:
    with conn.cursor() as cur:
        with open('migrations/001_create_shopper_feedback.sql', 'r') as f:
            cur.execute(f.read())
        conn.commit()
print(' [OK] PostgreSQL migration applied successfully.')
"
```

---

### Step 5: Start the Development Servers

#### Terminal A: Flask Web & Storefront REST API
```bash
python app.py
```
- Storefront UI: [http://127.0.0.1:5000](http://127.0.0.1:5000)
- Health Check: [http://127.0.0.1:5000/health](http://127.0.0.1:5000/health)

#### Terminal B: Streamlit BI Analytics Dashboard
```bash
python -m streamlit run streamlit/app.py
```
- Executive BI Dashboard: [http://localhost:8501](http://localhost:8501)

#### Optional: Containerized Execution with Docker Compose
```bash
docker compose up --build
```

---

## 11. Data Pipeline Execution Guide

Run the pipeline steps in chronological order to generate data, load stores, sync DuckDB, and execute analytical forensic scenarios:

```
+---------------------------------------------------------------------------------------------------+
|                                  DATA PIPELINE EXECUTION SEQUENCE                                 |
+---------------------------------------------------------------------------------------------------+

 1. GENERATE DATASETS           2. INGEST TO STORES             3. BATCH SYNCHRONIZATION
    python dataset_generation.py   python load_to_postgres.py      python incremental_sync.py
                                   python ingest_to_duckdb.py
                                            │                                │
                                            v                                v
                                   [Neon PostgreSQL]                [DuckDB warehouse]
                                                                             │
 4. FORENSIC SCENARIOS                      ◄────────────────────────────────┘
    python Scenario_A/scenario_a_trap_products.py
    python Scenario_B/scenario_b_base_detection.py
    python Scenario_B/scenario_b_deep_forensics.py
    python Scenario_C/scenario_c_audit.py
```

### Detailed Command Execution

```bash
# Step 1: Generate sample synthetic review & catalog records
python dataset_generation.py

# Step 2: Load products and historical reviews into Neon PostgreSQL
python load_to_postgres.py

# Step 3: Populate raw/Bronze ingestion tables in DuckDB
python ingest_to_duckdb.py

# Step 4: Run incremental CDC synchronization from PostgreSQL to DuckDB
# Note: Press Ctrl+C once synchronization passes complete
python incremental_sync.py

# Step 5: Execute Scenario A (Rating Trap Discovery & Defect Root Causes)
python Scenario_A/scenario_a_trap_products.py

# Step 6: Execute Scenario B (Base Detection & Deep Forensics on Underrated Gems)
python Scenario_B/scenario_b_base_detection.py
python Scenario_B/scenario_b_deep_forensics.py

# Step 7: Execute Scenario C (Catalog Lemons Semantic Audit & Purge Flags)
python Scenario_C/scenario_c_audit.py
```

---

## 12. API Reference & Contract Specifications

### 1. Health Status Check
- **Endpoint:** `GET /health`
- **Description:** Verifies database connectivity and serverless latency.
- **Response `200 OK`:**
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-11-04T14:54:14Z"
}
```

---

### 2. Catalog Metrics Summary
- **Endpoint:** `GET /api/summary`
- **Description:** Returns aggregate portfolio star averages, review totals, and anomaly indicators.
- **Response `200 OK`:**
```json
{
  "total_products": 15641,
  "total_reviews": 50000,
  "average_star_rating": 4.21,
  "scenario_a_traps_count": 440,
  "scenario_b_gems_count": 174,
  "scenario_c_lemons_count": 1481
}
```

---

### 3. Paginated Product Reviews
- **Endpoint:** `GET /api/reviews?page=1&page_size=20&sort=helpful`
- **Query Parameters:**
  - `page` (integer, default: 1): Page number offset.
  - `page_size` (integer, default: 20, max: 100): Records per page.
  - `asin` (string, optional): Specific ASIN filter.
  - `sort` (string, optional): `recent`, `helpful`, `rating_asc`, `rating_desc`.
- **Response `200 OK`:**
```json
{
  "page": 1,
  "page_size": 20,
  "total_records": 50000,
  "results": [
    {
      "review_id": "rev_7f9a2b",
      "asin": "B07JJQR94P",
      "rating": 1.0,
      "title": "Wire harness melted in 2 weeks",
      "text": "Dangerous part. Motor overheated and burned plastic smell.",
      "verified_purchase": true,
      "helpful_vote": 74,
      "review_timestamp": "2022-04-12T18:22:00Z"
    }
  ]
}
```

---

### 4. Shopper Feedback Ingestion
- **Endpoint:** `POST /api/shopper-reviews`
- **Headers:** `Content-Type: application/json`
- **Request Body Contract (Enforced via Pandera):**
```json
{
  "asin": "B0BDFT8DZR",
  "rating": 5,
  "review_text": "Makes soft crunchy nugget ice, fits perfectly under counter.",
  "dwell_time_seconds": 142,
  "added_to_cart": true
}
```
- **Response `201 Created`:**
```json
{
  "status": "success",
  "feedback_id": 892,
  "sentiment_classification": "POSITIVE",
  "sentiment_confidence": 0.942,
  "message": "Shopper feedback successfully audited and stored."
}
```

---

## 13. Production Deployment Guide (Vercel + Streamlit)

### Deploying the Storefront to Vercel

1. **Import Project:** In the [Vercel Dashboard](https://vercel.com/), select **Add New Project** and import the `Aislewise-2` repository.
2. **Root Directory:** Set the project root to `./`.
3. **Environment Variables:**
   - Configure `DATABASE_URL` (Neon PostgreSQL connection string).
   - Configure `FLASK_ENV="production"`.
4. **Vercel Build Output:** `vercel.json` automatically configures the Python 3.12 WSGI serverless wrapper to route requests to `app.py`.
5. **Model Ingestion:** Ensure `models/sentiment_pipeline.pkl` is tracked via Git LFS or standard Git (< 50MB) so the serverless function can deserialize it during cold start.

### Deploying the Executive BI Dashboard to Streamlit Cloud

1. **New App:** Open [Streamlit Community Cloud](https://share.streamlit.io/) and connect your GitHub repository.
2. **Main File Path:** Set to `streamlit/app.py`.
3. **Branch:** `main`.
4. **Secrets Management:** In **App Settings > Secrets**, configure:
   ```toml
   AISLEWISE_WAREHOUSE_PATH = "warehouse.duckdb"
   ```
5. **Snapshot Verification:** Verify that `warehouse.duckdb` has been refreshed with the latest scenario tables (`gold_product_discrepancy_flags`, etc.) prior to committing or hosting.

---

## 14. Automated Testing Suite

Aislewise maintains rigorous test coverage spanning API endpoints, Pandera data contracts, database transactions, and ML inference:

```bash
# Run full test suite with verbose output
python -m pytest -q

# Test Pandera validation contracts
python -m pytest tests/test_schema.py

# Test scikit-learn sentiment inference service
python -m pytest tests/test_sentiment.py

# Test Flask REST controllers and routing
python -m pytest tests/test_api.py
```

---

## 15. Operational Guardrails & Security Policies

1. **Data Freshness Guarantees:** Transactional PostgreSQL changes are isolated from DuckDB. Refresh the analytical layer deterministically using `incremental_sync.py` before presenting forensic reports to executive stakeholders.
2. **Investigative vs. Conclusive Claims:** Scenario anomaly flags identify statistical divergence ($\pm 3\sigma$). They serve as targeted investigative leads for quality assurance teams, not legally conclusive proof of merchant fraud.
3. **Zero Secret Leakage:** Database credentials and SSL private keys must never be included in client-facing bundles, vanilla JS scripts, or committed files.
4. **Model Boundaries:** Sentiment confidence values are probabilistic outputs of statistical language models. Critical corrective notices must be validated with verified buyer purchase checks.

---

## 16. Repository Structure

```
Aislewise-2/
├── api/                         # Vercel serverless gateway routing
│   └── index.py
├── migrations/                  # Idempotent PostgreSQL schema DDL
│   └── 001_create_shopper_feedback.sql
├── models/                      # Deserialized scikit-learn pipeline artifacts
│   └── sentiment_pipeline.pkl
├── public/static/               # Zero-framework CSS, JS & SVG navigation assets
│   ├── css/
│   │   └── main.css
│   └── js/
│       ├── astar_engine.js      # Client-side A* pathfinding
│       └── navigation_map.js    # Interactive SVG coordinate graph
├── Scenario_A/                  # Trap-product forensic routines
│   ├── scenario_a_trap_products.py
│   ├── charts/
│   └── reports/
├── Scenario_B/                  # Review collision and velocity analyzers
│   ├── scenario_b_base_detection.py
│   ├── scenario_b_deep_forensics.py
│   ├── charts/
│   └── reports/
├── Scenario_C/                  # Semantic NLP audit scripts
│   ├── scenario_c_audit.py
│   ├── charts/
│   └── reports/
├── streamlit/                   # Streamlit dashboard workspace
│   ├── app.py                   # BI interface & scenario visualizations
│   └── requirements.txt         # Isolated analytics dependencies
├── templates/                   # Frontend markup templates (Jinja2)
│   ├── index.html
│   └── navigation.html
├── tests/                       # Automated test suite
│   ├── test_api.py
│   ├── test_schema.py
│   └── test_sentiment.py
├── app.py                       # Core Flask application and REST controllers
├── shopper_review_schema.py     # Pandera payload validation contract
├── sentiment_service.py         # Model loading and prediction interface
├── dataset_generation.py        # Synthetic review corpus generator
├── load_to_postgres.py          # PostgreSQL bulk ingestion script
├── ingest_to_duckdb.py          # DuckDB Bronze ingestion script
├── incremental_sync.py          # CDC synchronizer (PostgreSQL -> DuckDB)
├── warehouse.duckdb             # Local OLAP analytics Gold snapshot
├── aislewise_warehouse.duckdb   # Working store for raw batch extraction
├── requirements.txt             # Web production dependencies (Flask/Vercel)
├── requirements-analysis.txt    # Data processing & scenario dependencies
├── requirements-dev.txt         # Testing & linting toolchains
├── docker-compose.yml           # Container orchestration
├── vercel.json                  # Serverless function runtime config
├── .env.example                 # Environment template
└── README.md                    # System documentation & master report
```

---

## 17. Author & Acknowledgements

**Poruri Jayakara Santhosh Vardhan**  
*AI/ML Engineer & Distributed Architecture Specialist*  
- **GitHub:** [@poruri-santhosh](https://github.com/poruri-santhosh)  
- **Project Repository:** [Aislewise-2 on GitHub](https://github.com/poruri-santhosh/Aislewise-2)  

### License
This project is licensed under the Apache License, Version 2.0. See the `LICENSE` file for details.

---

*Aislewise – Turning Customer Sentiment into Quality Intelligence and In-Store Shopping into a Frictionless Journey.*
