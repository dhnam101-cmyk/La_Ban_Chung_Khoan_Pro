import streamlit as st
import pandas as pd
from data.api_fetcher import get_stock_data
from components.chart_view import render_tradingview_chart
from ai_core.chatbot_engine import get_ai_analysis

# ==========================================
# 1. CẤU HÌNH TRANG WEB
# ==========================================
st.set_page_config(
    page_title="La Bàn Chứng Khoán Pro AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. KHỞI TẠO SESSION STATE
# ==========================================
if "language" not in st.session_state:
    st.session_state["language"] = "Tiếng Việt"
if "selected_model" not in st.session_state:
    st.session_state["selected_model"] = "gemini-1.5-flash"

# ==========================================
# 3. SIDEBAR: CÀI ĐẶT & CHỌN MODEL AI
# ==========================================
with st.sidebar:
    st.title("⚙️ Cài đặt Hệ thống")
    
    # Chọn ngôn ngữ
    selected_lang = st.selectbox(
        "🌐 Ngôn ngữ / Language", 
        options=["Tiếng Việt", "English"],
        index=0 if st.session_state["language"] == "Tiếng Việt" else 1
    )
    st.session_state["language"] = selected_lang
    
    st.markdown("---")
    
    # --- CHỌN BỘ NÃO AI (LINH HOẠT GÓI CƯỚC) ---
    st.subheader("🤖 Cấu hình Bộ não AI")
    model_map = {
        "Gemini 1.5 Flash (Nhanh & Tiết kiệm)": "gemini-1.5-flash",
        "Gemini 1.5 Pro (Phân tích chuyên sâu)": "gemini-1.5-pro",
        "Gemini 1.0 Pro (Ổn định)": "gemini-1.0-pro"
    }
    selected_model_label = st.selectbox(
        "Chọn Model AI phù hợp:",
        options=list(model_map.keys()),
        index=0
    )
    st.session_state["selected_model"] = model_map[selected_model_label]
    
    st.markdown("---")
    st.success(f"Đang dùng: {st.session_state['selected_model']}")
    st.info("Trạng thái: Sẵn sàng kết nối")

# ==========================================
# 4. KHU VỰC HIỂN THỊ CHÍNH
# ==========================================
st.title("📈 La Bàn Chứng Khoán AI (Multi-Brain Edition)")

with st.form(key="search_form"):
    col1, col2 = st.columns([4, 1])
    with col1:
        ticker_input = st.text_input("🔍 Nhập mã cổ phiếu và nhấn Enter:", value="").upper()
    with col2:
        submit_button = st.form_submit_button(label="Tra cứu")

# ==========================================
# 5. XỬ LÝ LOGIC
# ==========================================
if submit_button and ticker_input != "":
    with st.spinner(f"Đang quét dữ liệu mã {ticker_input}..."):
        # 1. Lấy dữ liệu số
        stock_info = get_stock_data(ticker_input)
        
        # 2. Hiển thị Metric
        st.success(f"Nguồn: {stock_info['source']}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Giá (VND)", f"{stock_info['price']:,}")
        m2.metric("Khối lượng", f"{stock_info['volume']:,}")
        m3.metric("P/E", str(stock_info['pe']))
        m4.metric("P/B", str(stock_info['pb']))
        
        st.markdown("---")
        
        # 3. Biểu đồ & AI
        chart_col, ai_col = st.columns([7, 3])
        
        with chart_col:
            st.subheader("📊 Biểu đồ Kỹ thuật")
            render_tradingview_chart(ticker_input) 
            
        with ai_col:
            st.subheader("🤖 Phân tích chuyên sâu")
            with st.container(border=True):
                # Gọi AI với Model đã chọn từ Sidebar
                ai_response = get_ai_analysis(
                    ticker_input, 
                    st.session_state["language"],
                    st.session_state["selected_model"]
                )
                st.markdown(ai_response)
elif submit_button and ticker_input == "":
    st.error("Vui lòng nhập mã cổ phiếu!")
