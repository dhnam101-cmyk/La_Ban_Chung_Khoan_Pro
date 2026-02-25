"""
================================================================================
  La Bàn Chứng Khoán AI Pro - app.py (Entry Point)
  Cấu trúc phẳng (flat): Tất cả file .py nằm cùng thư mục gốc repo.
  Chạy bằng: streamlit run app.py
================================================================================
"""

import streamlit as st
import sys, os, json

# ── Đảm bảo Python tìm được các module trong cùng thư mục ────────────────────
# Cần thiết trên Streamlit Cloud vì CWD có thể khác __file__
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
# Cũng thêm CWD phòng trường hợp Streamlit Cloud thay đổi working directory
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

# ── Import các module nội bộ (với thông báo lỗi rõ ràng) ─────────────────────
try:
    from data_fetcher import get_stock_data
    from chart_ui import render_chart
    from chatbot_ui import render_chat_interface
    from ai_engine import get_ai_analysis
except ModuleNotFoundError as _import_err:
    st.error(f"""
**❌ Lỗi Import Module: `{_import_err}`**

**Nguyên nhân thường gặp trên Streamlit Cloud:**
Các file sau phải nằm **cùng thư mục gốc** của repo (không được để trong subfolder):
- `app.py`
- `data_fetcher.py`
- `chart_ui.py`
- `chatbot_ui.py`
- `ai_engine.py`

**Kiểm tra GitHub repo của bạn** — nếu còn thư mục `core/` hoặc `components/`, 
hãy move các file ra ngoài thư mục gốc rồi commit lại.
""")
    st.stop()

# ── Import thư viện voice (bắt lỗi nếu chưa cài) ─────────────────────────────
try:
    from streamlit_mic_recorder import speech_to_text
    VOICE_ENABLED = True
except ImportError:
    VOICE_ENABLED = False

