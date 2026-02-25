"""
La Bàn Chứng Khoán AI Pro — app.py v2.5
"""

import streamlit as st
import sys, os, json

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in [_ROOT, os.getcwd()]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from core.data_fetcher import get_stock_data
    from components.chart_ui import render_chart
    from components.chatbot_ui import render_chat_interface
    from core.ai_engine import get_ai_analysis
except ModuleNotFoundError as _e:
    st.error(f"**❌ Import lỗi:** `{_e}`\n\nKiểm tra `core/__init__.py` và `components/__init__.py` đã có chưa.")
    st.stop()

try:
    from streamlit_mic_recorder import speech_to_text
    VOICE_ENABLED = True
except ImportError:
    VOICE_ENABLED = False

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="La Bàn Chứng Khoán Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.05rem !important; font-weight: 700; }
    [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.68rem !important; }
    div[data-testid="metric-container"] {
        background: #1a1a1a; border-radius: 8px;
        padding: 8px 10px !important; border: 1px solid #2e2e2e;
    }
    .chatbot-section { margin-top: 1.5rem; border-top: 2px solid #F4A261; padding-top: 1rem; }
    footer { visibility: hidden; }
    .stForm { border: none !important; }
</style>
""", unsafe_allow_html=True)


# ── Locale ────────────────────────────────────────────────────────────────────
@st.cache_data
def load_locales(lang_code: str) -> dict:
    path = os.path.join(_ROOT, "locales", f"{lang_code}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

_GENERAL_KEYWORDS = [
    "thị trường", "market", "nhận định", "lạm phát", "lãi suất", "kinh tế",
    "vĩ mô", "hôm nay", "tuần này", "tháng này", "xu hướng", "nên mua",
    "nên bán", "cổ phiếu nào", "gợi ý", "recommend", "inflation",
    "interest rate", "gdp", "fed", "ngân hàng", "strategy", "chiến lược",
    "danh mục", "portfolio", "rủi ro", "risk", "cơ hội", "opportunity",
    "phân tích chung", "tổng quan", "tổng kết", "diễn biến",
    "có gì", "thế nào", "ra sao", "như thế nào",
]

def classify_input(text: str) -> str:
    if not text:
        return "general"
    tl = text.lower().strip()
    words = tl.split()
    for kw in _GENERAL_KEYWORDS:
        if kw in tl:
            return "general"
    if len(words) == 1 and len(words[0]) <= 6 and words[0].isalnum():
        return "ticker"
    if len(words) == 2 and all(len(w) <= 6 and w.isalnum() for w in words):
        return "ticker"
    return "general"


# ── Session state defaults ────────────────────────────────────────────────────
if "language"       not in st.session_state: st.session_state["language"]       = "vi"
if "selected_model" not in st.session_state: st.session_state["selected_model"] = "gemini-2.0-flash"
if "market_region"  not in st.session_state: st.session_state["market_region"]  = "VN"

loc = load_locales(st.session_state["language"])


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title(loc.get("sidebar_title", "⚙️ Cài đặt"))

    lang_display = st.selectbox(
        loc.get("lang_select", "🌐 Ngôn ngữ:"),
        ["Tiếng Việt (vi)", "English (en)"]
    )
    new_lang = "vi" if "vi" in lang_display else "en"
    if new_lang != st.session_state["language"]:
        st.session_state["language"] = new_lang
        st.rerun()

    st.divider()

    st.subheader("🌍 Khu vực Thị trường")
    market_region = st.radio(
        "Chọn thị trường:",
        ["🇻🇳 Việt Nam (VN)", "🇺🇸 Mỹ (US)", "🌐 Quốc tế"]
    )
    if "Việt Nam" in market_region:
        st.session_state["market_region"] = "VN"
    elif "Mỹ" in market_region:
        st.session_state["market_region"] = "US"
    else:
        st.session_state["market_region"] = "INTL"

    if st.session_state["market_region"] == "VN":
        st.session_state["market_filter"] = st.radio(
            "Sàn giao dịch:", ["Tất cả", "HOSE", "HNX", "UPCOM"], horizontal=True
        )

    st.divider()

    st.subheader(loc.get("ai_config", "🤖 Cấu hình AI"))
    model_map = {
        "⚡ Gemini 2.0 Flash (Khuyên dùng)": "gemini-2.0-flash",
        "🧠 Gemini 2.0 Pro (Chậm hơn)":      "gemini-2.0-pro-exp-02-05",
        "✨ Gemini 1.5 Flash":                "gemini-1.5-flash",
    }
    # Tìm label hiện tại
    current_model = st.session_state["selected_model"]
    current_label = next(
        (k for k, v in model_map.items() if v == current_model),
        "⚡ Gemini 2.0 Flash (Khuyên dùng)"
    )
    sel_label = st.selectbox(
        loc.get("model_select", "Chọn Model:"),
        list(model_map.keys()),
        index=list(model_map.keys()).index(current_label)
    )
    st.session_state["selected_model"] = model_map[sel_label]

    # Cảnh báo nếu chọn Pro
    if "Pro" in sel_label:
        st.warning("⚠️ Pro có quota thấp hơn Flash (~2 req/phút trên Free Tier). Có thể bị Rate Limit.")

    st.divider()
    st.caption("📦 v2.5 | Subfolder Build")


# ── Main UI ───────────────────────────────────────────────────────────────────
st.title(loc.get("title", "📈 La Bàn Chứng Khoán AI Pro"))

with st.form(key="search_form", clear_on_submit=False):
    col_input, col_btn = st.columns([0.82, 0.18])
    with col_input:
        form_input = st.text_input(
            label="search", label_visibility="collapsed",
            placeholder="🔍 Nhập mã cổ phiếu (FPT, VND, AAPL...) hoặc câu hỏi thị trường",
        ).strip()
    with col_btn:
        submit_button = st.form_submit_button(
            loc.get("btn_analyze", "🔍 Phân tích"), use_container_width=True
        )

voice_input = None
if VOICE_ENABLED:
    st.caption("🎙️ Hoặc tìm bằng giọng nói:")
    voice_input = speech_to_text(
        language='vi-VN', start_prompt="Bấm để nói", stop_prompt="⏹️ Dừng", key='main_mic'
    )

user_input  = (form_input if form_input else voice_input) or ""
triggered   = submit_button or bool(voice_input)
lang_prompt = "Tiếng Việt" if st.session_state["language"] == "vi" else "English"


# ── Routing ───────────────────────────────────────────────────────────────────
if triggered and user_input:
    input_type = classify_input(user_input)

    # ── NHÁNH A: Mã cổ phiếu ──────────────────────────────────────────────────
    if input_type == "ticker":
        ticker = user_input.upper().split()[0]
        region = st.session_state["market_region"]

        with st.spinner(f"📡 Đang tải dữ liệu {ticker}..."):
            data = get_stock_data(ticker, region=region)

        if "error" in data:
            st.error(f"❌ {data['error']}")
            st.info("💡 Muốn hỏi thị trường? Ví dụ: *'Nhận định thị trường hôm nay'*")
        else:
            # Metrics
            st.subheader(f"📊 {ticker} — {data.get('industry', '')}")
            m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
            price = data.get('price', 0)
            unit  = " VNĐ" if region == "VN" else " USD"

            m1.metric(loc.get("price",    "Giá"),       f"{price:,.0f}{unit}")
            m2.metric(loc.get("volume",   "KL"),         f"{data.get('volume', 0):,}")
            m3.metric("Sàn",                              data.get('market', region))

            pe, avg_pe = data.get('pe', 'N/A'), data.get('avg_pe', 0) or 0
            pb, avg_pb = data.get('pb', 'N/A'), data.get('avg_pb', 0) or 0
            pe_d = round(float(pe) - float(avg_pe), 2) if pe != "N/A" and avg_pe else None
            pb_d = round(float(pb) - float(avg_pb), 2) if pb != "N/A" and avg_pb else None

            m4.metric(loc.get("pe_stock", "P/E"),       str(pe))
            m5.metric(loc.get("pe_avg",   "P/E Ngành"), str(avg_pe) if avg_pe else "N/A",
                      delta=pe_d, delta_color="inverse" if pe_d else "off")
            m6.metric(loc.get("pb_stock", "P/B"),       str(pb))
            m7.metric(loc.get("pb_avg",   "P/B Ngành"), str(avg_pb) if avg_pb else "N/A",
                      delta=pb_d, delta_color="inverse" if pb_d else "off")

            st.divider()

            # Chart
            st.subheader(loc.get("chart", "📊 Biểu đồ Kỹ thuật"))
            render_chart(ticker, exchange=data.get('market', 'HOSE'), region=region)

            # Chatbot
            st.markdown('<div class="chatbot-section">', unsafe_allow_html=True)
            st.subheader(loc.get("ai_analysis", "🤖 AI Phân tích"))
            render_chat_interface(
                ticker=ticker, lang=lang_prompt,
                model=st.session_state["selected_model"],
                mode="ticker", stock_data=data
            )
            st.markdown('</div>', unsafe_allow_html=True)

    # ── NHÁNH B: Câu hỏi thị trường chung ─────────────────────────────────────
    else:
        st.info(f"💡 **Chế độ: Phân tích thị trường chung** — *\"{user_input}\"*")
        st.divider()
        render_chat_interface(
            ticker="Thị trường", lang=lang_prompt,
            model=st.session_state["selected_model"],
            mode="general", initial_query=user_input
        )

elif not user_input:
    st.markdown("""
    <div style='text-align:center; padding: 3rem 1rem; color: #888;'>
        <h3 style='color:#F4A261'>📈 Chào mừng đến với La Bàn Chứng Khoán AI Pro</h3>
        <p>Nhập <b>mã cổ phiếu</b> (VD: <code>FPT</code>, <code>VND</code>, <code>MBB</code>)
        để xem biểu đồ & phân tích AI</p>
        <p>Hoặc đặt <b>câu hỏi</b> (VD: <em>"Nhận định thị trường hôm nay"</em>)
        để hỏi AI trực tiếp</p>
        <hr style='border-color:#333; margin: 1.5rem 0'>
        <p style='font-size:0.85rem'>
        💡 <b>Lưu ý:</b> Dùng model <b>Flash</b> (sidebar) để tránh Rate Limit.
        Free Tier giới hạn ~15 req/phút với Flash, ~2 req/phút với Pro.
        </p>
    </div>
    """, unsafe_allow_html=True)
