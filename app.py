import streamlit as st
import pandas as pd
import sys
import os

# ==========================================
# GIẢI PHÁP CHỐT HẠ: ÉP HỆ THỐNG NHẬN DIỆN THƯ MỤC GỐC
# ==========================================
# Lấy đường dẫn tuyệt đối của thư mục đang chứa file app.py
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Import các module nội bộ sau khi đã thiết lập sys.path
try:
    from data.api_fetcher import get_stock_data 
    from components.chart_view import render_tradingview_chart
    from ai_core.chatbot_engine import get_ai_analysis
except ImportError as e:
    st.error(f"❌ Lỗi nạp module nội bộ: {e}")
    st.info("💡 Mẹo: Hãy kiểm tra xem bạn đã có file __init__.py trong các thư mục data, components và ai_core chưa.")
    st.stop()

from streamlit_mic_recorder import mic_recorder 

# ==========================================
# 1. CẤU HÌNH TRANG WEB (Tương thích 2026)
# ==========================================
st.set_page_config(
    page_title="La Bàn Chứng Khoán Pro AI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. KHỞI TẠO SESSION STATE
if "language" not in st.session_state:
    st.session_state["language"] = "Tiếng Việt"
if "selected_model" not in st.session_state:
    st.session_state["selected_model"] = "gemini-1.5-flash"
if "ai_response_text" not in st.session_state:
    st.session_state["ai_response_text"] = ""

# ==========================================
# 3. THANH ĐIỀU KHIỂN (SIDEBAR)
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
        "Gemini 1.5 Flash (Nhanh)": "gemini-1.5-flash",
        "Gemini 1.5 Pro (Sâu)": "gemini-1.5-pro"
    }
    selected_model_label = st.selectbox("Chọn Model AI:", options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[selected_model_label]
    
    st.divider()
    st.info(f"Đang chạy Model: {st.session_state['selected_model']}")

# ==========================================
# 4. GIAO DIỆN CHÍNH & NHẬP LIỆU GIỌNG NÓI
# ==========================================
st.title("📈 La Bàn Chứng Khoán AI (Pro 2026)")

# Sử dụng container để bao quát khu vực nhập liệu
with st.container(border=True):
    col_text, col_mic = st.columns([0.85, 0.15])
    
    with col_text:
        ticker_input = st.text_input("🔍 Nhập mã cổ phiếu:", placeholder="VD: FPT, HPG, VCB...").upper()
    
    with col_mic:
        st.write("🎙️ Ghi âm")
        audio = mic_recorder(start_prompt="Bật Mic", stop_prompt="Dừng", key='recorder')

submit_button = st.button("Phân tích ngay", type="primary")

# ==========================================
# 5. XỬ LÝ LOGIC & HIỂN THỊ KẾT QUẢ
# ==========================================
if (submit_button or audio) and ticker_input != "":
    with st.spinner(f"🚀 AI đang quét dữ liệu mã {ticker_input}..."):
        # 1. Lấy dữ liệu từ api_fetcher
        stock_info = get_stock_data(ticker_input) [cite: 52]
        
        # 2. Hiển thị Metrics (Chỉ số tài chính)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Giá (VND)", f"{stock_info['price']:,}")
        m2.metric("Khối lượng", f"{stock_info['volume']:,}")
        m3.metric("P/E", str(stock_info['pe']))
        m4.metric("P/B", str(stock_info['pb']))
        
        st.markdown("---")
        
        # 3. Phân chia Cột Biểu đồ & AI
        chart_col, ai_col = st.columns([0.65, 0.35])
        
        with chart_col:
            st.subheader("📊 Biểu đồ Kỹ thuật")
            render_tradingview_chart(ticker_input)
            
        with ai_col:
            st.subheader("🤖 Phân tích chuyên sâu")
            with st.container(border=True):
                # Gọi AI nhận định
                response = get_ai_analysis(
                    ticker_input, 
                    st.session_state["language"],
                    st.session_state["selected_model"]
                )
                st.session_state["ai_response_text"] = response
                st.markdown(response)
                
                # NÚT BẤM ĐỌC GIỌNG NÓI (Text-to-Speech)
                if st.button("🔊 Nghe bài phân tích"):
                    # Làm sạch văn bản để trình duyệt đọc không bị lỗi
                    clean_text = response.replace("'", " ").replace('"', ' ').replace("\n", " ")
                    js_code = f"""
                    <script>
                    var msg = new SpeechSynthesisUtterance('{clean_text}');
                    msg.lang = 'vi-VN';
                    window.speechSynthesis.speak(msg);
                    </script>
                    """
                    st.components.v1.html(js_code, height=0)

elif submit_button and ticker_input == "":
    st.warning("⚠️ Vui lòng nhập mã cổ phiếu để bắt đầu phân tích.")
