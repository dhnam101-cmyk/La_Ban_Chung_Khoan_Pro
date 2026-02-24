import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. KIẾN TRÚC DỊCH THUẬT NGÀNH (FIX image_b90d44) ---
st.set_page_config(page_title="AI Terminal V70: Ultimate", layout="wide")

IND_MAP = {
    "Banks": "Ngân hàng", "Steel": "Thép", "Real Estate": "Bất động sản",
    "IT": "Công nghệ", "Financial": "Chứng khoán", "Oil": "Dầu khí",
    "Consumer": "Tiêu dùng", "Electricity": "Điện năng"
}

# --- 2. HỆ THỐNG AI TẬP TRUNG (CHỐNG LỖI BUSY - image_b90dfa) ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Dò tìm model đang sống thực tế
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        prio = ['models/gemini-1.5-flash', 'models/gemini-pro']
        for p in prio:
            if p in models: return genai.GenerativeModel(p)
        return genai.GenerativeModel(models[0])
    except: return None

# --- 3. MA TRẬN DỮ LIỆU ĐỘT KÍCH (FIX GIÁ 142 & N/A) ---
def fetch_data_ultimate(ticker, market):
    sym = ticker.upper().strip()
    suffix = ".VN" if market == "Việt Nam" else ""
    df, p, pe, pb, ind = None, 0, "N/A", "N/A", "N/A"
    
    try:
        s = yf.Ticker(sym + suffix); info = s.info
        h = s.history(period="6mo").reset_index()
        if not h.empty:
            df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
            pe = info.get('trailingPE') or info.get('forwardPE') or "N/A"
            pb = info.get('priceToBook') or "N/A"
            raw_ind = info.get('industry') or info.get('sector') or "N/A"
            # Dịch ngành sang Tiếng Việt cứng
            ind = next((v for k, v in IND_MAP.items() if k in raw_ind), raw_ind)
    except: pass
    return df, p, pe, pb, ind

# --- 4. GIAO DIỆN PHÍM ENTER (Yêu cầu 16) ---
query = st.text_input("🔍 Nhập mã hoặc Câu hỏi lọc mã (ENTER):", "GEX").upper()

if query:
    model = get_ai_brain()
    if len(query.split()) > 2: # CHẾ ĐỘ CHATBOT CHIẾN LƯỢC
        if model:
            with st.spinner("AI Sovereign đang quét toàn sàn..."):
                prompt = f"Expert Tycoon. Market: Việt Nam. Task: {query}. TRẢ VỀ DANH SÁCH MÃ + GIÁ CỤ THỂ. Không lý thuyết. Tiếng Việt."
                try: st.write(model.generate_content(prompt).text)
                except: st.error("AI đang nghỉ ngơi, thử lại sau 10 giây.")
    else: # CHẾ ĐỘ PHÂN TÍCH MÃ
        with st.spinner(f"Đang đồng bộ dữ liệu {query}..."):
            df, p_now, pe, pb, ind = fetch_data_ultimate(query, "Việt Nam")
            if df is not None and not df.empty:
                # 🤖 GOM LỆNH AI VÀO 1 LẦN GỌI (TIẾT KIỆM QUOTA - FIX image_b90dfa)
                with st.spinner("AI đang tổng hợp báo cáo và chỉ số Ngành..."):
                    try:
                        report = model.generate_content(f"Dữ liệu: {query}, Giá {p_now}, Ngành {ind}. 1. Cho P/E và P/B trung bình ngành {ind} tại VN. 2. Phân tích dòng tiền cá mập. Tiếng Việt.").text
                    except: report = "AI Busy. Report skipped."

                st.success(f"📌 Đã khóa mục tiêu: {query} | Việt Nam")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá Khớp Lệnh", f"{p_now:,.0f}")
                c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Ngành", ind)

                # BIỂU ĐỒ 2 TẦNG (FIX image_abedfa)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Giá"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # HIỂN THỊ BÁO CÁO TỔNG HỢP
                st.subheader("🤖 BÁO CÁO CHIẾN LƯỢC TỔNG HỢP")
                st.write(report)
            else: st.error("Data Not Found.")
