"""
================================================================================
  La Bàn Chứng Khoán AI Pro - app.py
  Cấu trúc repo:
    app.py                  ← file này
    core/
      __init__.py
      ai_engine.py
      data_fetcher.py
    components/
      __init__.py
      chart_ui.py
      chatbot_ui.py
    locales/
      vi.json / en.json
    .streamlit/
      config.toml
  Chạy: streamlit run app.py
================================================================================
"""

import streamlit as st
import sys, os, json

# ── Đảm bảo thư mục gốc của repo luôn có trong sys.path ─────────────────────
# Cần thiết trên Streamlit Cloud
_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in [_ROOT, os.getcwd()]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Import từ các subfolder ───────────────────────────────────────────────────
try:
    from core.data_fetcher import get_stock_data
    from components.chart_ui import render_chart
    from components.chatbot_ui import render_chat_interface
    from core.ai_engine import get_ai_analysis
except ModuleNotFoundError as _e:
    st.error(f"""
**❌ Import lỗi: `{_e}`**

Kiểm tra repo của bạn có đủ các file sau không:
```
app.py
core/__init__.py
core/data_fetcher.py
core/ai_engine.py
components/__init__.py
components/chart_ui.py
components/chatbot_ui.py
```
Nếu thiếu `__init__.py` trong `core/` hoặc `components/`, hãy tạo file rỗng đó.
""")
    st.stop()

# ── Voice input (tuỳ chọn) ────────────────────────────────────────────────────
try:
    from streamlit_mic_recorder import speech_to_text
    VOICE_ENABLED = True
except ImportError:
    VOICE_ENABLED = False


# ══════════════════════════════════════════════════════════════════════════════
#  CẤU HÌNH TRANG & CSS
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="La Bàn Chứng Khoán Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Thu nhỏ metric cards */
    [data-testid="stMetricValue"] { font-size: 1.1rem !important; font-weight: 700; }
    [data-testid="stMetricDelta"] { font-size: 0.75rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.7rem !important; }
    div[data-testid="metric-container"] {
        background: #1E1E1E; border-radius: 8px;
        padding: 8px 10px !important; border: 1px solid #333;
    }
    /* Chatbot phân cách khỏi chart */
    .chatbot-section { margin-top: 2rem; border-top: 2px solid #F4A261; padding-top: 1rem; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TIỆN ÍCH: TẢI LOCALE & SMART ROUTING
# ══════════════════════════════════════════════════════════════════════════════
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
    "phân tích chung", "tổng quan",
]

def classify_input(text: str) -> str:
    """
    Smart Routing: Phân biệt mã cổ phiếu vs câu hỏi thị trường.
    Trả về: 'ticker' | 'general'
    """
    if not text:
        return "general"
    text_lower = text.lower().strip()
    words = text_lower.split()

    for kw in _GENERAL_KEYWORDS:
        if kw in text_lower:
            return "general"

    # 1 từ ngắn (≤6 ký tự), toàn chữ/số → mã ticker
    if len(words) == 1 and len(words[0]) <= 6 and words[0].isalnum():
        return "ticker"

    # 2 từ ngắn (VD: "TCB VN") → ticker + sàn
    if len(words) == 2 and all(len(w) <= 6 and w.isalnum() for w in words):
        return "ticker"

    return "general"


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
if "language" not in st.session_state:       st.session_state["language"] = "vi"
if "selected_model" not in st.session_state: st.session_state["selected_model"] = "gemini-2.0-flash"
if "market_region" not in st.session_state:  st.session_state["market_region"] = "VN"

loc = load_locales(st.session_state["language"])

with st.sidebar:
    st.title(loc.get("sidebar_title", "⚙️ Cài đặt"))

    # Ngôn ngữ
    lang_display = st.selectbox(
        loc.get("lang_select", "🌐 Ngôn ngữ:"),
        ["Tiếng Việt (vi)", "English (en)"]
    )
    new_lang = "vi" if "vi" in lang_display else "en"
    if new_lang != st.session_state["language"]:
        st.session_state["language"] = new_lang
        st.rerun()

    st.divider()

    # Khu vực thị trường
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

    # Cấu hình AI
    st.subheader(loc.get("ai_config", "🤖 Cấu hình AI"))
    model_map = {
        "⚡ Gemini 2.0 Flash (Nhanh)": "gemini-2.0-flash",
        "🧠 Gemini 2.0 Pro (Sâu)":    "gemini-2.0-pro-exp-02-05",
    }
    sel_label = st.selectbox(loc.get("model_select", "Chọn Model:"), list(model_map.keys()))
    st.session_state["selected_model"] = model_map[sel_label]

    st.divider()
    st.caption("📦 v2.1 | Subfolder Build")


