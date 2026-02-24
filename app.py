import streamlit as st
import pandas as pd
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
if "ai_response_text" not in st.session_state:
    st.session_state["ai_response_text"] = ""

# SIDEBAR
with st.sidebar:
    st.title("⚙️ Cài đặt Hệ thống")
    selected_lang = st.selectbox("🌐 Ngôn ngữ", options=["Tiếng Việt", "English"])
    st.session_state["language"] = selected_lang
    
    st.subheader("🤖 Cấu hình AI")
    model_map = {
        "Gemini 1.5 Flash": "gemini-1.5-flash",
        "Gemini 1.5 Pro": "gemini-1.5-pro"
    }
    sel_model = st.selectbox("Chọn Model:", options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[sel_model]

st.title("📈 La Bàn Chứng Khoán AI (Pro 2026)")

# KHU VỰC NHẬP LIỆU
with st.container(border=True):
    col_text, col_mic = st.columns([0.85, 0.15])
    with col_text:
        ticker_input = st.text_input("🔍 Nhập mã cổ phiếu:", placeholder="VD: FPT...").upper()
    with col_mic:
        audio = mic_recorder(start_prompt="🎙️", stop_prompt="🛑", key='recorder')

submit_button = st.button("Phân tích ngay")

if (submit_button or audio) and ticker_input != "":
    with st.spinner("Đang xử lý..."):
        stock_info = get_stock_data(ticker_input) [cite: 4, 7]
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Giá", f"{stock_info['price']:,}")
        m2.metric("Khối lượng", f"{stock_info['volume']:,}")
        m3.metric("P/E", str(stock_info['pe']))
        m4.metric("P/B", str(stock_info['pb']))
        
        st.divider()
        
        chart_col, ai_col = st.columns([7, 3])
        with chart_col:
            render_tradingview_chart(ticker_input) [cite: 8]
        with ai_col:
            with st.container(border=True):
                response = get_ai_analysis(
                    ticker_input, 
                    st.session_state["language"],
                    st.session_state["selected_model"]
                )
                st.session_state["ai_response_text"] = response
                st.markdown(response)
                
                if st.button("🔊 Nghe"):
                    js = f"<script>speechSynthesis.speak(new SpeechSynthesisUtterance('{response.replace("'", "")}'));</script>"
                    st.components.v1.html(js, height=0)
