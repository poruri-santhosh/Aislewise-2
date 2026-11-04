import json
import os
import sys
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from sentiment_service import predict_sentiment


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Scenario_A.scenario_mlflow import (  # noqa: E402
    infer_review_sentiment,
    load_sentiment_model,
    register_ml_review_frame,
    register_scenario_b_forensics,
)

WAREHOUSE_PATH = Path(
    os.getenv("AISLEWISE_WAREHOUSE_PATH", str(PROJECT_ROOT / "warehouse.duckdb"))
).resolve()

SCENARIO_IMAGE_FILES = {
    "Scenario A": [
        "chart_scenario_a.png",
        "chart_price_vs_defects.png",
        "chart_scenario_a_forensics.png",
        "chart_scenario_a_complaints.png",
        "chart_scenario_a_durability.png",
    ],
    "Scenario B": [
        "chart_scenario_b_base.png",
        "chart_scenario_b_forensics.png",
        "chart_scenario_b_recovery.png",
    ],
    "Scenario C": ["chart_scenario_c_audit.png"],
}

st.set_page_config(
    page_title="Aislewise Quality Dashboard",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom High-Contrast Light-on-Dark Styling
st.markdown(
    """
    <style>
        /* Base page background */
        .stApp {
            background: linear-gradient(135deg, #090D16 0%, #0F172A 50%, #131D31 100%);
            color: #F8FAFC !important;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #0B1120 !important;
            border-right: 1px solid #334155 !important;
        }
        [data-testid="stSidebar"] label, [data-testid="stSidebar"] span, [data-testid="stSidebar"] p {
            color: #F1F5F9 !important;
            font-weight: 500;
        }

        /* General Typography */
        h1, h2, h3, h4, h5, h6, p, span, label {
            color: #F8FAFC !important;
        }
        .main-title { 
            font-size: 32px; 
            font-weight: 800; 
            color: #FFFFFF !important; 
            margin-bottom: 4px; 
            letter-spacing: -0.5px;
        }
        .sub-title { 
            font-size: 15px; 
            color: #CBD5E1 !important; 
            margin-bottom: 22px; 
        }

        /* Status Badge */
        .live-badge { 
            background: rgba(16, 185, 129, 0.25); 
            color: #6EE7B7 !important; 
            padding: 6px 14px; 
            border-radius: 20px; 
            font-weight: 700; 
            font-size: 13px; 
            border: 1px solid #34D399;
            display: inline-block;
        }

        /* Metric Cards */
        div[data-testid="stMetric"] {
            background: #1E293B !important;
            border: 1px solid #475569 !important;
            border-radius: 12px;
            padding: 14px 18px;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
        }
        div[data-testid="stMetric"] label {
            color: #CBD5E1 !important;
            font-size: 13px !important;
            font-weight: 600 !important;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #FFFFFF !important;
            font-size: 28px !important;
            font-weight: 800 !important;
        }

        /* Information / Note Cards */
        .explain-box {
            background: #1E293B !important;
            border-left: 5px solid #818CF8 !important;
            padding: 16px 20px;
            border-radius: 0 10px 10px 0;
            margin-bottom: 22px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
            border-top: 1px solid #334155;
            border-right: 1px solid #334155;
            border-bottom: 1px solid #334155;
        }
        .explain-title {
            font-size: 15px;
            font-weight: 700;
            color: #FFFFFF !important;
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
        }
        .explain-desc {
            font-size: 14px;
            color: #E2E8F0 !important;
            line-height: 1.6;
            margin: 0;
        }
        .action-chip {
            display: inline-block;
            background: rgba(129, 140, 248, 0.25) !important;
            color: #C7D2FE !important;
            font-size: 12px;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 6px;
            margin-top: 8px;
            border: 1px solid #818CF8;
        }

        /* Tabs Styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            border-bottom: 2px solid #334155;
            padding-bottom: 4px;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            padding: 10px 20px;
            color: #CBD5E1 !important;
            background-color: transparent;
            font-weight: 600;
        }
        .stTabs [aria-selected="true"] {
            background-color: #1E293B !important;
            color: #93C5FD !important;
            font-weight: 700 !important;
            border-bottom: 3px solid #60A5FA !important;
        }

        /* Dataframe Visibility */
        [data-testid="stDataFrame"] {
            border: 1px solid #334155;
            border-radius: 8px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_ml_scored_reviews(db_path, model):
    source = duckdb.connect(db_path, read_only=True)
    try:
        reviews = source.execute("SELECT * FROM silver_reviews").df()
    finally:
        source.close()
    return infer_review_sentiment(model, reviews)


def has_table(connection, table_name):
    return (
        connection.execute(
            """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
            [table_name],
        ).fetchone()[0]
        > 0
    )