# ══════════════════════════════════════════════════════════════════════════════
#  PHẦN 1: CẤU HÌNH TRANG & CSS TOÀN CỤC
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
    /* Phóng to khu vực chart */
    .chart-wrapper { margin: 0 -1rem; }
    /* Chatbot nằm dưới cùng, phân cách rõ ràng */
    .chatbot-section { margin-top: 2rem; border-top: 2px solid #F4A261; padding-top: 1rem; }
    /* Ẩn footer mặc định của Streamlit */
    footer { visibility: hidden; }
    /* Thanh tìm kiếm to hơn */
    div[data-testid="stTextInput"] input { font-size: 1.1rem !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PHẦN 2: HÀM TIỆN ÍCH - TẢI LOCALE & PHÂN LOẠI INPUT
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data
def load_locales(lang_code: str) -> dict:
    """Tải file ngôn ngữ từ thư mục locales/"""
    file_path = os.path.join(os.path.dirname(__file__), "locales", f"{lang_code}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# Danh sách từ khóa gợi ý query chung (không phải mã cổ phiếu)
_GENERAL_KEYWORDS = [
    "thị trường", "market", "nhận định", "lạm phát", "lãi suất", "kinh tế",
    "vĩ mô", "hôm nay", "tuần này", "tháng này", "phân tích", "xu hướng",
    "nên mua", "nên bán", "cổ phiếu nào", "gợi ý", "recommend", "inflation",
    "interest rate", "gdp", "fed", "ngân hàng", "strategy", "chiến lược",
    "danh mục", "portfolio", "rủi ro", "risk", "cơ hội", "opportunity"
]

def classify_input(text: str) -> str:
    """
    Smart Routing: Phân loại đầu vào của người dùng.
    Trả về: 'ticker' nếu là mã cổ phiếu, 'general' nếu là câu hỏi chung.
    Logic:
      - Mã ticker: 1-2 từ, ngắn (≤ 6 ký tự/từ), không chứa keyword chung.
      - Câu hỏi chung: Nhiều từ HOẶC chứa keyword từ _GENERAL_KEYWORDS.
    """
    if not text:
        return "general"
    
    text_lower = text.lower().strip()
    words = text_lower.split()
    
    # Nếu chứa keyword chung → query thị trường
    for kw in _GENERAL_KEYWORDS:
        if kw in text_lower:
            return "general"
    
    # Nếu là 1 từ ngắn (≤ 6 ký tự) và toàn chữ/số → khả năng cao là mã ticker
    if len(words) == 1 and len(words[0]) <= 6 and words[0].isalnum():
        return "ticker"
    
    # Nếu 2 từ, cả 2 đều ngắn (ví dụ "TCB VN") → có thể là ticker với sàn
    if len(words) == 2 and all(len(w) <= 6 and w.isalnum() for w in words):
        return "ticker"
    
    # Mặc định: Nếu nhiều hơn 2 từ → câu hỏi chung
    return "general"


# ══════════════════════════════════════════════════════════════════════════════
#  PHẦN 3: SIDEBAR - CÀI ĐẶT HỆ THỐNG
# ══════════════════════════════════════════════════════════════════════════════
# Khởi tạo session state
if "language" not in st.session_state:       st.session_state["language"] = "vi"
if "selected_model" not in st.session_state: st.session_state["selected_model"] = "gemini-2.0-flash"
if "market_region" not in st.session_state:  st.session_state["market_region"] = "VN"

loc = load_locales(st.session_state["language"])

with st.sidebar:
    st.title(loc.get("sidebar_title", "⚙️ Cài đặt"))
    
    # ── Chọn ngôn ngữ ────────────────────────────────────────────────────────
    lang_opts = ["Tiếng Việt (vi)", "English (en)"]
    lang_display = st.selectbox(loc.get("lang_select", "🌐 Ngôn ngữ:"), lang_opts)
    new_lang = "vi" if "vi" in lang_display else "en"
    if new_lang != st.session_state["language"]:
        st.session_state["language"] = new_lang
        st.rerun()
    
    st.divider()
    
    # ── Chọn khu vực thị trường (Market Region) ───────────────────────────────
    st.subheader("🌍 Khu vực Thị trường")
    market_region = st.radio(
        "Chọn thị trường:",
        options=["🇻🇳 Việt Nam (VN)", "🇺🇸 Mỹ (US)", "🌐 Quốc tế"],
        index=0
    )
    # Lưu region code
    if "Việt Nam" in market_region or "VN" in market_region:
        st.session_state["market_region"] = "VN"
    elif "Mỹ" in market_region or "US" in market_region:
        st.session_state["market_region"] = "US"
    else:
        st.session_state["market_region"] = "INTL"
    
    # ── Chọn sàn (chỉ hiển thị nếu là thị trường VN) ─────────────────────────
    if st.session_state["market_region"] == "VN":
        st.session_state["market_filter"] = st.radio(
            "Sàn giao dịch:",
            ["Tất cả", "HOSE", "HNX", "UPCOM"],
            horizontal=True
        )
    
    st.divider()
    
    # ── Cấu hình AI ───────────────────────────────────────────────────────────
    st.subheader(loc.get("ai_config", "🤖 Cấu hình AI"))
    model_map = {
        "⚡ Gemini 2.0 Flash (Nhanh)": "gemini-2.0-flash",
        "🧠 Gemini 2.0 Pro (Sâu)":    "gemini-2.0-pro-exp-02-05"
    }
    sel_model_label = st.selectbox(
        loc.get("model_select", "Chọn Model:"),
        options=list(model_map.keys())
    )
    st.session_state["selected_model"] = model_map[sel_model_label]
    
    st.divider()
    st.caption("📦 v2.0 | Refactored & Bug-fixed")


# ══════════════════════════════════════════════════════════════════════════════
#  PHẦN 4: TIÊU ĐỀ & THANH TÌM KIẾM CHÍNH
# ══════════════════════════════════════════════════════════════════════════════
st.title(loc.get("title", "📈 La Bàn Chứng Khoán AI Pro"))

# Form tìm kiếm (hỗ trợ Enter)
with st.form(key="search_form", clear_on_submit=False):
    col_input, col_btn = st.columns([0.82, 0.18])
    with col_input:
        form_input = st.text_input(
            label="search",
            label_visibility="collapsed",
            placeholder="🔍 Nhập mã cổ phiếu (FPT, VND, AAPL...) hoặc câu hỏi thị trường",
        ).strip()
    with col_btn:
        submit_button = st.form_submit_button(
            loc.get("btn_analyze", "🔍 Phân tích"),
            use_container_width=True
        )

# Voice input (tùy chọn)
voice_input = None
if VOICE_ENABLED:
    st.caption("🎙️ Hoặc tìm bằng giọng nói:")
    voice_input = speech_to_text(
        language='vi-VN',
        start_prompt="Bấm để nói",
        stop_prompt="⏹️ Dừng",
        key='main_mic'
    )

# ── Xác định input cuối cùng ─────────────────────────────────────────────────
user_input = (form_input if form_input else voice_input) or ""
triggered = submit_button or bool(voice_input)

lang_prompt = "Tiếng Việt" if st.session_state["language"] == "vi" else "English"


# ══════════════════════════════════════════════════════════════════════════════
#  PHẦN 5: LUỒNG XỬ LÝ CHÍNH - SMART ROUTING
# ══════════════════════════════════════════════════════════════════════════════
if triggered and user_input:
    
    input_type = classify_input(user_input)
    
    # ──────────────────────────────────────────────────────────────────────────
    #  NHÁNH A: MÃ CỔ PHIẾU CỤ THỂ
    # ──────────────────────────────────────────────────────────────────────────
    if input_type == "ticker":
        ticker = user_input.upper().split()[0]  # Lấy mã đầu tiên
        region = st.session_state["market_region"]
        
        with st.spinner(f"📡 Đang tải dữ liệu {ticker}..."):
            data = get_stock_data(ticker, region=region)
        
        # ── Bắt lỗi không tìm thấy mã ────────────────────────────────────────
        if "error" in data:
            st.error(f"❌ {data['error']}")
            st.info(
                "💡 **Gợi ý:** Kiểm tra lại mã cổ phiếu. Nếu bạn muốn hỏi về thị trường, "
                "hãy đặt câu hỏi dạng: *'Nhận định thị trường hôm nay'*"
            )
        else:
            # ── Metrics: Thu gọn, hiển thị dạng hàng ngang ───────────────────
            st.subheader(f"📊 {ticker} — {data.get('industry', '')}")
            
            m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
            
            price = data.get('price', 0)
            m1.metric(loc.get("price", "Giá"), f"{price:,.0f}" + (" VNĐ" if region == "VN" else " USD"))
            m2.metric(loc.get("volume", "Khối lượng"), f"{data.get('volume', 0):,}")
            m3.metric("Sàn", data.get('market', region))
            
            pe = data.get('pe', 'N/A')
            avg_pe = data.get('avg_pe', 0) or 0
            pe_delta = round(float(pe) - avg_pe, 2) if (pe != "N/A" and avg_pe) else None
            m4.metric(loc.get("pe_stock", "P/E"), str(pe))
            m5.metric(loc.get("pe_avg", "P/E Ngành"), str(avg_pe),
                      delta=pe_delta, delta_color="inverse" if pe_delta else "off")
            
            pb = data.get('pb', 'N/A')
            avg_pb = data.get('avg_pb', 0) or 0
            pb_delta = round(float(pb) - avg_pb, 2) if (pb != "N/A" and avg_pb) else None
            m6.metric(loc.get("pb_stock", "P/B"), str(pb))
            m7.metric(loc.get("pb_avg", "P/B Ngành"), str(avg_pb),
                      delta=pb_delta, delta_color="inverse" if pb_delta else "off")
            
            st.divider()
            
            # ── Biểu đồ: Chiếm diện tích tối đa ─────────────────────────────
            st.subheader(loc.get("chart", "📊 Biểu đồ Kỹ thuật"))
            render_chart(ticker, exchange=data.get('market', 'HOSE'), region=region)
            
            # ── Chatbot AI: Nằm hoàn toàn bên dưới chart ─────────────────────
            st.markdown('<div class="chatbot-section">', unsafe_allow_html=True)
            st.subheader(loc.get("ai_analysis", "🤖 Trợ lý AI - Phân tích chuyên sâu"))
            render_chat_interface(
                ticker=ticker,
                lang=lang_prompt,
                model=st.session_state["selected_model"],
                mode="ticker",
                stock_data=data
            )
            st.markdown('</div>', unsafe_allow_html=True)
    
    # ──────────────────────────────────────────────────────────────────────────
    #  NHÁNH B: CÂU HỎI THỊ TRƯỜNG CHUNG
    # ──────────────────────────────────────────────────────────────────────────
    else:
        st.info(f"💡 **Chế độ: Phân tích thị trường chung** — *\"{user_input}\"*")
        st.divider()
        
        # Trả lời AI trực tiếp, không gọi API lấy giá
        render_chat_interface(
            ticker="Thị trường",
            lang=lang_prompt,
            model=st.session_state["selected_model"],
            mode="general",
            initial_query=user_input
        )

# ── Hiển thị placeholder khi chưa có input ────────────────────────────────────
elif not user_input:
    st.markdown("""
    <div style='text-align:center; padding: 3rem 1rem; color: #666;'>
        <h3 style='color:#F4A261'>📈 Chào mừng đến với La Bàn Chứng Khoán AI Pro</h3>
        <p>Nhập <b>mã cổ phiếu</b> (VD: <code>FPT</code>, <code>AAPL</code>, <code>TCB</code>) để xem biểu đồ & phân tích AI</p>
        <p>Hoặc đặt <b>câu hỏi</b> (VD: <i>"Nhận định thị trường hôm nay"</i>) để hỏi AI trực tiếp</p>
    </div>
    """, unsafe_allow_html=True)
