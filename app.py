import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP & TRANSLATION ---
st.set_page_config(page_title="AI Terminal V63: Final Command", layout="wide")

T = {
    "Tiếng Việt": {"p": "Giá", "pe": "P/E", "pb": "P/B", "pei": "P/E Ngành", "pbi": "P/B Ngành", "ind": "Ngành", "msg": "Nhập mã/câu hỏi và ENTER"},
    "English": {"p": "Price", "pe": "P/E", "pb": "P/B", "pei": "Ind. P/E", "pbi": "Ind. P/B", "ind": "Industry", "msg": "Enter Symbol/Query and ENTER"}
}

with st.sidebar:
    st.header("⚙️ System Config")
    lang = st.selectbox("🌐 Ngôn ngữ", list(T.keys()))
    m_config = {
        "Việt Nam": {"suffix": ".VN", "is_intl": False},
        "Mỹ (USA)": {"suffix": "", "is_intl": True}
    }
    m_target = st.selectbox("🌍 Thị trường", list(m_config.keys()))

# --- 2. KHÁNG LỖI AI NOTFOUND (Sửa image_b83b87) ---
@st.cache_resource
def get_ai_sovereign():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Quét động danh sách model đang sống
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
        for p in priority:
            if p in models: return genai.GenerativeModel(p)
        return genai.GenerativeModel(models[0]) if models else None
    except: return None

# --- 3. DATA ENGINE (Xóa sổ N/A & Thêm chỉ số Ngành) ---
def fetch_sovereign_data(ticker, market):
    sym = ticker.upper().strip()
    cfg = m_config[market]
    df, p, pe, pb, pei, pbi, ind, is_vn = None, 0, "N/A", "N/A", "N/A", "N/A", "N/A", not cfg["is_intl"]

    if is_vn:
        try:
            # Tầng 1: VNDirect Snapshot
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", timeout=3).json()
            if r_p: p = r_p[0]['lastPrice'] * 1000
            # Tầng 2: TCBS Fundamental (Thêm chỉ số ngành)
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", timeout=3).json()
            pe, pb, ind = r_f.get('pe', "N/A"), r_f.get('pb', "N/A"), r_f.get('industry', "N/A")
            # Vét dữ liệu Ngành từ TCBS
            pei, pbi = r_f.get('industryPe', "N/A"), r_f.get('industryPb', "N/A")
            # Tầng 3: Entrade Chart
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", timeout=3).json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
        except: pass

    # Tầng 4: Fallback Yahoo (Fix N/A - image_b82d1b)
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
            
    return df, p, pe, pb, pei, pbi, ind, is_vn

# --- 4. INTERFACE ---
query = st.text_input(f"🔍 {T[lang]['msg']}:", "GEX").upper()

if query:
    if len(query.split()) > 2: # CHATBOT LỌC MÃ
        model = get_ai_sovereign()
        if model:
            with st.spinner("AI is analyzing..."):
                prompt = f"Expert Tycoon Mode. List 10 specific stocks for: {query} in {m_target}. Reply in {lang}."
                st.write(model.generate_content(prompt).text)
    else: # ANALYZER
        with st.spinner("Loading Sovereign Data..."):
            df, p_now, pe, pb, pei, pbi, ind, is_vn = fetch_sovereign_data(query, m_target)
            if df is not None and not df.empty:
                df['MA20'] = ta.sma(df['close'], 20); df['MA200'] = ta.sma(df['close'], 200)
                
                st.success(f"📌 {query} | {m_target}")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric(T[lang]['p'], f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
                c2.metric(T[lang]['pe'], pe); c3.metric(T[lang]['pb'], pb)
                c4.metric(T[lang]['pei'], pei); c5.metric(T[lang]['pbi'], pbi)
                c6.metric(T[lang]['ind'], ind)

                # BIỂU ĐỒ 2 TẦNG (Fix Indent)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Candle"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # BÁO CÁO AI (Fix NotFound - image_b83b87)
                model = get_ai_sovereign()
                if model:
                    st.subheader(f"🤖 {lang} Expert Report")
                    st.write(model.generate_content(f"Deep analysis: {query} ({m_target}). Price: {p_now}. RSI: {ta.rsi(df['close'], 14).iloc[-1]:.2f}. Lang: {lang}.").text)
            else: st.error("Data Not Found.")
