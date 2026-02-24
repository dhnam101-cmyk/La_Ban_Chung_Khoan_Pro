import streamlit as st
import pandas as pd
from data.api_fetcher import get_stock_data
from components.chart_view import render_tradingview_chart
from ai_core.chatbot_engine import get_ai_analysis  # <--- Bổ sung não bộ AI

# ==========================================
# 1. CẤU HÌNH TRANG WEB (BẮT BUỘC ĐỂ LÊN ĐẦU)
# ==========================================
st.set_page_config(
    page_title="La Bàn Chứng Khoán Pro AI",
    page_icon="📈",
    layout="wide", # Mở rộng toàn màn hình
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. KHỞI TẠO BỘ NHỚ TẠM (SESSION STATE)
# ==========================================
if "language" not in st.session_state:
    st.session_state["language"] = "Tiếng Việt"
if "current_ticker" not in st.session_state:
    st.session_state["current_ticker"] = ""

# ==========================================
# 3. THIẾT KẾ THANH ĐIỀU HƯỚNG BÊN TRÁI (SIDEBAR)
# ==========================================
with st.sidebar:
    st.title("⚙️ Cài đặt Hệ thống")
    
    selected_lang = st.selectbox(
        "🌐 Ngôn ngữ / Language", 
        options=["Tiếng Việt", "English"],
        index=0 if st.session_state["language"] == "Tiếng Việt" else 1
    )
    st.session_state["language"] = selected_lang
    
    st.markdown("---")
    
    st.subheader("🏦 Chọn thị trường")
    market_choice = st.selectbox(
        "Sàn giao dịch:",
        options=["VN-Index (Việt Nam)", "S&P 500 (Mỹ)", "Crypto (Binance)"]
    )
    
    st.markdown("---")
    
    st.success("Trạng thái AI: Đang hoạt động (Model chính)")
    st.info("Kết nối Dữ liệu: Real-time 100%")

# ==========================================
# 4. KHU VỰC HIỂN THỊ CHÍNH (MAIN AREA)
# ==========================================
st.title("📈 Bảng Điều Khiển: La Bàn Chứng Khoán AI")
st.write(f"Đang hiển thị ngôn ngữ: **{st.session_state['language']}** | Thị trường: **{market_choice}**")

with st.form(key="search_form"):
    col1, col2 = st.columns([4, 1])
    
    with col1:
        ticker_input = st.text_input("🔍 Nhập mã cổ phiếu (VD: FPT, VCB, AAPL) và nhấn Enter:", value="").upper()
    
    with col2:
        submit_button = st.form_submit_button(label="Tra cứu ngay")

# ==========================================
# 5. XỬ LÝ LOGIC SAU KHI NHẤN ENTER (FULL TÍNH NĂNG)
# ==========================================
if submit_button and ticker_input != "":
    st.session_state["current_ticker"] = ticker_input
    
    with st.spinner(f"Đang quét dữ liệu đa nguồn cho mã {ticker_input}..."):
        
        # 1. LẤY DỮ LIỆU CƠ BẢN (Đã chống sập)
        stock_info = get_stock_data(ticker_input)
        
        st.success(f"Dữ liệu được lấy từ: **{stock_info['source']}**")
        
        metric1, metric2, metric3, metric4 = st.columns(4)
        metric1.metric("Giá hiện tại (VND)", f"{stock_info['price']:,}")
        metric2.metric("Khối lượng 24h", f"{stock_info['volume']:,}")
        metric3.metric("Chỉ số P/E", str(stock_info['pe']))
        metric4.metric("Chỉ số P/B", str(stock_info['pb']))
        
        st.markdown("---")
        
        # 2. CHIA CỘT HIỂN THỊ BIỂU ĐỒ VÀ AI
        chart_col, ai_col = st.columns([7, 3])
        
        with chart_col:
            st.subheader("📊 Biểu đồ Kỹ thuật (TradingView)")
            render_tradingview_chart(ticker_input) 
            
        with ai_col:
            st.subheader("🤖 Phân tích AI & Vĩ mô")
            
            # Khung bọc kết quả AI cho đẹp mắt
            with st.container(border=True):
                with st.spinner("AI đang tổng hợp vĩ mô và kỹ thuật..."):
                    current_lang = st.session_state["language"]
                    # Gọi hàm AI với cơ chế dự phòng
                    ai_response = get_ai_analysis(ticker_input, current_lang)
                    st.markdown(ai_response)

elif submit_button and ticker_input == "":
    st.error("Vui lòng nhập một mã cổ phiếu hợp lệ!")
