import os
import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration
st.set_page_config(
    page_title="Aislewise Intelligence Dashboard",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

DUCKDB_PATH = "warehouse.duckdb"

# 2. Live Data Refresh Logic
# ప్రతి 10 సెకన్లకు ఒకసారి డ్యాష్‌బోర్డ్‌ను రీ-రన్ చేసి కొత్త డేటాను లాగుతుంది
st.sidebar.title("⚡ Stream Controls")
auto_refresh = st.sidebar.checkbox("Enable Live Data Stream (10s sync)", value=True)
if auto_refresh:
    # 10,000 milliseconds = 10 seconds auto-refresh
    st.empty()
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=10000, key="datarefresh")
    except ImportError:
        pass

if st.sidebar.button("🔄 Force Live Refresh"):
    st.cache_data.clear()
    st.rerun()

# Dynamic Connection: No hard cache so live inserts from PostgreSQL/MongoDB are caught immediately
def get_live_con():
    return duckdb.connect(DUCKDB_PATH, read_only=True)

con = get_live_con()

# Custom CSS for UI
st.markdown("""
    <style>
        .main-title { font-size: 28px; font-weight: bold; color: #1E3A8A; margin-bottom: 0px; }
        .sub-title { font-size: 15px; color: #4B5563; margin-bottom: 20px; }
        .live-badge { background-color: #DEF7EC; color: #03543F; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 13px; }
    </style>
""", unsafe_allow_html=True)

col_t1, col_t2 = st.columns([4, 1])
with col_t1:
    st.markdown('<div class="main-title">🛒 Aislewise: Catalog Quality & Forensic Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Live Discrepancy Stream: Rating Traps, Hidden Gems, and Lemons</div>', unsafe_allow_html=True)
with col_t2:
    st.markdown('<br><span class="live-badge">🟢 LIVE WAREHOUSE SYNC</span>', unsafe_allow_html=True)

# 3. Live Executive KPI Strip
try:
    total_prods = con.execute("SELECT COUNT(DISTINCT product_id) FROM silver_reviews;").fetchone()[0]
    total_revs = con.execute("SELECT COUNT(*) FROM silver_reviews;").fetchone()[0]
    scen_a_count = con.execute("SELECT COUNT(*) FROM gold_product_discrepancy_flags WHERE flag = 'INVESTIGATE_SCENARIO_A';").fetchone()[0]
    scen_b_count = con.execute("SELECT COUNT(*) FROM gold_product_discrepancy_flags WHERE flag = 'INVESTIGATE_SCENARIO_B';").fetchone()[0]
    scen_c_count = con.execute("SELECT COUNT(*) FROM gold_product_discrepancy_flags WHERE avg_star_rating <= 2.5 AND negative_pct >= 60.0;").fetchone()[0]
except Exception as e:
    st.error(f"Error connecting to live warehouse: {e}")
    st.stop()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Catalog Products", f"{total_prods:,}")
col2.metric("Analyzed Reviews", f"{total_revs:,}")
col3.metric("Scenario A (Traps)", f"{scen_a_count:,}", delta="Rating Gap", delta_color="inverse")
col4.metric("Scenario B (Gems)", f"{scen_b_count:,}", delta="Under-reviewed", delta_color="normal")
col5.metric("Scenario C (Lemons)", f"{scen_c_count:,}", delta="Purge Needed", delta_color="inverse")

st.markdown("---")

# 4. Interactive Tabs
tab_a, tab_b, tab_c, tab_search = st.tabs([
    "🚨 Scenario A: Rating Traps", 
    "💎 Scenario B: Hidden Gems", 
    "🍋 Scenario C: Catalog Lemons", 
    "🔍 Real-Time ASIN Inspector"
])

# --- TAB A: RATING TRAPS ---
with tab_a:
    st.subheader("Scenario A: Deceptive Star Ratings (Rating Traps)")
    st.caption("Products with public Star Rating >= 4.0 but high negative customer review text (>= 35%).")
    
    col_a_left, col_a_right = st.columns([3, 2])
    with col_a_left:
        df_traps = con.execute("""
            SELECT 
                f.product_id,
                f.avg_star_rating as stars,
                f.negative_pct as neg_pct,
                f.total_reviews as total_revs,
                f.neg_count
            FROM gold_product_discrepancy_flags f
            WHERE f.flag = 'INVESTIGATE_SCENARIO_A'
            ORDER BY f.negative_pct DESC, f.total_reviews DESC
            LIMIT 50;
        """).df()
        st.write(f"##### Top Traps (Live Count: {len(df_traps)})")
        st.dataframe(df_traps.style.format({"stars": "{:.2f} ⭐", "neg_pct": "{:.1f}%"}), width="stretch", height=320)
        
    with col_a_right:
        st.write("##### Forensic Defect Distribution")
        defect_data = pd.DataFrame({
            "Category": ["Mechanical / Part Defect", "Size & Compatibility Flaw", "General Dissatisfaction", "Shipping & Delivery", "Packaging Damage"],
            "Share": [48.89, 23.54, 20.72, 5.23, 1.61]
        })
        fig_pie = px.pie(defect_data, names="Category", values="Share", hole=0.45, color_discrete_sequence=px.colors.sequential.Reds_r)
        fig_pie.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
        st.plotly_chart(fig_pie, width="stretch")

    st.markdown("##### 📑 Automated Supplier Audit Notice Inspection")
    selected_trap = st.selectbox("Select Flagged Trap ASIN:", df_traps["product_id"].tolist())
    if selected_trap:
        memo_path = os.path.join("Scenario_A", "vendor_memos", f"VENDOR_NOTICE_{selected_trap}.txt")
        if os.path.exists(memo_path):
            with open(memo_path, "r", encoding="utf-8") as f:
                st.text_area("Vendor Quality Warning Notice Content:", f.read(), height=180)
        else:
            st.info(f"Vendor notice for {selected_trap} can be generated via Scenario A memo engine.")