def product_dimensions(connection):
    if has_table(connection, "gold_scenario_a_durability"):
        category_join = """
            LEFT JOIN (
                SELECT product_id, MAX(appliance_category) AS category
                FROM gold_scenario_a_durability
                GROUP BY product_id
            ) AS c USING (product_id)
        """
        category_value = "COALESCE(c.category, 'General')"
    else:
        category_join = ""
        category_value = "'General'"

    return connection.execute(
        f"""
        SELECT
            r.product_id,
            p.title,
            p.price,
            {category_value} AS category
        FROM (SELECT DISTINCT product_id FROM silver_reviews_ml) AS r
        LEFT JOIN bronze_products AS p USING (product_id)
        {category_join}
        ORDER BY r.product_id
        """
    ).df()


def price_tier(price):
    if pd.isna(price):
        return "Unknown"
    if price < 25:
        return "Under $25"
    if price < 100:
        return "$25 to $100"
    return "Above $100"


def show_scenario_images(scenario):
    with st.expander(f"📁 View Charts & Reports ({scenario})", expanded=False):
        for image_name in SCENARIO_IMAGE_FILES[scenario]:
            image_path = PROJECT_ROOT / scenario.replace(" ", "_") / image_name
            if image_path.is_file():
                st.image(str(image_path), caption=image_name, use_container_width=True)


def show_vendor_notices():
    index_path = PROJECT_ROOT / "Scenario_A" / "vendor_memos" / "vendor_notices_index.json"
    st.markdown("#### Supplier Warning Letters")
    if not index_path.is_file():
        st.info("No supplier warning letters found.")
        return
    with index_path.open(encoding="utf-8") as index_file:
        notices = json.load(index_file)
    if not isinstance(notices, list):
        raise ValueError("vendor_notices_index.json must contain a JSON list.")
    st.dataframe(pd.DataFrame(notices), use_container_width=True, hide_index=True)


