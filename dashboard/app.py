# dashboard/app.py  -- Retail Ops Intelligence with Voice-enabled Copilot

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from io import BytesIO
from typing import Generator
from datetime import datetime
import tempfile

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.io as pio
import streamlit.components.v1 as components

# ---------- Optional TTS (voice) – uses pyttsx3 if installed ----------
try:
    import pyttsx3
    tts_engine = pyttsx3.init()
    HAS_TTS = True
except Exception:
    tts_engine = None
    HAS_TTS = False

# ---------- Optional STT (mic) – uses streamlit-mic-recorder ----------
try:
    from streamlit_mic_recorder import speech_to_text
    HAS_STT = True
except Exception:
    HAS_STT = False

# ---------- backend imports (your project) ----------
from backend.db.db_utils import get_connection
from backend.ml.demand_forecast import moving_average_forecast
from backend.ml.alerts import generate_low_stock_alerts
from backend.rag.ops_copilot import answer_ops_question

# ----------------- PAGE CONFIG -----------------
st.set_page_config(
    page_title="Retail Ops Intelligence",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- SESSION STATE INIT (GLOBAL) -----------------
for key, default in {
    "copilot_messages": [],
    "copilot_audio": None,
    "copilot_input": "",
    "pending_question": None,    # question waiting for AI answer
    "stt_text": "",              # last mic transcript
    "clear_copilot_input": False # flag to safely clear text box
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ----------------- PLOTLY THEME -----------------
if "plotly_dark" in pio.templates:
    base = pio.templates["plotly_dark"]
else:
    base = pio.templates.default

pio.templates["retail_theme"] = base
theme = pio.templates["retail_theme"]

try:
    theme.layout.font.family = "Inter, Roboto, system-ui, sans-serif"
    theme.layout.font.size = 13
except Exception:
    theme["layout"]["font"] = dict(family="Inter, Roboto, system-ui, sans-serif", size=13)

theme.layout.paper_bgcolor = "rgba(0,0,0,0)"
theme.layout.plot_bgcolor = "rgba(0,0,0,0)"
theme.layout.colorway = ["#4C8BF5", "#7F7FFF", "#FF9F43", "#6BE3B6", "#FF7AB6"]

pio.templates.default = "retail_theme"

# ----------------- GLOBAL CSS / THEME -----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');

.block-container { padding: 4.5rem 2.5rem 2rem 2.5rem; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#07080a 0%, #0d0f12 100%);
    padding-top: 88px;
    border-right: 1px solid rgba(255,255,255,0.03);
}

/* KPI card */
.kpi-card {
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
    padding: 16px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.04);
    box-shadow: 0 8px 30px rgba(0,0,0,0.6);
}
.kpi-label { font-size:13px; color:#9aa7bf; margin-bottom:6px; }
.kpi-value { font-size:32px; font-weight:800; color:#4C8BF5; }

.panel {
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
    padding:18px; border-radius:12px; border:1px solid rgba(255,255,255,0.03);
}

/* Chat UI */
.chat-container {
    max-height: 62vh;
    overflow-y: auto;
    padding: 12px;
    border-radius: 10px;
    background: rgba(0,0,0,0.12);
    border: 1px solid rgba(255,255,255,0.02);
}
.msg { margin: 10px 0; display:flex; width:100%; opacity:0; transform: translateY(6px); animation: fadeInUp 0.22s forwards; }
@keyframes fadeInUp { to { opacity: 1; transform: translateY(0px); } }
.msg.ai { justify-content:flex-start; }
.msg.user { justify-content:flex-end; }
.bubble {
    max-width:78%;
    padding:12px 14px;
    border-radius: 14px;
    line-height:1.4;
    font-family: Inter, sans-serif;
    font-size:14px;
}
.bubble.ai {
    background: linear-gradient(180deg,#0f1724,#0b1220);
    border: 1px solid rgba(255,255,255,0.03);
    color: #e6eef8;
    border-bottom-left-radius: 6px;
}
.bubble.user {
    background: linear-gradient(90deg,#4C8BF5,#7F7FFF);
    color: white;
    border-bottom-right-radius: 6px;
}
.msg-ts { font-size:11px; color:#9aa7bf; margin-top:6px; }

/* input area */
.input-textarea {
    width:100%;
    height:90px;
    border-radius:10px;
    padding:12px;
    background: rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.03);
    color: #e6eef8;
}
.btn-primary {
    background: linear-gradient(90deg,#4C8BF5,#7F7FFF);
    color:white; border:none; padding:10px 16px; border-radius:10px; font-weight:600;
}

.small-muted { color:#9aa7bf; font-size:13px; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ----------------- THREE.JS WIDGET -----------------
threejs_html = r"""
<div id="threejs-container" style="width:100%;height:220px;border-radius:10px;overflow:hidden"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r152/three.min.js"></script>
<script>
const container = document.getElementById('threejs-container');
const width = container.clientWidth || 400;
const height = container.clientHeight || 220;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, width/height, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(width, height);
container.appendChild(renderer.domElement);
const cube = new THREE.Mesh(new THREE.BoxGeometry(1.4,1.4,1.4), new THREE.MeshStandardMaterial({ color:0x4C8BF5, metalness:0.5, roughness:0.25 }));
scene.add(cube);
scene.add(new THREE.AmbientLight(0xffffff,0.35));
let dl = new THREE.DirectionalLight(0xffffff,1); dl.position.set(5,5,5); scene.add(dl);
camera.position.z = 4;
function animate(){ requestAnimationFrame(animate); cube.rotation.x += 0.008; cube.rotation.y += 0.01; renderer.render(scene,camera); }
animate();
</script>
"""

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.markdown("<div style='display:flex;align-items:center;gap:12px;margin-bottom:6px'>"
                "<div style='font-size:20px;font-weight:800;color:#fff'>🛒 Retail Ops Intelligence</div>"
                "</div>", unsafe_allow_html=True)
    st.markdown("---")
    page = st.radio(
        "Go to",
        [
            "Store Overview",
            "Inventory & Alerts",
            "Incidents & Store Health",
            "Demand Forecasting",
            "Customer Segmentation",
            "Ops Copilot (AI)"
        ],
        index=0
    )
    st.markdown("---")
    components.html(threejs_html, height=220)
    st.markdown("---")
    st.markdown("<div class='small-muted'>Built with Python · Streamlit · Groq LLM · Voice</div>", unsafe_allow_html=True)


# ----------------- HELPERS -----------------
def get_store_list():
    try:
        conn = get_connection()
        if not conn:
            return pd.DataFrame()
        df = pd.read_sql("SELECT store_id, store_name FROM stores ORDER BY store_id;", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def get_product_list():
    try:
        conn = get_connection()
        if not conn:
            return pd.DataFrame()
        df = pd.read_sql("SELECT product_id, product_name FROM products ORDER BY product_id;", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def render_kpi(label, value, subtitle=None):
    subtitle_html = f"<div class='small-muted' style='margin-top:8px'>{subtitle}</div>" if subtitle else ""
    st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-value'>{value}</div>
            {subtitle_html}
        </div>
    """, unsafe_allow_html=True)


def generate_tts_audio(text: str):
    """Generate WAV audio bytes from text using pyttsx3 if available."""
    if not HAS_TTS or not text:
        return None
    try:
        trimmed = text.strip()
        if len(trimmed) > 800:
            trimmed = trimmed[:800] + " ..."

        # Use a temporary WAV file, then load bytes
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp_path = tmp.name

        tts_engine.save_to_file(trimmed, tmp_path)
        tts_engine.runAndWait()

        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()

        try:
            os.remove(tmp_path)
        except Exception:
            pass

        return audio_bytes
    except Exception:
        return None


# ----------------- PAGES -----------------
# Store Overview
if page == "Store Overview":
    st.markdown("<div style='padding-top:6px'></div>", unsafe_allow_html=True)
    st.markdown("<h1 style='font-weight:800;color:#fff;margin-bottom:0'>🏬 Store Overview</h1>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted'>Executive KPIs, sales by store and daily trends</div>", unsafe_allow_html=True)

    conn = get_connection()
    if not conn:
        st.error("Could not connect to database.")
    else:
        with st.spinner("Loading KPIs and charts..."):
            try:
                df_total = pd.read_sql(
                    "SELECT COALESCE(SUM(total_amount),0) as total_sales, COUNT(*) as total_txns FROM sales_transactions;",
                    conn
                )
            except Exception:
                df_total = pd.DataFrame([{"total_sales": 0, "total_txns": 0}])
            try:
                df_store = pd.read_sql(
                    """
                    SELECT s.store_name, SUM(t.total_amount) as store_sales, COUNT(*) as txns
                    FROM sales_transactions t
                    JOIN stores s ON t.store_id = s.store_id
                    GROUP BY s.store_name
                    ORDER BY store_sales DESC;
                    """,
                    conn
                )
            except Exception:
                df_store = pd.DataFrame(columns=["store_name", "store_sales", "txns"])
            try:
                df_daily = pd.read_sql(
                    """
                    SELECT DATE(txn_timestamp) as sale_date, SUM(total_amount) as sales
                    FROM sales_transactions
                    GROUP BY DATE(txn_timestamp)
                    ORDER BY sale_date;
                    """,
                    conn
                )
            except Exception:
                df_daily = pd.DataFrame(columns=["sale_date", "sales"])
            conn.close()

        total_sales = int(df_total['total_sales'].iloc[0]) if not df_total.empty else 0
        total_txns = int(df_total['total_txns'].iloc[0]) if not df_total.empty else 0
        avg_txn = int(total_sales / total_txns) if total_txns > 0 else 0

        c1, c2, c3 = st.columns([1.8, 1, 1])
        with c1:
            render_kpi("Total Sales (₹)", f"{total_sales:,}", "Period: All time (demo data)")
        with c2:
            render_kpi("Total Transactions", f"{total_txns:,}")
        with c3:
            render_kpi("Avg Transaction (₹)", f"{avg_txn:,}")

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='panel'><h3 style='margin-top:0'>Sales by Store</h3>", unsafe_allow_html=True)
        if not df_store.empty:
            fig_store = px.bar(
                df_store,
                x="store_name",
                y="store_sales",
                text="store_sales",
                labels={"store_name": "Store", "store_sales": "Sales"}
            )
            fig_store.update_layout(margin=dict(l=0, r=0, t=8, b=0), height=380)
            fig_store.update_traces(marker_color='#4C8BF5')
            st.plotly_chart(fig_store, width="stretch")
        else:
            st.info("No store sales data available.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='panel'><h3 style='margin-top:0'>Daily Sales Trend</h3>", unsafe_allow_html=True)
        if not df_daily.empty:
            fig_daily = px.line(df_daily, x="sale_date", y="sales")
            fig_daily.update_layout(margin=dict(l=0, r=0, t=8, b=0), height=300)
            st.plotly_chart(fig_daily, width="stretch")
        else:
            st.info("No daily sales data available.")
        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("Show raw tables"):
            if not df_store.empty:
                st.dataframe(df_store)
            if not df_daily.empty:
                st.dataframe(df_daily)

# Inventory & Alerts
elif page == "Inventory & Alerts":
    st.markdown("<h1 style='font-weight:800;color:#fff'>📦 Inventory Intelligence & Alerts</h1>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted'>Low-stock alerts and snapshot across stores</div>", unsafe_allow_html=True)

    threshold = st.slider("Low-stock threshold", min_value=5, max_value=200, value=20, key="low_stock_th")
    st.write(f"Current threshold: **{threshold} units**")

    if st.button("Generate Low-Stock Alerts"):
        with st.spinner("Generating alerts..."):
            try:
                df_low = generate_low_stock_alerts(threshold)
            except Exception as e:
                st.error(f"Alert generation error: {e}")
                df_low = pd.DataFrame()
            if df_low is None or df_low.empty:
                st.success("No low-stock items detected ✅")
            else:
                st.warning("Low-stock items detected:")
                st.dataframe(df_low)

    conn = get_connection()
    if not conn:
        st.error("DB connection failed.")
    else:
        try:
            df_inv = pd.read_sql("""
                SELECT i.store_id, s.store_name, i.product_id, p.product_name,
                       i.on_hand_qty, i.on_order_qty
                FROM inventory_snapshots i
                JOIN stores s ON i.store_id = s.store_id
                JOIN products p ON i.product_id = p.product_id
                WHERE i.snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshots)
                ORDER BY s.store_name, p.product_name;
            """, conn)
        except Exception:
            df_inv = pd.DataFrame()
        conn.close()

        st.markdown("<div class='panel'><h3 style='margin-top:0'>Latest Inventory Snapshot</h3>", unsafe_allow_html=True)
        if not df_inv.empty:
            st.dataframe(df_inv)
            fig_inv = px.bar(
                df_inv,
                x="product_name",
                y="on_hand_qty",
                color="store_name",
                labels={"on_hand_qty": "On-hand qty", "product_name": "Product"},
                title="On-hand quantity by product & store"
            )
            fig_inv.update_layout(height=350)
            st.plotly_chart(fig_inv, width="stretch")
        else:
            st.info("No inventory snapshot available.")
        st.markdown("</div>", unsafe_allow_html=True)

# Incidents & Store Health
elif page == "Incidents & Store Health":
    st.markdown("<h1 style='font-weight:800;color:#fff'>🚨 Incidents & Store Health</h1>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted'>Track incidents, SLA and store health at a glance</div>", unsafe_allow_html=True)

    conn = get_connection()
    if not conn:
        st.error("DB connection failed.")
    else:
        try:
            df_inc_store = pd.read_sql("""
                SELECT s.store_name,
                       COUNT(*) as total_incidents,
                       AVG(TIMESTAMPDIFF(HOUR, created_at, resolved_at)) as avg_resolution_hours
                FROM incidents i
                JOIN stores s ON i.store_id = s.store_id
                GROUP BY s.store_name;
            """, conn)
        except Exception:
            df_inc_store = pd.DataFrame()
        try:
            df_recent = pd.read_sql("""
                SELECT i.incident_id, s.store_name, i.created_at, i.resolved_at,
                       i.incident_type, i.severity, i.status
                FROM incidents i
                JOIN stores s ON i.store_id = s.store_id
                ORDER BY i.created_at DESC
                LIMIT 50;
            """, conn)
        except Exception:
            df_recent = pd.DataFrame()
        conn.close()

        st.markdown("<div class='panel'><h3 style='margin-top:0'>Store Health Summary</h3>", unsafe_allow_html=True)
        if not df_inc_store.empty:
            st.dataframe(df_inc_store)
        else:
            st.info("No incidents summary data.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='panel'><h3 style='margin-top:0'>Recent Incidents (Last 50)</h3>", unsafe_allow_html=True)
        if not df_recent.empty:
            st.dataframe(df_recent)
        else:
            st.info("No recent incidents.")
        st.markdown("</div>", unsafe_allow_html=True)

# Demand Forecasting
elif page == "Demand Forecasting":
    st.markdown("<h1 style='font-weight:800;color:#fff'>📈 Demand Forecasting (Moving Average)</h1>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted'>Quick, interpretable short-term forecast for replenishment planning</div>", unsafe_allow_html=True)

    stores_df = get_store_list()
    products_df = get_product_list()
    if stores_df.empty or products_df.empty:
        st.error("No stores or products found in DB.")
        st.stop()

    store_name = st.selectbox("Select Store", stores_df["store_name"])
    product_name = st.selectbox("Select Product", products_df["product_name"])
    horizon = st.slider("Forecast Horizon (days)", 3, 30, 7)

    store_id = int(stores_df.loc[stores_df["store_name"] == store_name, "store_id"].iloc[0])
    product_id = int(products_df.loc[products_df["product_name"] == product_name, "product_id"].iloc[0])

    if st.button("Run Forecast"):
        with st.spinner("Running forecast..."):
            try:
                hist_df, forecast_df = moving_average_forecast(store_id, product_id, window=7, horizon=horizon)
            except Exception as e:
                st.error(f"Forecast error: {e}")
                hist_df, forecast_df = pd.DataFrame(), pd.DataFrame()
            if hist_df is None or hist_df.empty:
                st.error("Not enough data to forecast for this store/product.")
            else:
                tab_hist, tab_forecast = st.tabs(["📉 Historical Demand", "🔮 Forecast"])
                with tab_hist:
                    st.markdown("**Historical daily demand**")
                    fig_hist = px.line(hist_df, x="sale_date", y="qty", title="Historical Demand")
                    st.plotly_chart(fig_hist, width="stretch")
                with tab_forecast:
                    st.markdown("**Forecasted demand**")
                    st.dataframe(forecast_df)
                    figf = px.line(forecast_df, x="sale_date", y="forecast_qty", title="Forecast")
                    st.plotly_chart(figf, width="stretch")

# Customer Segmentation
elif page == "Customer Segmentation":
    st.markdown("<h1 style='font-weight:800;color:#fff'>👥 Customer Segmentation (RFM + KMeans)</h1>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted'>Compute customer segments using Recency, Frequency & Monetary value.</div>", unsafe_allow_html=True)

    k = st.slider("Number of segments (K)", min_value=2, max_value=8, value=4)
    run_btn = st.button("Run Segmentation")
    if run_btn:
        with st.spinner("Computing RFM and clustering..."):
            try:
                from backend.ml.customer_segmentation import compute_rfm
                rfm_df, cluster_summary, sil = compute_rfm(k=k)
            except Exception as e:
                st.error(f"Segmentation error: {e}")
                rfm_df, cluster_summary, sil = pd.DataFrame(), pd.DataFrame(), None

        if rfm_df is None or rfm_df.empty:
            st.info("No customer data found or segmentation failed.")
        else:
            st.success("Segmentation completed.")
            if sil is not None:
                st.markdown(f"**Silhouette Score:** {sil:.3f}")
            else:
                st.markdown("**Silhouette Score:** N/A")
            st.markdown("### Cluster Summary")
            st.dataframe(cluster_summary)

            seg_counts = rfm_df.groupby("segment_name")["customer_id"].count().reset_index().rename(columns={"customer_id": "count"})
            fig = px.pie(seg_counts, names="segment_name", values="count", title="Customer Segment Distribution")
            st.plotly_chart(fig, width="stretch")

            rfm_df["monetary_log"] = np.log1p(rfm_df["monetary"])
            fig2 = px.scatter(
                rfm_df,
                x="recency",
                y="monetary",
                color="segment_name",
                hover_data=["customer_id", "frequency", "monetary"],
                labels={"recency": "Recency (days)", "monetary": "Monetary (₹)"},
                title="Recency vs Monetary (colored by segment)"
            )
            st.plotly_chart(fig2, width="stretch")

            st.markdown("### Top customers in each segment")
            with st.expander("Show top customers per segment"):
                for seg in sorted(rfm_df["segment"].unique()):
                    name = rfm_df.loc[rfm_df["segment"] == seg, "segment_name"].iloc[0]
                    st.markdown(f"**Segment: {name} (id={seg})**")
                    top = rfm_df[rfm_df["segment"] == seg].sort_values("monetary", ascending=False).head(10)
                    st.dataframe(top[["customer_id", "recency", "frequency", "monetary", "segment_name"]])

# Ops Copilot (AI) with mic + voice reply
elif page == "Ops Copilot (AI)":
    st.markdown("<div style='padding-top:6px'></div>", unsafe_allow_html=True)
    st.markdown("<h1 style='font-weight:800;color:#fff'>🤖 Ops Copilot (AI)</h1>", unsafe_allow_html=True)
    st.markdown("<div class='small-muted'>Ask operations questions by text or voice. Copilot will answer and speak back.</div>", unsafe_allow_html=True)

    # ---- safely clear text input before creating the widget ----
    if st.session_state.get("clear_copilot_input"):
        st.session_state.copilot_input = ""
        st.session_state.clear_copilot_input = False

    left_col, right_col = st.columns([0.62, 0.38])

    # ---------- LEFT: Chat + input (text + mic) ----------
    with left_col:
        # Chat history
        st.markdown("<div class='chat-container' id='chatbox'>", unsafe_allow_html=True)
        for msg in st.session_state.copilot_messages:
            role = msg.get("role", "ai")
            text = msg.get("text", "")
            ts = msg.get("ts", "")
            ts_html = f"<div class='msg-ts'>{ts}</div>" if ts else ""
            if role == "ai":
                st.markdown(
                    f"<div class='msg ai'><div><div class='bubble ai'>{text}</div>{ts_html}</div></div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"<div class='msg user'><div><div class='bubble user'>{text}</div>{ts_html}</div></div>",
                    unsafe_allow_html=True
                )
        st.markdown("</div>", unsafe_allow_html=True)

        # auto-scroll script
        components.html("""
            <script>
            setTimeout(function() {
                var el = window.parent.document.getElementById('chatbox');
                if (el) { el.scrollTop = el.scrollHeight; }
            }, 150);
            </script>
        """, height=0)

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        # ----- Input row: text area + mic (like ChatGPT) -----
        col_input, col_mic = st.columns([5, 1])

        # MIC column FIRST in logic so it can update state before text widget
        with col_mic:
            if HAS_STT:
                st.markdown("<div class='small-muted' style='margin-bottom:3px'>&nbsp;</div>", unsafe_allow_html=True)
                stt_result = speech_to_text(
                    start_prompt="🎙️",
                    stop_prompt="■",
                    just_once=True,
                    use_container_width=True,
                    key="stt_mic"
                )
                # speech_to_text returns a plain string when recording stops
                if stt_result:
                    transcript = str(stt_result).strip()
                    if transcript:
                        # Immediately send as a question (no need to click Ask)
                        st.session_state.copilot_messages.append({
                            "role": "user",
                            "text": transcript,
                            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "meta": None
                        })
                        st.session_state.pending_question = transcript
                        st.session_state.copilot_input = ""  # safe here (before text_area)
                        st.session_state.stt_text = transcript
                        st.session_state.copilot_audio = None
                        st.rerun()
            else:
                st.markdown("<div class='small-muted'>Install <code>streamlit-mic-recorder</code> for mic.</div>", unsafe_allow_html=True)

        with col_input:
            question = st.text_area(
                "Your question",
                key="copilot_input",
                height=90,
                placeholder="E.g. Why did sales drop yesterday? Which store needs attention?"
            )

        ask_btn = st.button("Ask Copilot")

        # when Ask clicked -> create user message & mark pending_question, then rerun
        if ask_btn:
            q = str(question).strip()
            if not q:
                st.warning("Please enter a question or use the mic.")
            else:
                st.session_state.copilot_messages.append({
                    "role": "user",
                    "text": q,
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "meta": None
                })
                st.session_state.pending_question = q
                st.session_state.copilot_audio = None
                # mark to clear text box on next run (before widget is created)
                st.session_state.clear_copilot_input = True
                st.session_state.stt_text = ""
                st.rerun()

    # ---------- RIGHT: Insights + Audio ----------
    with right_col:
        st.markdown("<div class='panel'><h4 style='margin-top:0'>Copilot Insights</h4>", unsafe_allow_html=True)

        # get last ai meta
        last_ai_meta = None
        for m in reversed(st.session_state.copilot_messages):
            if m.get("role") == "ai" and m.get("meta"):
                last_ai_meta = m["meta"]
                break

        def render_insights(meta):
            if not meta:
                st.markdown("<div class='small-muted'>Copilot will surface KPIs, tables and charts here.</div>", unsafe_allow_html=True)
                return
            if "kpis" in meta:
                kpis = meta["kpis"]
                cols = st.columns(len(kpis))
                for (label, val), col in zip(kpis.items(), cols):
                    col.markdown(
                        f"<div class='kpi-card'><div class='kpi-label'>{label}</div><div class='kpi-value'>{val}</div></div>",
                        unsafe_allow_html=True
                    )
            if "tables" in meta:
                for tbl in meta["tables"]:
                    try:
                        st.dataframe(pd.DataFrame(tbl))
                    except Exception:
                        st.write(tbl)
            if "charts" in meta:
                for ch in meta["charts"]:
                    df = pd.DataFrame(ch.get("data", []))
                    if ch.get("type") == "bar":
                        fig_bar = px.bar(df, x=ch.get("x"), y=ch.get("y"), color=ch.get("color"))
                        st.plotly_chart(fig_bar, width="stretch")
                    elif ch.get("type") == "line":
                        fig_line = px.line(df, x=ch.get("x"), y=ch.get("y"))
                        st.plotly_chart(fig_line, width="stretch")

        render_insights(last_ai_meta)

    

        st.markdown("</div>", unsafe_allow_html=True)

    # ---------- HANDLE PENDING QUESTION (AI CALL + TTS) ----------
    if st.session_state.pending_question:
        qtext = st.session_state.pending_question
        try:
            response = answer_ops_question(qtext)
        except Exception as e:
            response = {"text": f"AI Error: {e}", "meta": None}

        ai_msg = {
            "role": "ai",
            "text": "",
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "meta": None
        }

        # response can be dict {"text": "...", "meta": {...}} or plain string
        if isinstance(response, dict):
            ai_msg["text"] = response.get("text", "")
            ai_msg["meta"] = response.get("meta", None)
        else:
            ai_msg["text"] = str(response)

        # append AI message with meta so insights update every time
        st.session_state.copilot_messages.append(ai_msg)

        # generate TTS for this answer
        audio = generate_tts_audio(ai_msg["text"])
        if audio:
            st.session_state.copilot_audio = audio

        # clear pending flag and rerun to show answer + insights
        st.session_state.pending_question = None
        st.rerun()


# ----------------- FOOTER -----------------
st.markdown("---")
st.markdown(
    "<div style='display:flex;justify-content:space-between;color:#8892a6;font-size:13px;'>"
    "<div>Retail Ops Intelligence • Demo</div>"
    "<div>Data: synthetic demo • UI: Streamlit + Plotly • Voice-enabled Copilot</div>"
    "</div>",
    unsafe_allow_html=True
)