# --- TAB B: HIDDEN GEMS ---
with tab_b:
    st.subheader("Scenario B: Underrated Hidden Gems")
    st.caption("Products with displayed Rating <= 3.0 but authentic positive customer text >= 65%.")
    
    df_gems = con.execute("""
        SELECT product_id, total_reviews, avg_rating, positive_pct, forensic_verdict
        FROM gold_scenario_b_forensics
        ORDER BY positive_pct DESC, total_reviews DESC;
    """).df()

    col_b_left, col_b_right = st.columns([3, 2])
    with col_b_left:
        st.write(f"##### Suppressed Quality Products ({len(df_gems)} Items)")
        st.dataframe(df_gems.style.format({"avg_rating": "{:.2f} ⭐", "positive_pct": "{:.1f}%"}), width="stretch", height=320)
        
    with col_b_right:
        st.write("##### Diagnostic Bottlenecks")
        verdict_counts = df_gems["forensic_verdict"].value_counts().reset_index()
        verdict_counts.columns = ["Verdict", "Count"]
        fig_bar = px.bar(verdict_counts, x="Count", y="Verdict", orientation="h", color="Count", color_continuous_scale="Teal")
        fig_bar.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=300)
        st.plotly_chart(fig_bar, width="stretch")

    st.success("💡 **Action Roadmap:** 98.9% of these products need only **1 to 2 verified 5-star reviews** to climb to a 4.0+ rating.")

# --- TAB C: CATALOG LEMONS ---
with tab_c:
    st.subheader("Scenario C: Confirmed Catalog Lemons")
    st.caption("Products with consistently poor ratings (<= 2.5) and overwhelming negative complaints (>= 60%).")
    
    df_lemons = con.execute("""
        SELECT product_id, product_title, total_reviews, avg_star_rating as stars, negative_pct as neg_pct, neg_count
        FROM gold_scenario_c_catalog_purge
        ORDER BY total_reviews DESC, neg_pct DESC;
    """).df()
    
    st.write(f"##### Flagged for Catalog Purge ({len(df_lemons):,} Items)")
    st.dataframe(df_lemons.style.format({"stars": "{:.2f} ⭐", "neg_pct": "{:.1f}%"}), width="stretch", height=300)
    
    csv_data = df_lemons.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download De-listing Action List (CSV)",
        data=csv_data,
        file_name="aislewise_catalog_purge_list.csv",
        mime="text/csv"
    )

# --- TAB 4: REAL-TIME ASIN INSPECTOR ---
with tab_search:
    st.subheader("🔍 Live ASIN Deep Search & Sentiment Explorer")
    search_asin = st.text_input("Enter Product ASIN to inspect live (e.g., B0BDFT8DZR, B07JJQR94P, B005E0LBFY):", "").strip()
    
    if search_asin:
        p_info = con.execute(f"SELECT * FROM gold_product_discrepancy_flags WHERE product_id = '{search_asin}';").df()
        if not p_info.empty:
            p_row = p_info.iloc[0]
            st.markdown(f"**Classification:** `{p_row['flag']}` | **Stars:** ⭐ {p_row['avg_star_rating']} | **Positive:** {p_row['positive_pct']}% | **Negative:** {p_row['negative_pct']}%")
            
            reviews = con.execute(f"""
                SELECT rating, sentiment, verified_purchase, helpful_vote, title, text 
                FROM silver_reviews 
                WHERE product_id = '{search_asin}'
                ORDER BY helpful_vote DESC, rating ASC;
            """).df()
            
            st.write(f"##### Live Synced Customer Reviews ({len(reviews)} Total Records)")
            st.dataframe(reviews, width="stretch")
        else:
            st.warning(f"ASIN '{search_asin}' was not found in discrepancy flags.")

con.close()