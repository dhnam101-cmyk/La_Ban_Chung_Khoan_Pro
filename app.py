import streamlit as st
import pandas as pd
# Kết nối các module nội bộ
from data.api_fetcher import get_stock_data 
from components.chart_view import render_tradingview_chart
from ai_core.chatbot_engine import get_ai_analysis
from streamlit_mic_recorder import mic_recorder 

# 1. CẤU HÌNH TRANG
st.set_page_config(
    page_title="La Bàn Chứng Khoán Pro AI",
    page_icon="📈",
    layout="wide"
)

# 2. KHỞI TẠO TRẠNG THÁI
if "language" not in st.session_state:
    st.session_state["language"] = "Tiếng Việt"
if "selected_model" not in st.session_state:
    st.session_state["selected_model"] = "gemini-1.5-flash"

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
    col_text, col_mic = st.columns([0.8, 0.2])
    with col_text:
        ticker_input = st.text_input("🔍 Nhập mã (VD: FPT, VCB):").upper()
    with col_mic:
        st.write("🎙️ Mic")
        audio = mic_recorder(start_prompt="Bật", stop_prompt="Dừng", key='recorder')

if (st.button("Phân tích") or audio) and ticker_input:
    with st.spinner(f"Đang xử lý {ticker_input}..."):
        # Lấy dữ liệu
        data = get_stock_data(ticker_input)
        
        # Hiển thị chỉ số
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Giá", f"{data['price']:,}")
        m2.metric("Khối lượng", f"{data['volume']:,}")
        m3.metric("P/E", str(data['pe']))
        m4.metric("P/B", str(data['pb']))
        
        st.divider()
        
        # Biểu đồ và AI
        c1, c2 = st.columns([7, 3])
        with c1:
            st.subheader("📊 Biểu đồ")
            render_tradingview_chart(ticker_input)
        with c2:
            st.subheader("🤖 AI Phân tích")
            with st.container(border=True):
                res = get_ai_analysis(ticker_input, st.session_state["language"], st.session_state["selected_model"])
                st.markdown(res)
                
                # SỬA LỖI CÚ PHÁP TẠI ĐÂY: Sử dụng dấu nháy khác loại để tránh xung đột
                if st.button("🔊 Nghe"):
                    clean_text = res.replace("'", " ").replace('"', ' ')
                    js = f"""
                    <script>
                    var speech = new SpeechSynthesisUtterance("{clean_text}");
                    speech.lang = 'vi-VN';
                    window.speechSynthesis.speak(speech);
                    </script>
                    """
                    st.components.v1.html(js, height=0)
