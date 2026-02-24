import streamlit as st
import pandas as pd
# ĐẢM BẢO NHẬP ĐÚNG CÁC MODULE NỘI BỘ
from data.api_fetcher import get_stock_data 
from components.chart_view import render_tradingview_chart
from ai_core.chatbot_engine import get_ai_analysis
from streamlit_mic_recorder import mic_recorder 

# CẤU HÌNH TRANG WEB
st.set_page_config(
    page_title="La Bàn Chứng Khoán Pro AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# KHỞI TẠO SESSION STATE
if "language" not in st.session_state:
    st.session_state["language"] = "Tiếng Việt"
if "selected_model" not in st.session_state:
    st.session_state["selected_model"] = "gemini-1.5-flash"

st.title("📈 La Bàn Chứng Khoán AI (Pro 2026)")

# THANH SIDEBAR
with st.sidebar:
    st.title("⚙️ Cài đặt Hệ thống")
    st.session_state["language"] = st.selectbox("🌐 Ngôn ngữ", options=["Tiếng Việt", "English"])
    st.markdown("---")
    st.subheader("🤖 Cấu hình AI")
    model_map = {"Gemini 1.5 Flash": "gemini-1.5-flash", "Gemini 1.5 Pro": "gemini-1.5-pro"}
    sel_model = st.selectbox("Chọn Model:", options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[sel_model]

# KHU VỰC NHẬP LIỆU
with st.container(border=True):
    col_text, col_mic = st.columns([0.85, 0.15])
    with col_text:
        ticker_input = st.text_input("🔍 Nhập mã cổ phiếu:", placeholder="VD: FPT, HPG...").upper()
    with col_mic:
        st.write("🎙️ Mic")
        audio = mic_recorder(start_prompt="Bật", stop_prompt="Dừng", key='recorder')

submit_button = st.button("Phân tích ngay")

if (submit_button or audio) and ticker_input != "":
    with st.spinner(f"Đang phân tích mã {ticker_input}..."):
        # Lấy dữ liệu từ data/api_fetcher.py
        stock_info = get_stock_data(ticker_input) 
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Giá (VND)", f"{stock_info['price']:,}")
        m2.metric("Khối lượng", f"{stock_info['volume']:,}")
        m3.metric("P/E", str(stock_info['pe']))
        m4.metric("P/B", str(stock_info['pb']))
        
        st.divider()
        
        # Chia cột Biểu đồ và AI
        chart_col, ai_col = st.columns([7, 3])
        with chart_col:
            st.subheader("📊 Biểu đồ Kỹ thuật")
            render_tradingview_chart(ticker_input)
            
        with ai_col:
            st.subheader("🤖 Phân tích AI")
            with st.container(border=True):
                # Gọi bộ não AI
                response = get_ai_analysis(
                    ticker_input, 
                    st.session_state["language"],
                    st.session_state["selected_model"]
                )
                st.markdown(response)
                
                if st.button("🔊 Nghe"):
                    js = f"<script>speechSynthesis.speak(new SpeechSynthesisUtterance('{response.replace(\"'\", \"\")}'));</script>"
                    st.components.v1.html(js, height=0)
