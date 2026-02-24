import streamlit as st
import pandas as pd
import sys
import os

# Bước quan trọng nhất: Ép Python nhận diện thư mục gốc của dự án
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Kết nối các module nội bộ với xử lý lỗi Import
try:
    from data.api_fetcher import get_stock_data 
    from components.chart_view import render_tradingview_chart
    from ai_core.chatbot_engine import get_ai_analysis
except ImportError as e:
    st.error(f"Lỗi hệ thống khi nạp module: {e}")
    st.info("Hãy đảm bảo bạn đã có file __init__.py trống trong các thư mục data, components và ai_core.")
    st.stop()

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

# 3. THANH ĐIỀU KHIỂN (SIDEBAR)
with st.sidebar:
    st.title("⚙️ Cài đặt")
    st.session_state["language"] = st.selectbox("🌐 Ngôn ngữ", options=["Tiếng Việt", "English"])
    st.divider()
    st.subheader("🤖 Cấu hình AI")
    model_map = {"Gemini 1.5 Flash": "gemini-1.5-flash", "Gemini 1.5 Pro": "gemini-1.5-pro"}
    sel_model = st.selectbox("Chọn Model:", options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[sel_model]

# 4. GIAO DIỆN CHÍNH
st.title("📈 La Bàn Chứng Khoán AI (Pro 2026)")

with st.container(border=True):
    col_text, col_mic = st.columns([0.8, 0.2])
    with col_text:
        ticker_input = st.text_input("🔍 Nhập mã (VD: FPT, HPG, VCB):").upper()
    with col_mic:
        st.write("🎙️ Mic")
        audio = mic_recorder(start_prompt="Bật", stop_prompt="Dừng", key='recorder')

# 5. XỬ LÝ DỮ LIỆU VÀ HIỂN THỊ
if (st.button("Phân tích ngay") or audio) and ticker_input:
    with st.spinner(f"Đang xử lý dữ liệu mã {ticker_input}..."):
        # Gọi hàm từ data/api_fetcher.py
        data = get_stock_data(ticker_input)
        
        # Hiển thị các chỉ số chính
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Giá", f"{data['price']:,}")
        m2.metric("Khối lượng", f"{data['volume']:,}")
        m3.metric("P/E", str(data['pe']))
        m4.metric("P/B", str(data['pb']))
        
        st.divider()
        
        # Biểu đồ và AI Phân tích
        c1, c2 = st.columns([7, 3])
        with c1:
            st.subheader("📊 Biểu đồ Kỹ thuật")
            render_tradingview_chart(ticker_input)
        with c2:
            st.subheader("🤖 AI Nhận định")
            with st.container(border=True):
                res = get_ai_analysis(
                    ticker_input, 
                    st.session_state["language"], 
                    st.session_state["selected_model"]
                )
                st.markdown(res)
                
                # Tính năng đọc kết quả bằng giọng nói
                if st.button("🔊 Nghe phân tích"):
                    clean_text = res.replace("'", " ").replace('"', ' ')
                    js = f"""
                    <script>
                    var speech = new SpeechSynthesisUtterance("{clean_text}");
                    speech.lang = 'vi-VN';
                    window.speechSynthesis.speak(speech);
                    </script>
                    """
                    st.components.v1.html(js, height=0)