# ══════════════════════════════════════════════════════════════════════════════
#  THANH TÌM KIẾM CHÍNH
# ══════════════════════════════════════════════════════════════════════════════
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

user_input = (form_input if form_input else voice_input) or ""
triggered  = submit_button or bool(voice_input)
lang_prompt = "Tiếng Việt" if st.session_state["language"] == "vi" else "English"


# ══════════════════════════════════════════════════════════════════════════════
#  LUỒNG XỬ LÝ CHÍNH — SMART ROUTING
# ══════════════════════════════════════════════════════════════════════════════
if triggered and user_input:
    input_type = classify_input(user_input)

    # ── NHÁNH A: Mã cổ phiếu ─────────────────────────────────────────────────
    if input_type == "ticker":
        ticker = user_input.upper().split()[0]
        region = st.session_state["market_region"]

        with st.spinner(f"📡 Đang tải dữ liệu {ticker}..."):
            data = get_stock_data(ticker, region=region)

        if "error" in data:
            st.error(f"❌ {data['error']}")
            st.info(
                "💡 Nếu bạn muốn hỏi về thị trường, hãy đặt câu hỏi dạng: "
                "*'Nhận định thị trường hôm nay'*"
            )
        else:
            # Metrics thu gọn 7 cột
            st.subheader(f"📊 {ticker} — {data.get('industry', '')}")
            m1, m2, m3, m4, m5, m6, m7 = st.columns(7)

            price = data.get('price', 0)
            unit  = " VNĐ" if region == "VN" else " USD"
            m1.metric(loc.get("price", "Giá"), f"{price:,.0f}{unit}")
            m2.metric(loc.get("volume", "KL"), f"{data.get('volume', 0):,}")
            m3.metric("Sàn", data.get('market', region))

            pe, avg_pe = data.get('pe', 'N/A'), data.get('avg_pe', 0) or 0
            pb, avg_pb = data.get('pb', 'N/A'), data.get('avg_pb', 0) or 0
            pe_d = round(float(pe) - avg_pe, 2) if pe != "N/A" and avg_pe else None
            pb_d = round(float(pb) - avg_pb, 2) if pb != "N/A" and avg_pb else None

            m4.metric(loc.get("pe_stock", "P/E"),      str(pe))
            m5.metric(loc.get("pe_avg",   "P/E Ngành"), str(avg_pe),
                      delta=pe_d, delta_color="inverse" if pe_d else "off")
            m6.metric(loc.get("pb_stock", "P/B"),      str(pb))
            m7.metric(loc.get("pb_avg",   "P/B Ngành"), str(avg_pb),
                      delta=pb_d, delta_color="inverse" if pb_d else "off")

            st.divider()

            # Chart — chiếm tối đa không gian
            st.subheader(loc.get("chart", "📊 Biểu đồ Kỹ thuật"))
            render_chart(ticker, exchange=data.get('market', 'HOSE'), region=region)

            # Chatbot — nằm hoàn toàn bên dưới chart
            st.markdown('<div class="chatbot-section">', unsafe_allow_html=True)
            st.subheader(loc.get("ai_analysis", "🤖 Trợ lý AI"))
            render_chat_interface(
                ticker=ticker, lang=lang_prompt,
                model=st.session_state["selected_model"],
                mode="ticker", stock_data=data
            )
            st.markdown('</div>', unsafe_allow_html=True)

    # ── NHÁNH B: Câu hỏi thị trường chung ────────────────────────────────────
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
        <p>Nhập <b>mã cổ phiếu</b> (VD: <code>FPT</code>, <code>AAPL</code>, <code>TCB</code>)
        để xem biểu đồ & phân tích AI</p>
        <p>Hoặc đặt <b>câu hỏi</b> (VD: <em>"Nhận định thị trường hôm nay"</em>)
        để hỏi AI trực tiếp</p>
    </div>
    """, unsafe_allow_html=True)
