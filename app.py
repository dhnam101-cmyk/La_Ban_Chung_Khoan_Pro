import streamlit as st
import pandas as pd
import sys
import os

# 1. ÉP HỆ THỐNG NHẬN DIỆN THƯ MỤC NỘI BỘ
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# 2. NẠP CÁC MODULE VỚI XỬ LÝ LỖI
try:
    from data.api_fetcher import get_stock_data 
    from components.chart_view import render_tradingview_chart
    from ai_core.chatbot_engine import get_ai_analysis
except ImportError as e:
    st.error(f"❌ Lỗi nạp module nội bộ: {e}")
    st.stop()

from streamlit_mic_recorder import mic_recorder 

# 3. CẤU HÌNH TRANG
st.set_page_config(
    page_title="La Bàn Chứng Khoán Pro AI",
    page_icon="📈",
    layout="wide"
)

# Khởi tạo trạng thái ứng dụng
if "language" not in st.session_state:
    st.session_state["language"] = "Tiếng Việt"
if "selected_model" not in st.session_state:
    st.session_state["selected_model"] = "gemini-1.5-flash"

# 4. THANH ĐIỀU KHIỂN (SIDEBAR)
with st.sidebar:
    st.title("⚙️ Cài đặt")
    st.session_state["language"] = st.selectbox("🌐 Ngôn ngữ", options=["Tiếng Việt", "English"])
    st.divider()
    st.subheader("🤖 Cấu hình AI")
    model_map = {"Gemini 1.5 Flash": "gemini-1.5-flash", "Gemini 1.5 Pro": "gemini-1.5-pro"}
    sel_model = st.selectbox("Chọn Model:", options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[sel_model]

# 5. GIAO DIỆN CHÍNH
st.title("📈 La Bàn Chứng Khoán AI (Dữ liệu Đa nguồn)")

with st.container(border=True):
    col_text, col_mic = st.columns([0.85, 0.15])
    with col_text:
        ticker_input = st.text_input("🔍 Nhập mã cổ phiếu (VD: FPT, HPG, VCB):").upper()
    with col_mic:
        st.write("🎙️ Ghi âm")
        audio = mic_recorder(start_prompt="Bật Mic", stop_prompt="Dừng", key='recorder')

submit_button = st.button("Phân tích ngay", type="primary")

# 6. XỬ LÝ DỮ LIỆU & HIỂN THỊ
if (submit_button or audio) and ticker_input:
    with st.spinner(f"🚀 Hệ thống đang quét đa nguồn cho mã {ticker_input}..."):
        # Lấy dữ liệu từ hệ thống dự phòng (api_fetcher.py)
        data = get_stock_data(ticker_input)
        
        # Hiển thị nguồn dữ liệu để người dùng kiểm chứng
        if data['price'] > 0:
            st.success(f"✅ Đã lấy dữ liệu từ: **{data['source']}**")
        else:
            st.error(f"❌ Thất bại: {data['source']}")

        # Hiển thị các chỉ số tài chính thực tế
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Giá (VND)", f"{data['price']:,}")
        m2.metric("Khối lượng", f"{data['volume']:,}")
        m3.metric("Chỉ số P/E", str(data['pe']))
        m4.metric("Chỉ số P/B", str(data['pb']))
        
        st.divider()
        
        # Bố cục Biểu đồ và AI Phân tích
        c1, c2 = st.columns([0.65, 0.35])
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
                
                # Tính năng đọc kết quả
                if st.button("🔊 Nghe phân tích"):
                    clean_text = res.replace("'", " ").replace('"', ' ').replace("\n", " ")
                    js = f"""
                    <script>
                    var msg = new SpeechSynthesisUtterance('{clean_text}');
                    msg.lang = 'vi-VN';
                    window.speechSynthesis.speak(msg);
                    </script>
                    """
                    st.components.v1.html(js, height=0)
