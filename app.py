import streamlit as st
import sys
import os

# Ép hệ thống nhận diện thư mục gốc chuẩn
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# NẠP MODULE CHUẨN KIẾN TRÚC GỐC
try:
    from core.data_fetcher import get_stock_data 
    from components.chart_ui import render_tradingview_chart
    from components.chatbot_ui import render_chat_interface
except ImportError as e:
    st.error(f"❌ Lỗi cấu trúc thư mục: {e}")
    st.info("💡 Hãy kiểm tra lại tên file: core/data_fetcher.py và components/chatbot_ui.py")
    st.stop()

# CẤU HÌNH TRANG
st.set_page_config(page_title="La Bàn Chứng Khoán Pro", page_icon="📈", layout="wide")

# KHỞI TẠO STATE
if "language" not in st.session_state: st.session_state["language"] = "Tiếng Việt (vi)"
if "selected_model" not in st.session_state: st.session_state["selected_model"] = "gemini-1.5-flash"

# ==========================================
# SIDEBAR: CÀI ĐẶT
# ==========================================
with st.sidebar:
    st.title("⚙️ Cài đặt Hệ thống")
    
    # Nút chọn ngôn ngữ liên kết với locales/
    st.session_state["language"] = st.selectbox("🌐 Ngôn ngữ hiển thị:", ["Tiếng Việt (vi)", "English (en)"])
    st.divider()
    
    st.subheader("🤖 Cấu hình AI")
    model_map = {"Gemini 1.5 Flash (Nhanh)": "gemini-1.5-flash", "Gemini 1.5 Pro (Sâu)": "gemini-1.5-pro"}
    sel_model = st.selectbox("Chọn Model:", options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[sel_model]

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
st.title("📈 La Bàn Chứng Khoán AI Pro")

# Form hỗ trợ gõ mã xong ấn Enter
with st.form(key="search_form"):
    col_input, col_btn = st.columns([0.85, 0.15])
    with col_input:
        ticker_input = st.text_input("🔍 Nhập mã cổ phiếu (Gõ xong ấn Enter):", placeholder="VD: FPT, HPG, VCB...").upper()
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        submit_button = st.form_submit_button("Phân tích")

# ==========================================
# XỬ LÝ DỮ LIỆU & HIỂN THỊ
# ==========================================
if submit_button and ticker_input:
    with st.spinner(f"🚀 Đang quét dữ liệu toàn diện cho {ticker_input}..."):
        data = get_stock_data(ticker_input)
        
        if "error" in data:
            st.error(f"❌ {data['error']}")
        else:
            # THÔNG TIN CƠ BẢN
            st.subheader("📊 Thông tin Giao dịch")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá hiện tại", f"{data.get('price', 0):,} VNĐ")
            c2.metric("Khối lượng ngày", f"{data.get('volume', 0):,}")
            c3.metric("Sàn niêm yết", data.get('market', 'N/A'))
            c4.metric("Nhóm Ngành", data.get('industry', 'N/A'))

            # ĐỊNH GIÁ CHUYÊN SÂU
            st.subheader("⚖️ Định giá & So sánh ngành")
            col1, col2, col3, col4 = st.columns(4)
            
            pe = data.get('pe', 'N/A')
            avg_pe = data.get('avg_pe', 0)
            pb = data.get('pb', 'N/A')
            avg_pb = data.get('avg_pb', 0)
            
            col1.metric("P/E Cổ phiếu", str(pe))
            col2.metric("P/E TB Ngành", str(avg_pe), 
                        delta=round(float(pe) - avg_pe, 2) if pe != "N/A" and avg_pe else 0, delta_color="inverse")
            
            col3.metric("P/B Cổ phiếu", str(pb))
            col4.metric("P/B TB Ngành", str(avg_pb), 
                        delta=round(float(pb) - avg_pb, 2) if pb != "N/A" and avg_pb else 0, delta_color="inverse")

            st.divider()
            
            # BIỂU ĐỒ VÀ CHATBOT
            left, right = st.columns([0.6, 0.4])
            with left:
                render_tradingview_chart(ticker_input)
            with right:
                # GỌI GIAO DIỆN CHATBOT CÓ TÍCH HỢP MIC
                render_chat_interface(ticker_input, st.session_state["language"], st.session_state["selected_model"])
