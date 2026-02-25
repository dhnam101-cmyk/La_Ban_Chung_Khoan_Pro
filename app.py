import streamlit as st
import sys
import os
import json

# ==========================================
# 1. ÉP HỆ THỐNG NHẬN DIỆN THƯ MỤC GỐC
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# ==========================================
# 2. IMPORT ĐẦY ĐỦ CÁC MODULE (KHÔNG ĐỂ MẤT CHATBOT UI)
# ==========================================
try:
    from core.data_fetcher import get_stock_data 
    from components.chart_ui import render_tradingview_chart
    from components.chatbot_ui import render_chat_interface # Đã khôi phục khung Chat & Mic
except ImportError as e:
    st.error(f"❌ Lỗi sai cấu trúc thư mục: {e}")
    st.info("💡 Hãy chắc chắn bạn có 3 file: core/data_fetcher.py, components/chart_ui.py, components/chatbot_ui.py")
    st.stop()

# ==========================================
# 3. HÀM NẠP NGÔN NGỮ (LOCALES)
# ==========================================
@st.cache_data
def load_locales(lang_code):
    file_path = os.path.join(current_dir, "locales", f"{lang_code}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# CẤU HÌNH TRANG
st.set_page_config(page_title="La Bàn Chứng Khoán Pro", page_icon="📈", layout="wide")

# KHỞI TẠO STATE
if "language" not in st.session_state: st.session_state["language"] = "vi"
if "selected_model" not in st.session_state: st.session_state["selected_model"] = "gemini-1.5-flash"

loc = load_locales(st.session_state["language"])

# ==========================================
# 4. SIDEBAR: NGÔN NGỮ, THỊ TRƯỜNG & AI
# ==========================================
with st.sidebar:
    st.title(loc.get("sidebar_title", "⚙️ Cài đặt Hệ thống"))
    
    # --- Chọn Ngôn ngữ ---
    lang_display = st.selectbox(loc.get("lang_select", "🌐 Ngôn ngữ:"), ["Tiếng Việt (vi)", "English (en)"])
    new_lang = "vi" if "vi" in lang_display else "en"
    if new_lang != st.session_state["language"]:
        st.session_state["language"] = new_lang
        st.rerun()
    
    st.divider()
    
    # --- Chọn Thị trường (Mới bổ sung) ---
    st.subheader("🏢 Thị trường")
    st.session_state["market_filter"] = st.radio(
        "Chọn sàn giao dịch:", 
        ["Tất cả (All)", "HOSE (HSX)", "HNX", "UPCOM"]
    )
    
    st.divider()
    
    # --- Chọn AI Model ---
    st.subheader(loc.get("ai_config", "🤖 Cấu hình AI"))
    model_map = {"Gemini 1.5 Flash (Nhanh)": "gemini-1.5-flash", "Gemini 1.5 Pro (Sâu)": "gemini-1.5-pro"}
    sel_model = st.selectbox(loc.get("model_select", "Chọn Model:"), options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[sel_model]

# ==========================================
# 5. GIAO DIỆN CHÍNH & FORM (ẤN ENTER)
# ==========================================
st.title(loc.get("title", "📈 La Bàn Chứng Khoán AI Pro"))

with st.form(key="search_form"):
    col_input, col_btn = st.columns([0.85, 0.15])
    with col_input:
        ticker_input = st.text_input(loc.get("search_placeholder", "🔍 Nhập mã (Gõ xong ấn Enter):"), placeholder="VD: FPT, HPG...").upper()
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        submit_button = st.form_submit_button(loc.get("btn_analyze", "Phân tích"))

# ==========================================
# 6. XỬ LÝ DỮ LIỆU & HIỂN THỊ
# ==========================================
if submit_button and ticker_input:
    with st.spinner(f"{loc.get('loading', 'Đang quét...')} {ticker_input}..."):
        data = get_stock_data(ticker_input)
        
        if "error" in data:
            st.error(f"❌ {data['error']}")
        else:
            # --- HIỂN THỊ CHỈ SỐ ---
            st.subheader(loc.get("trade_info", "📊 Thông tin"))
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(loc.get("price", "Giá"), f"{data.get('price', 0):,} VNĐ")
            c2.metric(loc.get("volume", "Khối lượng"), f"{data.get('volume', 0):,}")
            c3.metric(loc.get("market", "Sàn"), data.get('market', 'N/A'))
            c4.metric(loc.get("industry", "Ngành"), data.get('industry', 'N/A'))

            st.subheader(loc.get("valuation", "⚖️ Định giá"))
            col1, col2, col3, col4 = st.columns(4)
            
            pe = data.get('pe', 'N/A')
            avg_pe = data.get('avg_pe', 0)
            pb = data.get('pb', 'N/A')
            avg_pb = data.get('avg_pb', 0)
            
            col1.metric(loc.get("pe_stock", "P/E"), str(pe))
            col2.metric(loc.get("pe_avg", "P/E Ngành"), str(avg_pe), 
                        delta=round(float(pe) - avg_pe, 2) if pe != "N/A" and avg_pe else 0, delta_color="inverse")
            
            col3.metric(loc.get("pb_stock", "P/B"), str(pb))
            col4.metric(loc.get("pb_avg", "P/B Ngành"), str(avg_pb), 
                        delta=round(float(pb) - avg_pb, 2) if pb != "N/A" and avg_pb else 0, delta_color="inverse")

            st.divider()
            
            # --- BIỂU ĐỒ & CHATBOT ---
            left, right = st.columns([0.6, 0.4])
            with left:
                render_tradingview_chart(ticker_input)
            with right:
                # TRUYỀN NGÔN NGỮ VÀ GỌI CHATBOT (Có lưu lịch sử và Mic voice)
                lang_prompt = "Tiếng Việt" if st.session_state["language"] == "vi" else "English"
                render_chat_interface(ticker_input, lang_prompt, st.session_state["selected_model"])
