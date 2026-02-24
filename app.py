import streamlit as st
import sys
import os

# Ép hệ thống nhận diện thư mục
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    from data.api_fetcher import get_stock_data 
    from components.chart_view import render_tradingview_chart
    from ai_core.chatbot_engine import get_ai_analysis
except Exception as e:
    st.error(f"Lỗi khởi động: {e}")
    st.stop()

st.set_page_config(page_title="La Bàn Chứng Khoán Pro", layout="wide")

# SIDEBAR: THÊM NÚT CHỌN THỊ TRƯỜNG
with st.sidebar:
    st.header("🌐 Thị trường")
    market = st.radio("Chọn sàn giao dịch:", ["Tất cả", "HOSE", "HNX", "UPCOM"])
    st.divider()
    model = st.selectbox("🤖 Model AI:", ["gemini-1.5-flash", "gemini-1.5-pro"])

st.title("📈 La Bàn Chứng Khoán AI (Bản Full Dữ Liệu)")

ticker = st.text_input("🔍 Nhập mã cổ phiếu:").upper()

if st.button("Soi mã") and ticker:
    data = get_stock_data(ticker)
    
    if "error" in data:
        st.error(data["error"])
    else:
        # HÀNG 1: THÔNG TIN CƠ BẢN
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Giá hiện tại", f"{data['price']:,} VNĐ")
        c2.metric("Khối lượng ngày", f"{data['volume']:,}")
        c3.metric("Sàn niêm yết", data['market'])
        c4.metric("Ngành", data['industry'])

        # HÀNG 2: SO SÁNH ĐỊNH GIÁ (P/E, P/B)
        st.subheader("⚖️ Định giá & So sánh ngành")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("P/E Cổ phiếu", str(data['pe']))
        col2.metric("P/E Trung bình ngành", str(data['avg_pe']), delta=round(float(data['pe'])-data['avg_pe'],2) if data['pe']!="N/A" else 0, delta_color="inverse")
        col3.metric("P/B Cổ phiếu", str(data['pb']))
        col4.metric("P/B Trung bình ngành", str(data['avg_pb']), delta=round(float(data['pb'])-data['avg_pb'],2) if data['pb']!="N/A" else 0, delta_color="inverse")

        st.divider()
        
        # BIỂU ĐỒ VÀ AI
        left, right = st.columns([7, 3])
        with left:
            render_tradingview_chart(ticker)
        with right:
            analysis = get_ai_analysis(ticker, "Tiếng Việt", model)
            st.markdown(analysis)
