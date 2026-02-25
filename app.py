import streamlit as st
import sys
import os
import json

# Ép hệ thống nhận diện thư mục gốc chuẩn
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# IMPORT CHUẨN THEO KIẾN TRÚC GỐC
try:
    from core.data_fetcher import get_stock_data 
    from components.chart_ui import render_tradingview_chart
    from core.ai_engine import get_ai_analysis
except ImportError as e:
    st.error(f"❌ Lỗi sai cấu trúc thư mục: {e}")
    st.stop()

from streamlit_mic_recorder import mic_recorder 

# HÀM NẠP NGÔN NGỮ
@st.cache_data
def load_locales(lang_code):
    file_path = os.path.join(current_dir, "locales", f"{lang_code}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {} # Trả về rỗng nếu không tìm thấy file

# CẤU HÌNH TRANG
st.set_page_config(page_title="La Bàn Chứng Khoán Pro", page_icon="📈", layout="wide")

# KHỞI TẠO STATE NGÔN NGỮ
if "language" not in st.session_state: st.session_state["language"] = "vi"
if "selected_model" not in st.session_state: st.session_state["selected_model"] = "gemini-1.5-flash"

# Nạp file ngôn ngữ theo State hiện tại
loc = load_locales(st.session_state["language"])

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.title(loc.get("sidebar_title", "⚙️ Cài đặt"))
    
    lang_display = st.selectbox(loc.get("lang_select", "🌐 Ngôn ngữ:"), ["Tiếng Việt (vi)", "English (en)"])
    new_lang = "vi" if "vi" in lang_display else "en"
    
    # Nếu đổi ngôn ngữ thì reload lại trang
    if new_lang != st.session_state["language"]:
        st.session_state["language"] = new_lang
        st.rerun()
    
    st.divider()
    
    st.subheader(loc.get("ai_config", "🤖 Cấu hình AI"))
    model_map = {"Gemini 1.5 Flash (Nhanh)": "gemini-1.5-flash", "Gemini 1.5 Pro (Sâu)": "gemini-1.5-pro"}
    sel_model = st.selectbox(loc.get("model_select", "Chọn Model:"), options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[sel_model]

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
st.title(loc.get("title", "📈 La Bàn Chứng Khoán AI Pro"))

with st.form(key="search_form"):
    col_input, col_btn = st.columns([0.85, 0.15])
    with col_input:
        ticker_input = st.text_input(loc.get("search_placeholder", "🔍 Nhập mã:"), placeholder="VD: FPT, HPG...").upper()
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        submit_button = st.form_submit_button(loc.get("btn_analyze", "Phân tích"))

st.write(loc.get("voice_hint", "🎙️ Hoặc tìm bằng giọng nói:"))
audio = mic_recorder(start_prompt="Bật Mic", stop_prompt="Dừng", key='recorder')

# ==========================================
# XỬ LÝ DỮ LIỆU
# ==========================================
if (submit_button or audio) and ticker_input:
    with st.spinner(f"{loc.get('loading', 'Đang quét...')} {ticker_input}..."):
        data = get_stock_data(ticker_input)
        
        if "error" in data:
            st.error(f"❌ {data['error']}")
        else:
            st.subheader(loc.get("trade_info", "📊 Thông tin"))
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(loc.get("price", "Giá"), f"{data.get('price', 0):,} VNĐ")
            c2.metric(loc.get("volume", "Khối lượng"), f"{data.get('volume', 0):,}")
            c3.metric(loc.get("market", "Sàn"), data.get('market', 'N/A'))
            c4.metric(loc.get("industry", "Ngành"), data.get('industry', 'N/A'))

            st.subheader(loc.get("valuation", "⚖️ Định giá"))
            col1, col2, col3, col4 = st.columns(4)
            
            pe = data.get('pe', 'N/A')
            avg_pe = data.get('avg_pe', 0)
            pb = data.get('pb', 'N/A')
            avg_pb = data.get('avg_pb', 0)
            
            col1.metric(loc.get("pe_stock", "P/E"), str(pe))
            col2.metric(loc.get("pe_avg", "P/E Ngành"), str(avg_pe), 
                        delta=round(float(pe) - avg_pe, 2) if pe != "N/A" and avg_pe else 0, delta_color="inverse")
            
            col3.metric(loc.get("pb_stock", "P/B"), str(pb))
            col4.metric(loc.get("pb_avg", "P/B Ngành"), str(avg_pb), 
                        delta=round(float(pb) - avg_pb, 2) if pb != "N/A" and avg_pb else 0, delta_color="inverse")

            st.divider()
            
            left, right = st.columns([0.65, 0.35])
            with left:
                render_tradingview_chart(ticker_input)
            with right:
                st.subheader(loc.get("ai_analysis", "🤖 AI Phân tích"))
                with st.container(border=True):
                    # Truyền ngôn ngữ vào AI để nó trả lời đúng tiếng
                    lang_prompt = "Tiếng Việt" if st.session_state["language"] == "vi" else "English"
                    analysis = get_ai_analysis(ticker_input, lang_prompt, st.session_state["selected_model"])
                    st.markdown(analysis)
                    
                    if st.button(loc.get("btn_listen", "🔊 Nghe")):
                        clean_text = analysis.replace("'", " ").replace('"', ' ').replace("\n", " ")
                        voice_lang = 'vi-VN' if st.session_state["language"] == "vi" else 'en-US'
                        js = f"<script>var msg=new SpeechSynthesisUtterance('{clean_text}');msg.lang='{voice_lang}';window.speechSynthesis.speak(msg);</script>"
                        st.components.v1.html(js, height=0)
