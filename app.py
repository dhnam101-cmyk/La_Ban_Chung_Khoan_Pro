import streamlit as st
import pandas as pd
import sys
import os

# Ép hệ thống nhận diện thư mục gốc để nạp module
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Nạp các module nội bộ
try:
    from data.api_fetcher import get_stock_data 
    from components.chart_view import render_tradingview_chart
    from ai_core.chatbot_engine import get_ai_analysis
except ImportError as e:
    st.error(f"Lỗi module: {e}")
    st.stop()

from streamlit_mic_recorder import mic_recorder 

# 1. CẤU HÌNH TRANG
st.set_page_config(page_title="La Bàn Chứng Khoán Pro AI", page_icon="📈", layout="wide")

# 2. KHỞI TẠO STATE
if "language" not in st.session_state: st.session_state["language"] = "Tiếng Việt"
if "selected_model" not in st.session_state: st.session_state["selected_model"] = "gemini-1.5-flash"
if "ai_response_text" not in st.session_state: st.session_state["ai_response_text"] = ""

# 3. SIDEBAR
with st.sidebar:
    st.title("⚙️ Cài đặt")
    st.session_state["language"] = st.selectbox("🌐 Ngôn ngữ", options=["Tiếng Việt", "English"])
    st.divider()
    model_map = {"Gemini 1.5 Flash": "gemini-1.5-flash", "Gemini 1.5 Pro": "gemini-1.5-pro"}
    sel_model = st.selectbox("🤖 Chọn AI:", options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[sel_model]

# 4. GIAO DIỆN CHÍNH
st.title("📈 La Bàn Chứng Khoán AI (Pro 2026)")

with st.container(border=True):
    col_text, col_mic = st.columns([0.85, 0.15])
    with col_text:
        ticker_input = st.text_input("🔍 Nhập mã (VD: FPT, HPG):").upper()
    with col_mic:
        st.write("🎙️ Mic")
        audio = mic_recorder(start_prompt="Bật", stop_prompt="Dừng", key='recorder')

submit_button = st.button("Phân tích ngay", type="primary")

if (submit_button or audio) and ticker_input != "":
    with st.spinner(f"🚀 AI đang quét dữ liệu mã {ticker_input}..."):
        # Lấy dữ liệu
        stock_info = get_stock_data(ticker_input)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Giá", f"{stock_info['price']:,}")
        m2.metric("Khối lượng", f"{stock_info['volume']:,}")
        m3.metric("P/E", str(stock_info['pe']))
        m4.metric("P/B", str(stock_info['pb']))
        
        st.divider()
        
        c1, c2 = st.columns([0.65, 0.35])
        with c1:
            st.subheader("📊 Biểu đồ")
            render_tradingview_chart(ticker_input)
        with c2:
            st.subheader("🤖 Phân tích")
            with st.container(border=True):
                response = get_ai_analysis(
                    ticker_input, 
                    st.session_state["language"],
                    st.session_state["selected_model"]
                )
                st.session_state["ai_response_text"] = response
                st.markdown(response)
                
                if st.button("🔊 Nghe"):
                    clean_text = response.replace("'", " ").replace('"', ' ').replace("\n", " ")
                    js_code = f"""
                    <script>
                    var msg = new SpeechSynthesisUtterance('{clean_text}');
                    msg.lang = 'vi-VN';
                    window.speechSynthesis.speak(msg);
                    </script>
                    """
                    st.components.v1.html(js_code, height=0)
