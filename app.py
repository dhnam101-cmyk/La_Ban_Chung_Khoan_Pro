import streamlit as st
import pandas as pd
# SỬA LỖI QUAN TRỌNG: Đảm bảo dòng này có mặt để nhận diện hàm get_stock_data
from data.api_fetcher import get_stock_data 
from components.chart_view import render_tradingview_chart
from ai_core.chatbot_engine import get_ai_analysis
from streamlit_mic_recorder import mic_recorder 

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
if "ai_response_text" not in st.session_state:
    st.session_state["ai_response_text"] = ""

# ==========================================
# 3. SIDEBAR: CÀI ĐẶT
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
    st.subheader("🤖 Cấu hình AI")
    model_map = {
        "Gemini 1.5 Flash": "gemini-1.5-flash",
        "Gemini 1.5 Pro": "gemini-1.5-pro"
    }
    selected_model_label = st.selectbox("Chọn Model AI:", options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[selected_model_label]

# ==========================================
# 4. KHU VỰC HIỂN THỊ CHÍNH
# ==========================================
st.title("📈 La Bàn Chứng Khoán AI (Pro 2026)")

with st.container(border=True):
    col_text, col_mic = st.columns([0.85, 0.15])
    with col_text:
        ticker_input = st.text_input("🔍 Nhập mã cổ phiếu:", placeholder="VD: FPT, HPG...").upper()
    with col_mic:
        st.write("🎙️ Mic")
        audio = mic_recorder(start_prompt="Bật", stop_prompt="Dừng", key='recorder')

submit_button = st.button("Phân tích ngay")

if (submit_button or audio) and ticker_input != "":
    with st.spinner(f"Đang xử lý mã {ticker_input}..."):
        # GỌI HÀM LẤY DỮ LIỆU (Đã sửa lỗi định nghĩa)
        stock_info = get_stock_data(ticker_input) 
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Giá (VND)", f"{stock_info['price']:,}")
        m2.metric("Khối lượng", f"{stock_info['volume']:,}")
        m3.metric("P/E", str(stock_info['pe']))
        m4.metric("P/B", str(stock_info['pb']))
        
        st.divider()
        
        chart_col, ai_col = st.columns([7, 3])
        with chart_col:
            st.subheader("📊 Biểu đồ Kỹ thuật")
            render_tradingview_chart(ticker_input)
            
        with ai_col:
            st.subheader("🤖 Phân tích AI")
            with st.container(border=True):
                response = get_ai_analysis(
                    ticker_input, 
                    st.session_state["language"],
                    st.session_state["selected_model"]
                )
                st.session_state["ai_response_text"] = response
                st.markdown(response)
                
                if st.button("🔊 Nghe"):
                    js_code = f"""
                    <script>
                    var msg = new SpeechSynthesisUtterance('{st.session_state["ai_response_text"].replace("'", "")}');
                    msg.lang = 'vi-VN';
                    window.speechSynthesis.speak(msg);
                    </script>
                    """
                    st.components.v1.html(js_code, height=0)
