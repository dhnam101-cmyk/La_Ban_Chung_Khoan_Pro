import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP HỆ THỐNG & DỊCH THUẬT ---
st.set_page_config(page_title="AI Terminal V67: AI-Driven", layout="wide")

LABELS = {
    "Tiếng Việt": {"p": "Giá", "pe": "P/E", "pb": "P/B", "pei": "P/E Ngành (AI)", "pbi": "P/B Ngành (AI)", "ind": "Ngành", "msg": "Mã hoặc Câu hỏi và ENTER:"},
    "English": {"p": "Price", "pe": "P/E", "pb": "P/B", "pei": "Ind. P/E (AI)", "pbi": "Ind. P/B (AI)", "ind": "Industry", "msg": "Symbol or Question and ENTER:"}
}

with st.sidebar:
    st.header("⚙️ Sovereign Config")
    lang = st.selectbox("🌐 Ngôn ngữ / Language", list(LABELS.keys()))
    m_config = {
        "Việt Nam": {"suffix": ".VN", "is_intl": False},
        "Mỹ (USA)": {"suffix": "", "is_intl": True}
    }
    m_target = st.selectbox("🌍 Thị trường / Market:", list(m_config.keys()))

# --- 2. BẢO VỆ AI (Self-healing & Anti-Busy - Sửa image_b8ac1f) ---
@st.cache_resource
def get_ai_absolute():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Luôn quét tìm model đang hoạt động để tránh NotFound (image_b8999f)
        alive_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-flash', 'models/gemini-pro', 'models/gemini-1.5-pro']
        for p in priority:
            if p in alive_models: return genai.GenerativeModel(p)
        return genai.GenerativeModel(alive_models[0]) if alive_models else None
    except: return None

# --- 3. DATA ENGINE (Xóa sổ N/A bằng AI - Yêu cầu 2, 15) ---
def fetch_sovereign_data(ticker, market):
    sym = ticker.upper().strip()
    cfg = m_config[market]
    df, p, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", not cfg["is_intl"]

    if is_vn:
        try:
            # Snapshot VNDirect
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", timeout=4).json()
            if r_p: p = r_p[0]['lastPrice'] * 1000
            # TCBS Fundamental
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", timeout=4).json()
            pe, pb, ind = r_f.get('pe', "N/A"), r_f.get('pb', "N/A"), r_f.get('industry', "N/A")
            # Entrade Chart
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", timeout=4).json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
        except: pass

    # FALLBACK DỮ LIỆU TRỐNG
    if df is None or pe == "N/A":
        try:
            s = yf.Ticker(sym + cfg["suffix"]); info = s.info
            if df is None:
                h = s.history(period="6mo").reset_index()
                if not h.empty: df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
            pe = pe if pe != "N/A" else info.get('trailingPE', "N/A")
            pb = pb if pb != "N/A" else info.get('priceToBook', "N/A")
            ind = ind if ind != "N/A" else info.get('industry', "N/A")
        except: pass
            
    return df, p, pe, pb, ind, is_vn

# --- 4. GIAO DIỆN & PHÍM ENTER (Yêu cầu 16) ---
query = st.text_input(f"🔍 {LABELS[lang]['msg']}", "GEX").upper()

if query:
    model = get_ai_absolute()
    if len(query.split()) > 2: # CHATBOT CHIẾN LƯỢC
        if model:
            with st.spinner("AI Sovereign is processing..."):
                try: 
                    st.write(model.generate_content(f"Expert Tycoon. Market {m_target}. List 10 tickers + real prices for: {query}. No theory. Reply in {lang}.").text)
                except: st.error("AI Busy. Please retry in 20s.")
    else: # ANALYZER
        with st.spinner("Syncing Sovereign Data..."):
            df, p_now, pe, pb, ind, is_vn = fetch_sovereign_data(query, m_target)
            if df is not None and not df.empty:
                # 🤖 AI ĐỨNG RA ĐIỀN CHỈ SỐ NGÀNH (Yêu cầu mới)
                with st.spinner("AI is calculating Industry Metrics..."):
                    try:
                        ai_data = model.generate_content(f"Give me current average P/E and P/B for {ind} industry in {m_target}. Format: PE:X | PB:Y. Short only.").text
                        pei = ai_data.split('|')[0].split(':')[-1].strip()
                        pbi = ai_data.split('|')[1].split(':')[-1].strip()
                    except: pei, pbi = "N/A", "N/A"

                st.success(f"📌 {query} | {m_target}")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric(LABELS[lang]['p'], f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
                c2.metric(LABELS[lang]['pe'], pe); c3.metric(LABELS[lang]['pb'], pb)
                c4.metric(LABELS[lang]['pei'], pei); c5.metric(LABELS[lang]['pbi'], pbi)
                c6.metric(LABELS[lang]['ind'], ind)

                # CHART
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Candle"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # AI REPORT
                if model:
                    st.subheader(f"🤖 {lang} Expert Report")
                    try: st.write(model.generate_content(f"Deep analysis: {query} ({m_target}). Price {p_now}. Industry {ind} with Avg P/E {pei}. Lang: {lang}.").text)
                    except: st.warning("AI Overloaded. Report skipped.")
            else: st.error("Data Not Found.")
