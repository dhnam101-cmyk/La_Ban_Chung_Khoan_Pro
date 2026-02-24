import streamlit as st
import pandas as pd
from data.api_fetcher import get_stock_data
from components.chart_view import render_tradingview_chart  # <--- Bổ sung thợ vẽ biểu đồ

# ==========================================
# 1. CẤU HÌNH TRANG WEB (BẮT BUỘC ĐỂ LÊN ĐẦU)
# ==========================================
st.set_page_config(
    page_title="La Bàn Chứng Khoán Pro AI",
    page_icon="📈",
    layout="wide", # Mở rộng toàn màn hình để xem biểu đồ rõ hơn
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. KHỞI TẠO BỘ NHỚ TẠM (SESSION STATE)
# ==========================================
if "language" not in st.session_state:
    st.session_state["language"] = "Tiếng Việt"
if "current_ticker" not in st.session_state:
    st.session_state["current_ticker"] = "" # Mã cổ phiếu đang tra cứu

# ==========================================
# 3. THIẾT KẾ THANH ĐIỀU HƯỚNG BÊN TRÁI (SIDEBAR)
# ==========================================
with st.sidebar:
    st.title("⚙️ Cài đặt Hệ thống")
    
    # Nút chọn ngôn ngữ lập tức lưu vào Session State
    selected_lang = st.selectbox(
        "🌐 Ngôn ngữ / Language", 
        options=["Tiếng Việt", "English"],
        index=0 if st.session_state["language"] == "Tiếng Việt" else 1
    )
    st.session_state["language"] = selected_lang
    
    st.markdown("---")
    
    # Khu vực chọn sàn giao dịch
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

# Form tra cứu mã cổ phiếu (Sử dụng Enter để kích hoạt)
with st.form(key="search_form"):
    col1, col2 = st.columns([4, 1])
    
    with col1:
        ticker_input = st.text_input("🔍 Nhập mã cổ phiếu (VD: FPT, VCB, AAPL) và nhấn Enter:", value="").upper()
    
    with col2:
        submit_button = st.form_submit_button(label="Tra cứu ngay")

# ==========================================
# 5. XỬ LÝ LOGIC SAU KHI NHẤN ENTER
# ==========================================
if submit_button and ticker_input != "":
    st.session_state["current_ticker"] = ticker_input
    
    with st.spinner(f"Đang quét dữ liệu đa nguồn cho mã {ticker_input}..."):
        
        # 1. GỌI DỮ LIỆU TỪ MODULE data/api_fetcher.py
        stock_info = get_stock_data(ticker_input)
        
        # 2. HIỂN THỊ DỮ LIỆU CƠ BẢN LÊN GIAO DIỆN
        st.success(f"Dữ liệu được lấy từ: **{stock_info['source']}**")
        
        metric1, metric2, metric3, metric4 = st.columns(4)
        metric1.metric("Giá hiện tại (VND)", f"{stock_info['price']:,}")
        metric2.metric("Khối lượng 24h", f"{stock_info['volume']:,}")
        metric3.metric("Chỉ số P/E", str(stock_info['pe']))
        metric4.metric("Chỉ số P/B", str(stock_info['pb']))
        
        st.markdown("---")
        
        # 3. CHIA CỘT BIỂU ĐỒ VÀ AI
        chart_col, ai_col = st.columns([7, 3])
        
        with chart_col:
            st.subheader("📊 Biểu đồ Kỹ thuật (TradingView)")
            # Đã thay thế dòng thông báo bằng hàm vẽ biểu đồ thật
            render_tradingview_chart(ticker_input) 
            
        with ai_col:
            st.subheader("🤖 Phân tích AI & Vĩ mô")
            st.warning("Khu vực này sẽ nhúng module components/ai_chatbot.py ở Giai đoạn 4.")

elif submit_button and ticker_input == "":
    st.error("Vui lòng nhập một mã cổ phiếu hợp lệ!")
