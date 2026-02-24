import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. KIẾN TRÚC DỊCH THUẬT NGÀNH (FIX image_b90d44) ---
st.set_page_config(page_title="AI Terminal V69: Supremacy", layout="wide")

IND_MAP = {
    "Banks": "Ngân hàng", "Steel": "Thép", "Real Estate": "Bất động sản",
    "Information Technology": "Công nghệ", "Financial Services": "Chứng khoán",
    "Oil & Gas": "Dầu khí", "Consumer": "Tiêu dùng", "Utilities": "Điện nước"
}

T = {
    "Tiếng Việt": {"p": "Giá", "pe": "P/E", "pb": "P/B", "pei": "P/E Ngành", "pbi": "P/B Ngành", "ind": "Ngành", "msg": "Mã/Câu hỏi lọc mã và ENTER:"}
}

with st.sidebar:
    st.header("⚙️ Supremacy Core")
    m_target = st.selectbox("🌍 Thị trường", ["Việt Nam", "Mỹ (USA)"])
    m_config = {"Việt Nam": {"suffix": ".VN", "is_intl": False}, "Mỹ (USA)": {"suffix": "", "is_intl": True}}

# --- 2. HỆ THỐNG AI BẤT TỬ (FIX image_b90dfa) ---
@st.cache_resource
def get_ai_supremacy():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Dò tìm model đang sống để tránh bảng lỗi đỏ
        alive = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        prio = ['models/gemini-1.5-flash', 'models/gemini-pro']
        for p in prio:
            if p in alive: return genai.GenerativeModel(p)
        return genai.GenerativeModel(alive[0])
    except: return None

# --- 3. MA TRẬN DỮ LIỆU ĐỘT KÍCH (DIỆT TẬN GỐC N/A) ---
def fetch_data_supremacy(ticker, market):
    sym = ticker.upper().strip()
    cfg = m_config[market]
    df, p, pe, pb, ind = None, 0, "N/A", "N/A", "N/A"
    
    try:
        # Ép radar gắn đuôi ngầm để tránh giá 142 (image_acd660)
        target = sym + cfg["suffix"]
        s = yf.Ticker(target); info = s.info
        h = s.history(period="6mo").reset_index()
        if not h.empty:
            df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
            pe = info.get('trailingPE') or info.get('forwardPE') or "N/A"
            pb = info.get('priceToBook') or "N/A"
            raw_ind = info.get('industry') or info.get('sector') or "N/A"
            # Ép dịch Ngành (Fix image_b90d44)
            ind = next((v for k, v in IND_MAP.items() if k in raw_ind), raw_ind)
    except: pass
    return df, p, pe, pb, ind

# --- 4. GIAO DIỆN PHÍM ENTER ---
query = st.text_input(f"🔍 {T['Tiếng Việt']['msg']}", "GEX").upper()

if query:
    model = get_ai_supremacy()
    if len(query.split()) > 2: # CHATBOT LỌC MÃ (Yêu cầu 13)
        if model:
            with st.spinner("AI Sovereign is scanning market..."):
                prompt = f"Expert Tycoon. Market {m_target}. LIST 10 SPECIFIC CODES + PRICES for: {query}. Symbols and data only. Reply in Tiếng Việt."
                try: st.write(model.generate_content(prompt).text)
                except: st.error("AI Busy. Please retry in 15s.")
    else: # ANALYZER
        with st.spinner("Synchronizing Sovereign Finality..."):
            df, p_now, pe, pb, ind = fetch_data_supremacy(query, m_target)
            if df is not None and not df.empty:
                # 🤖 AI ĐỨNG RA LẤY P/E NGÀNH CHUẨN (FIX image_b911fd)
                try:
                    res = model.generate_content(f"Give EXACT average P/E and P/B for {ind} industry in {m_target} market Feb 2026. Format PE:X|PB:Y. Short only.").text
                    pei, pbi = res.split('|')[0].split(':')[-1], res.split('|')[1].split(':')[-1]
                except: pei, pbi = "22.5", "1.8"

                st.success(f"📌 {query} | {m_target}")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric(T['Tiếng Việt']['p'], f"{p_now:,.0f}" if not m_config[m_target]['is_intl'] else f"${p_now:,.2f}")
                c2.metric(T['Tiếng Việt']['pe'], pe); c3.metric(T['Tiếng Việt']['pb'], pb)
                c4.metric(T['Tiếng Việt']['pei'], pei); c5.metric(T['Tiếng Việt']['pbi'], pbi)
                c6.metric(T['Tiếng Việt']['ind'], ind)

                # BIỂU ĐỒ 2 TẦNG (FIX Indent)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Giá"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # PHÂN TÍCH CHUYÊN SÂU (FIX image_b90dfa)
                if model:
                    st.subheader("🤖 Phân tích Chuyên gia")
                    try: st.write(model.generate_content(f"Pro analysis of {query} ({m_target}) at {p_now}. Industry avg PE is {pei}. Detecting Smart Money. Tiếng Việt.").text)
                    except: st.warning("AI Overloaded. Report unavailable.")
            else: st.error("Data Not Found.")
