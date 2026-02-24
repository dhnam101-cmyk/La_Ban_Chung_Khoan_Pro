import streamlit as st
import pandas as pd
from data.api_fetcher import get_stock_data
from components.chart_view import render_tradingview_chart
from ai_core.chatbot_engine import get_ai_analysis
from streamlit_mic_recorder import mic_recorder # Thư viện ghi âm mới

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
    st.subheader("🤖 Cấu hình Bộ não AI")
    model_map = {
        "Gemini 1.5 Flash (Nhanh & Tiết kiệm)": "gemini-1.5-flash",
        "Gemini 1.5 Pro (Phân tích chuyên sâu)": "gemini-1.5-pro",
        "Gemini 1.0 Pro (Ổn định)": "gemini-1.0-pro"
    }
    selected_model_label = st.selectbox("Chọn Model AI:", options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[selected_model_label]

# ==========================================
# 4. KHU VỰC ĐIỀU KHIỂN GIỌNG NÓI & NHẬP LIỆU
# ==========================================
st.title("📈 La Bàn Chứng Khoán AI (Voice Edition)")

with st.container(border=True):
    col_text, col_mic = st.columns([0.85, 0.15])
    
    with col_text:
        ticker_input = st.text_input("🔍 Nhập mã cổ phiếu:", placeholder="VD: FPT, VCB...").upper()
    
    with col_mic:
        st.write("🎙️ Mic")
        audio = mic_recorder(start_prompt="Bật", stop_prompt="Dừng", key='recorder')
        # Lưu ý: Ở bản đại chúng, Speech-to-Text sẽ được xử lý qua API Gemini ở bước sau

submit_button = st.button("Tra cứu & Phân tích")

# ==========================================
# 5. XỬ LÝ LOGIC & HIỂN THỊ
# ==========================================
if (submit_button or audio) and ticker_input != "":
    with st.spinner(f"AI đang quét dữ liệu cho mã {ticker_input}..."):
        # 1. Lấy dữ liệu số [cite: 4, 7]
        stock_info = get_stock_data(ticker_input)
        
        # 2. Hiển thị thông số
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Giá (VND)", f"{stock_info['price']:,}")
        m2.metric("Khối lượng", f"{stock_info['volume']:,}")
        m3.metric("P/E", str(stock_info['pe']))
        m4.metric("P/B", str(stock_info['pb']))
        
        st.markdown("---")
        
        chart_col, ai_col = st.columns([7, 3])
        
        with chart_col:
            st.subheader("📊 Biểu đồ Kỹ thuật")
            render_tradingview_chart(ticker_input) [cite: 8]
            
        with ai_col:
            st.subheader("🤖 Phân tích AI")
            with st.container(border=True):
                # Gọi AI lấy kết quả
                response = get_ai_analysis(
                    ticker_input, 
                    st.session_state["language"],
                    st.session_state["selected_model"]
                )
                st.session_state["ai_response_text"] = response
                st.markdown(response)
                
                # NÚT BẤM ĐỌC GIỌNG NÓI (Text-to-Speech)
                if st.button("🔊 Nghe bài phân tích"):
                    # Sử dụng tính năng có sẵn của trình duyệt để đọc (giúp tiết kiệm phí API)
                    js_code = f"""
                    <script>
                    var msg = new SpeechSynthesisUtterance('{st.session_state["ai_response_text"].replace("'", "")}');
                    msg.lang = 'vi-VN';
                    window.speechSynthesis.speak(msg);
                    </script>
                    """
                    st.components.v1.html(js_code, height=0)

elif submit_button and ticker_input == "":
    st.error("Vui lòng nhập mã cổ phiếu!")
