import streamlit as st
import sys
import os
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path: sys.path.append(current_dir)

try:
    from core.data_fetcher import get_stock_data 
    from components.chart_ui import render_tradingview_chart
    from components.chatbot_ui import render_chat_interface
except ImportError as e:
    st.error(f"❌ Lỗi cấu trúc: {e}")
    st.stop()

from streamlit_mic_recorder import speech_to_text 

@st.cache_data
def load_locales(lang_code):
    file_path = os.path.join(current_dir, "locales", f"{lang_code}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f: return json.load(f)
    return {}

st.set_page_config(page_title="La Bàn Chứng Khoán Pro", page_icon="📈", layout="wide")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    [data-testid="stMetricDelta"] { font-size: 0.9rem !important; }
</style>
""", unsafe_allow_html=True)

if "language" not in st.session_state: st.session_state["language"] = "vi"
if "selected_model" not in st.session_state: st.session_state["selected_model"] = "gemini-2.0-flash"

loc = load_locales(st.session_state["language"])

with st.sidebar:
    st.title(loc.get("sidebar_title", "⚙️ Cài đặt Hệ thống"))
    lang_display = st.selectbox(loc.get("lang_select", "🌐 Ngôn ngữ:"), ["Tiếng Việt (vi)", "English (en)"])
    new_lang = "vi" if "vi" in lang_display else "en"
    if new_lang != st.session_state["language"]:
        st.session_state["language"] = new_lang
        st.rerun()
    st.divider()
    st.subheader("🏢 Thị trường")
    st.session_state["market_filter"] = st.radio("Chọn sàn giao dịch:", ["Tất cả", "HOSE", "HNX", "UPCOM"])
    st.divider()
    st.subheader(loc.get("ai_config", "🤖 Cấu hình AI"))
    
    # DÙNG BẢN GEMINI 2.0 MỚI NHẤT
    model_map = {"Gemini 2.0 Flash (Nhanh)": "gemini-2.0-flash", "Gemini 2.0 Pro (Sâu)": "gemini-2.0-pro-exp-02-05"}
    sel_model = st.selectbox(loc.get("model_select", "Chọn Model:"), options=list(model_map.keys()))
    st.session_state["selected_model"] = model_map[sel_model]

st.title(loc.get("title", "📈 La Bàn Chứng Khoán AI Pro"))

with st.form(key="search_form"):
    col_input, col_btn = st.columns([0.85, 0.15])
    with col_input:
        form_input = st.text_input("🔍 Nhập mã HOẶC câu hỏi thị trường (Ấn Enter):", placeholder="VD: FPT, hoặc 'Ngành thép hôm nay'").strip()
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        submit_button = st.form_submit_button(loc.get("btn_analyze", "Phân tích"))

st.caption("🎙️ Hoặc tìm bằng giọng nói:")
voice_input = speech_to_text(language='vi-VN', start_prompt="Bấm để nói", stop_prompt="Dừng", key='main_mic')

user_input = form_input if form_input else voice_input

if (submit_button or voice_input) and user_input:
    is_ticker = len(user_input.split()) == 1 and len(user_input) <= 6
    lang_prompt = "Tiếng Việt" if st.session_state["language"] == "vi" else "English"

    if is_ticker:
        ticker_input = user_input.upper()
        with st.spinner(f"{loc.get('loading', 'Đang quét')} {ticker_input}..."):
            data = get_stock_data(ticker_input)
            if "error" in data:
                st.error(f"❌ {data['error']}")
            else:
                st.subheader(loc.get("trade_info", "📊 Thông tin & Định giá"))
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric(loc.get("price", "Giá"), f"{data.get('price', 0):,} VNĐ")
                c2.metric(loc.get("volume", "Khối lượng"), f"{data.get('volume', 0):,}")
                
                pe, avg_pe = data.get('pe', 'N/A'), data.get('avg_pe', 0)
                c3.metric(loc.get("pe_stock", "P/E"), str(pe))
                c4.metric(loc.get("pe_avg", "P/E Ngành"), str(avg_pe), delta=round(float(pe) - avg_pe, 2) if pe != "N/A" and avg_pe else 0, delta_color="inverse")
                
                pb, avg_pb = data.get('pb', 'N/A'), data.get('avg_pb', 0)
                c5.metric(loc.get("pb_stock", "P/B"), str(pb))
                c6.metric(loc.get("pb_avg", "P/B Ngành"), str(avg_pb), delta=round(float(pb) - avg_pb, 2) if pb != "N/A" and avg_pb else 0, delta_color="inverse")
                st.divider()
                
                st.subheader(loc.get("chart", "📊 Biểu đồ Kỹ thuật"))
                render_tradingview_chart(ticker_input, exchange=data.get('market', 'HOSE'))
                st.divider()

                st.subheader(loc.get("ai_analysis", "🤖 Trò chuyện AI"))
                render_chat_interface(ticker_input, lang_prompt, st.session_state["selected_model"], is_general_query=False)
    else:
        st.info("💡 Chế độ: Phân tích Thị trường chung")
        render_chat_interface("Thị trường", lang_prompt, st.session_state["selected_model"], is_general_query=True, initial_query=user_input)