def apply_bright_plot_style(fig):
    """Ensures all charts have crisp white text, light tick marks, and visible grid lines."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F8FAFC", size=12),
        title_font=dict(color="#FFFFFF", size=15),
        legend=dict(
            font=dict(color="#F1F5F9"),
            bgcolor="rgba(30, 41, 59, 0.7)",
            bordercolor="#475569",
            borderwidth=1,
        ),
    )
    fig.update_xaxes(
        color="#F1F5F9",
        tickfont=dict(color="#E2E8F0"),
        gridcolor="#334155",
        zerolinecolor="#475569",
    )
    fig.update_yaxes(
        color="#F1F5F9",
        tickfont=dict(color="#E2E8F0"),
        gridcolor="#334155",
        zerolinecolor="#475569",
    )
    return fig


def render_dashboard():
    if not WAREHOUSE_PATH.is_file():
        st.error(f"Database not found: {WAREHOUSE_PATH}")
        st.stop()

    st.sidebar.title("⚡ Control Panel")
    auto_refresh = st.sidebar.checkbox("Auto Refresh (every 10 seconds)", value=False)
    if auto_refresh:
        st_autorefresh(interval=10_000, key="datarefresh")
    if st.sidebar.button("🔄 Refresh Data Now"):
        st.rerun()

    try:
        import joblib
        from pathlib import Path

        model_file = Path(__file__).resolve().parent.parent / "models" / "sentiment_pipeline.pkl"
        if not model_file.exists():
            model_file = Path("models/sentiment_pipeline.pkl")

        model = joblib.load(str(model_file))
        classifier = getattr(model, "named_steps", {}).get("clf")
        if classifier is not None and not hasattr(classifier, "multi_class"):
            classifier.multi_class = "auto"

        scored_reviews = get_ml_scored_reviews(str(WAREHOUSE_PATH), model)
    except Exception as error:
        st.error(
            "Could not load the AI model or read reviews. "
            f"Details: {error}"
        )
        st.stop()

    connection = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    try:
        register_ml_review_frame(connection, scored_reviews)
        register_scenario_b_forensics(connection)
        connection.execute(
            """
            CREATE OR REPLACE TEMP TABLE dashboard_model_confidence AS
            SELECT
                product_id,
                COALESCE(AVG(COALESCE(ml_confidence, 1.0)), 1.0)
                    AS model_confidence
            FROM silver_reviews_ml
            GROUP BY product_id
            """
        )
        dimensions = product_dimensions(connection)
        dimensions["price_tier"] = dimensions["price"].map(price_tier)

        st.sidebar.subheader("Filter Items")
        min_confidence = st.sidebar.slider(
            "Minimum AI Confidence",
            min_value=0.50,
            max_value=1.00,
            value=0.50,
            step=0.01,
        )
        price_options = ["All"] + sorted(dimensions["price_tier"].dropna().unique().tolist())
        selected_price_tiers = st.sidebar.multiselect(
            "Price Range",
            options=price_options,
            default=["All"],
        )
        category_options = ["All"] + sorted(dimensions["category"].dropna().unique().tolist())
        selected_categories = st.sidebar.multiselect(
            "Product Category",
            options=category_options,
            default=["All"],
        )

        filtered_dimensions = dimensions
        if selected_price_tiers and "All" not in selected_price_tiers:
            filtered_dimensions = filtered_dimensions[
                filtered_dimensions["price_tier"].isin(selected_price_tiers)
            ]
        if selected_categories and "All" not in selected_categories:
            filtered_dimensions = filtered_dimensions[
                filtered_dimensions["category"].isin(selected_categories)
            ]
        connection.register(
            "dashboard_filtered_products",
            filtered_dimensions[["product_id"]].drop_duplicates(),
        )

        filtered_flags = connection.execute(
            """
            SELECT
                f.*,
                COALESCE(f.avg_ml_confidence, m.model_confidence, 1.0)
                    AS resolved_ml_confidence
            FROM gold_product_discrepancy_flags AS f
            INNER JOIN dashboard_filtered_products AS d USING (product_id)
            LEFT JOIN dashboard_model_confidence AS m USING (product_id)
            WHERE COALESCE(f.avg_ml_confidence, m.model_confidence, 1.0) >= ?
            """,
            [min_confidence],
        ).df()
        reviewed_product_count = max(len(filtered_dimensions), 1)
        trap_count = int((filtered_flags["flag"] == "INVESTIGATE_SCENARIO_A").sum())
        average_confidence = (
            float(scored_reviews["ml_confidence"].mean()) if not scored_reviews.empty else 1.0
        )
        scenario_b_count = int((filtered_flags["flag"] == "INVESTIGATE_SCENARIO_B").sum())
        scenario_c_count = int((filtered_flags["flag"] == "INVESTIGATE_SCENARIO_C").sum())

        title_col, badge_col = st.columns([4, 1])
        with title_col:
            st.markdown(
                '<div class="main-title">🛒 Aislewise: Product Quality & AI Review Monitor</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="sub-title">Detecting review manipulation, hidden quality issues, and catalog errors</div>',
                unsafe_allow_html=True,
            )
        with badge_col:
            st.markdown(
                '<div style="text-align: right; margin-top: 10px;"><span class="live-badge">🟢 AI MODEL ONLINE</span></div>',
                unsafe_allow_html=True,
            )

        metric_columns = st.columns(5)
        metric_columns[0].metric("Total Reviews Scanned", f"{len(scored_reviews):,}")
        metric_columns[1].metric(
            "Rating Trap Ratio",
            f"{trap_count / reviewed_product_count:.1%}",
            help=f"{trap_count:,} fake/misleading products out of {len(filtered_dimensions):,} checked items.",
        )
        metric_columns[2].metric("Average AI Confidence", f"{average_confidence:.1%}")
        metric_columns[3].metric("Hidden Good Products", f"{scenario_b_count:,}")
        metric_columns[4].metric("Defective Products", f"{scenario_c_count:,}")

        st.markdown(
            """
            <div class="explain-box">
                <div class="explain-title">💡 How this dashboard works</div>
                <div class="explain-desc">
                    Sometimes star ratings don't tell the real story. An item can show 4.5 stars due to fake reviews, 
                    even when verified customer comments describe broken parts or severe defects. 
                    Our AI reads the actual customer text to spot mismatches between stars and real opinions.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### 📊 Storewide Summary")
        g_col1, g_col2 = st.columns(2)
        with g_col1:
            flag_dist = (
                filtered_flags["flag"]
                .value_counts()
                .reset_index()
                .rename(columns={"flag": "Category", "count": "Count"})
            )
            if not flag_dist.empty:
                category_labels = {
                    "INVESTIGATE_SCENARIO_A": "Fake High Ratings (Traps)",
                    "INVESTIGATE_SCENARIO_B": "Hidden Good Products",
                    "INVESTIGATE_SCENARIO_C": "High Defect Rate",
                }
                flag_dist["Category"] = flag_dist["Category"].map(
                    lambda x: category_labels.get(x, x)
                )
                fig_flag_pie = px.pie(
                    flag_dist,
                    names="Category",
                    values="Count",
                    title="Product Issue Breakdown",
                    hole=0.45,
                    color_discrete_sequence=["#F87171", "#60A5FA", "#FBBF24"],
                )
                fig_flag_pie.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
                apply_bright_plot_style(fig_flag_pie)
                st.plotly_chart(fig_flag_pie, use_container_width=True)

        with g_col2:
            sentiment_dist = (
                scored_reviews["sentiment"]
                .value_counts()
                .reset_index()
                .rename(columns={"sentiment": "Sentiment", "count": "Reviews"})
            )
            if not sentiment_dist.empty:
                fig_sent_bar = px.bar(
                    sentiment_dist,
                    x="Sentiment",
                    y="Reviews",
                    color="Sentiment",
                    title="Customer Sentiment in Reviews",
                    text_auto=True,
                    color_discrete_map={
                        "positive": "#34D399",
                        "negative": "#F87171",
                        "neutral": "#94A3B8",
                    },
                )
                fig_sent_bar.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
                apply_bright_plot_style(fig_sent_bar)
                st.plotly_chart(fig_sent_bar, use_container_width=True)

        st.markdown("---")
        tab_a, tab_b, tab_c, tab_search = st.tabs(
            [
                "🚨 Scenario A: Rating Traps",
                "💎 Scenario B: Hidden Gems",
                "🧭 Scenario C: Poor Quality Items",
                "🔍 Search Any Product",
            ]
        )

        with tab_a:
            st.markdown(
                """
                <div class="explain-box" style="border-left-color: #F87171 !important;">
                    <div class="explain-title" style="color: #FCA5A5 !important;">🚨 Scenario A: High Stars with Severe Complaints</div>
                    <div class="explain-desc">
                        <b>What this means:</b> These items show 4.0+ stars, but over <b>35% of customer reviews are strongly negative</b>. 
                        Buyers are getting misled by old ratings or bot activity while recent batches arrive broken.
                        <br><span class="action-chip" style="background: rgba(239, 68, 68, 0.25) !important; color: #FECACA !important; border-color: #F87171;">
                            Suggested Action: Pause sales and review supplier batch quality
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            traps = connection.execute(
                """
                SELECT f.product_id, p.title, p.price, f.avg_star_rating AS stars,
                       f.negative_pct AS negative_pct, f.total_reviews,
                       COALESCE(f.avg_ml_confidence, m.model_confidence, 1.0)
                           AS ml_confidence
                FROM gold_product_discrepancy_flags AS f
                LEFT JOIN bronze_products AS p USING (product_id)
                LEFT JOIN dashboard_model_confidence AS m USING (product_id)
                INNER JOIN dashboard_filtered_products AS d USING (product_id)
                WHERE f.flag = 'INVESTIGATE_SCENARIO_A'
                  AND COALESCE(f.avg_ml_confidence, m.model_confidence, 1.0) >= ?
                ORDER BY f.negative_pct DESC, f.total_reviews DESC
                """,
                [min_confidence],
            ).df()

            if not traps.empty:
                c1, c2 = st.columns([2, 1])
                with c1:
                    fig_scatter_a = px.scatter(
                        traps,
                        x="stars",
                        y="negative_pct",
                        size="total_reviews",
                        color="ml_confidence",
                        hover_data=["product_id", "price"],
                        title="Star Rating vs Actual Negative Reviews",
                        labels={"stars": "Displayed Star Rating", "negative_pct": "Negative Reviews %"},
                        color_continuous_scale="sunset",
                    )
                    fig_scatter_a.update_layout(height=340, margin=dict(t=40, b=20, l=20, r=20))
                    apply_bright_plot_style(fig_scatter_a)
                    st.plotly_chart(fig_scatter_a, use_container_width=True)
                with c2:
                    top_traps = traps.head(8)
                    fig_bar_a = px.bar(
                        top_traps,
                        x="negative_pct",
                        y="product_id",
                        orientation="h",
                        title="Top Products to Investigate",
                        color="negative_pct",
                        color_continuous_scale="Reds",
                    )
                    fig_bar_a.update_layout(
                        height=340,
                        yaxis=dict(autorange="reversed"),
                        margin=dict(t=40, b=20, l=20, r=20),
                    )
                    apply_bright_plot_style(fig_bar_a)
                    st.plotly_chart(fig_bar_a, use_container_width=True)

            st.dataframe(traps, use_container_width=True, hide_index=True)
            show_vendor_notices()
            show_scenario_images("Scenario A")

        with tab_b:
            st.markdown(
                """
                <div class="explain-box" style="border-left-color: #38BDF8 !important;">
                    <div class="explain-title" style="color: #7DD3FC !important;">💎 Scenario B: Hidden High-Quality Products</div>
                    <div class="explain-desc">
                        <b>What this means:</b> Excellent products that are getting pushed down in search rankings. 
                        This happens when a good item gets hit by an accidental 1-star delivery complaint, or when reviews are mapped incorrectly. 
                        Actual feedback shows <b>over 90% positive sentiment</b>.
                        <br><span class="action-chip" style="background: rgba(56, 189, 248, 0.25) !important; color: #E0F2FE !important; border-color: #38BDF8;">
                            Suggested Action: Fix catalog position and feature on front page
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            gems = connection.execute(
                """
                SELECT b.product_id, p.title, p.price, b.total_reviews, b.avg_rating,
                       b.positive_pct, b.forensic_verdict,
                       COALESCE(b.avg_model_confidence, 1.0) AS ml_confidence
                FROM scenario_b_forensics_ml AS b
                LEFT JOIN bronze_products AS p USING (product_id)
                INNER JOIN dashboard_filtered_products AS d USING (product_id)
                WHERE COALESCE(b.avg_model_confidence, 1.0) >= ?
                ORDER BY b.positive_pct DESC, b.total_reviews DESC
                """,
                [min_confidence],
            ).df()

            if not gems.empty:
                b1, b2 = st.columns(2)
                with b1:
                    verdict_dist = gems["forensic_verdict"].value_counts().reset_index()
                    verdict_dist.columns = ["Verdict", "Count"]
                    fig_verdict = px.pie(
                        verdict_dist,
                        names="Verdict",
                        values="Count",
                        title="Why Products Were Hidden",
                        hole=0.4,
                        color_discrete_sequence=px.colors.qualitative.Pastel,
                    )
                    fig_verdict.update_layout(height=330, margin=dict(t=40, b=20, l=20, r=20))
                    apply_bright_plot_style(fig_verdict)
                    st.plotly_chart(fig_verdict, use_container_width=True)
                with b2:
                    fig_pos = px.histogram(
                        gems,
                        x="positive_pct",
                        nbins=15,
                        title="Positive Review Percentage Across Gems",
                        color_discrete_sequence=["#38BDF8"],
                    )
                    fig_pos.update_layout(height=330, margin=dict(t=40, b=20, l=20, r=20))
                    apply_bright_plot_style(fig_pos)
                    st.plotly_chart(fig_pos, use_container_width=True)

            st.dataframe(gems, use_container_width=True, hide_index=True)
            show_scenario_images("Scenario B")

        with tab_c:
            st.markdown(
                """
                <div class="explain-box" style="border-left-color: #F59E0B !important;">
                    <div class="explain-title" style="color: #FDE68A !important;">🧭 Scenario C: Consistently Defective Items</div>
                    <div class="explain-desc">
                        <b>What this means:</b> Low-quality products that keep receiving high return rates and poor reviews. 
                        Keeping these items visible damages buyer trust across the store.
                        <br><span class="action-chip" style="background: rgba(245, 158, 11, 0.25) !important; color: #FEF3C7 !important; border-color: #FBBF24;">
                            Suggested Action: Remove from primary aisles or delist product
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            lemons = connection.execute(
                """
                SELECT f.product_id, p.title, p.price, f.total_reviews,
                       f.avg_star_rating AS stars, f.negative_pct,
                       COALESCE(f.avg_ml_confidence, m.model_confidence, 1.0)
                           AS ml_confidence
                FROM gold_product_discrepancy_flags AS f
                LEFT JOIN bronze_products AS p USING (product_id)
                LEFT JOIN dashboard_model_confidence AS m USING (product_id)
                INNER JOIN dashboard_filtered_products AS d USING (product_id)
                WHERE f.flag = 'INVESTIGATE_SCENARIO_C'
                  AND COALESCE(f.avg_ml_confidence, m.model_confidence, 1.0) >= ?
                ORDER BY f.negative_pct DESC, f.total_reviews DESC
                """,
                [min_confidence],
            ).df()

            if not lemons.empty:
                fig_lemons = px.box(
                    lemons,
                    x="negative_pct",
                    title="Spread of Negative Feedback (% of Reviews)",
                    points="outliers",
                    color_discrete_sequence=["#FBBF24"],
                )
                fig_lemons.update_layout(height=260, margin=dict(t=40, b=20, l=20, r=20))
                apply_bright_plot_style(fig_lemons)
                st.plotly_chart(fig_lemons, use_container_width=True)

            st.dataframe(lemons, use_container_width=True, hide_index=True)
            show_scenario_images("Scenario C")

        with tab_search:
            st.markdown(
                """
                <div class="explain-box" style="border-left-color: #34D399 !important;">
                    <div class="explain-title" style="color: #6EE7B7 !important;">🔍 Single Product Check</div>
                    <div class="explain-desc">
                        Type any Product ID (ASIN) below to see its complete rating history, customer comments, and AI sentiment analysis.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            product_id = st.text_input("Enter Product ID to inspect:", "").strip()
            if product_id:
                details = connection.execute(
                    """
                    SELECT f.product_id, f.flag, f.avg_star_rating, f.positive_pct,
                           f.negative_pct, f.total_reviews,
                           COALESCE(f.avg_ml_confidence, m.model_confidence, 1.0)
                               AS ml_confidence
                    FROM gold_product_discrepancy_flags AS f
                    LEFT JOIN dashboard_model_confidence AS m USING (product_id)
                    WHERE f.product_id = ?
                    """,
                    [product_id],
                ).df()
                if details.empty:
                    st.warning(f"No flagged issues found for Product ID '{product_id}'.")
                else:
                    st.dataframe(details, use_container_width=True, hide_index=True)
                    reviews = connection.execute(
                        """
                        SELECT rating, sentiment, ml_confidence, verified_purchase,
                               helpful_vote, title, text
                        FROM silver_reviews_ml
                        WHERE product_id = ? AND COALESCE(ml_confidence, 1.0) >= ?
                        ORDER BY helpful_vote DESC, rating ASC
                        """,
                        [product_id, min_confidence],
                    ).df()

                    if not reviews.empty:
                        r1, r2 = st.columns(2)
                        with r1:
                            fig_prod_sent = px.pie(
                                reviews,
                                names="sentiment",
                                title=f"Sentiment for {product_id}",
                                hole=0.35,
                                color="sentiment",
                                color_discrete_map={
                                    "positive": "#34D399",
                                    "negative": "#F87171",
                                    "neutral": "#94A3B8",
                                },
                            )
                            fig_prod_sent.update_layout(height=280)
                            apply_bright_plot_style(fig_prod_sent)
                            st.plotly_chart(fig_prod_sent, use_container_width=True)
                        with r2:
                            fig_prod_ratings = px.histogram(
                                reviews,
                                x="rating",
                                title=f"Star Ratings for {product_id}",
                                nbins=5,
                                color_discrete_sequence=["#FBBF24"],
                            )
                            fig_prod_ratings.update_layout(height=280)
                            apply_bright_plot_style(fig_prod_ratings)
                            st.plotly_chart(fig_prod_ratings, use_container_width=True)

                    st.dataframe(reviews, use_container_width=True, hide_index=True)
    finally:
        connection.close()


render_dashboard()