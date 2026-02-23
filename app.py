import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. KIẾN TRÚC DỊCH THUẬT (Yêu cầu 12, 17) ---
st.set_page_config(page_title="AI Terminal V65: Singularity", layout="wide")

LABELS = {
    "Tiếng Việt": {"p": "Giá", "pe": "P/E", "pb": "P/B", "pei": "P/E Ngành", "pbi": "P/B Ngành", "ind": "Ngành", "ask": "Nhập mã/câu hỏi lọc mã và ENTER:"},
    "English": {"p": "Price", "pe": "P/E", "pb": "P/B", "pei": "Ind. P/E", "pbi": "Ind. P/B", "ind": "Industry", "ask": "Enter symbol/query and press ENTER:"},
    "日本語": {"p": "価格", "pe": "収益率", "pb": "純資産倍率", "pei": "業界収益率", "pbi": "業界純資産倍率", "ind": "業界", "ask": "シンボルを入力してENTER:"}
}

with st.sidebar:
    st.header("⚙️ Core Engine")
    lang = st.selectbox("🌐 Language", list(LABELS.keys()))
    m_config = {
        "Việt Nam": {"suffix": ".VN", "is_intl": False},
        "Mỹ (USA)": {"suffix": "", "is_intl": True}
    }
    m_target = st.selectbox("🌍 Market", list(m_config.keys()))

# --- 2. GIAO THỨC AI BẤT TỬ (Fix 404/Resource - image_b8999f) ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Luôn quét danh sách model khả dụng thực tế thay vì gọi tên cứng
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-flash', 'models/gemini-pro', 'models/gemini-1.5-pro']
        for p in priority:
            if p in available_models: return genai.GenerativeModel(p)
        return genai.GenerativeModel(available_models[0]) if available_models else None
    except: return None

# --- 3. MA TRẬN DỮ LIỆU ĐA TẦNG (Xóa sổ N/A Ngành - image_b89920) ---
def fetch_singularity_data(ticker, market):
    sym = ticker.upper().strip()
    cfg = m_config[market]
    df, p, pe, pb, pei, pbi, ind, is_vn = None, 0, "N/A", "N/A", "N/A", "N/A", "N/A", not cfg["is_intl"]

    if is_vn:
        try:
            # Snapshot giá thực từ VNDirect (Vòi chính)
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", timeout=3).json()
            if r_p: p = r_p[0]['lastPrice'] * 1000
            
            # Lấy chỉ số Ngành & Fundamentals từ TCBS (Fix image_b89920)
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", timeout=3).json()
            pe, pb, ind = r_f.get('pe', "N/A"), r_f.get('pb', "N/A"), r_f.get('industry', "N/A")
            pei = r_f.get('industryPe') or "N/A"
            pbi = r_f.get('industryPb') or "N/A"
            
            # Biểu đồ nến từ Entrade
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", timeout=3).json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
        except: pass

    # CHẾ ĐỘ "VÉT" CẠN QUỐC TẾ (Chống N/A & DNS Block)
    if df is None or pe == "N/A":
        try:
            target_intl = sym + cfg["suffix"]
            s = yf.Ticker(target_intl); info = s.info
            if df is None:
                h = s.history(period="6mo").reset_index()
                if not h.empty: df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
            pe = pe if pe != "N/A" else info.get('trailingPE', "N/A")
            pb = pb if pb != "N/A" else info.get('priceToBook', "N/A")
            ind = ind if ind != "N/A" else info.get('industry', "N/A")
        except: pass
            
    return df, p, pe, pb, pei, pbi, ind, is_vn

# --- 4. GIAO DIỆN & PHÍM ENTER (Yêu cầu 16) ---
query = st.text_input(f"🔍 {LABELS[lang]['ask']}", "GEX").upper()

if query:
    if len(query.split()) > 2: # CHATBOT LỌC MÃ (Yêu cầu 13)
        model = get_ai_brain()
        if model:
            with st.spinner("AI Sovereign is scanning..."):
                prompt = f"Expert Tycoon. List 10 tickers + prices for: {query} in {m_target}. No theory. Reply in {lang}."
                try: st.write(model.generate_content(prompt).text)
                except: st.error("AI is busy. Please try again.")
    else: # ANALYZER
        with st.spinner("Synchronizing Sovereign Data..."):
            df, p_now, pe, pb, pei, pbi, ind, is_vn = fetch_singularity_data(query, m_target)
            if df is not None and not df.empty:
                # Indicators (Yêu cầu 6)
                df['MA20'] = ta.sma(df['close'], 20); df['MA200'] = ta.sma(df['close'], 200)
                df['RSI'] = ta.rsi(df['close'], 14)
                
                st.success(f"📌 {query} | {m_target}")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric(LABELS[lang]['p'], f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
                c2.metric(LABELS[lang]['pe'], f"{pe:.2f}" if isinstance(pe, (int,float)) else pe)
                c3.metric(LABELS[lang]['pb'], f"{pb:.2f}" if isinstance(pb, (int,float)) else pb)
                c4.metric(LABELS[lang]['pei'], f"{pei:.2f}" if isinstance(pei, (int,float)) else pei)
                c5.metric(LABELS[lang]['pbi'], f"{pbi:.2f}" if isinstance(pbi, (int,float)) else pbi)
                c6.metric(LABELS[lang]['ind'], ind)

                # CHART 2 TẦNG (Yêu cầu 5)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Candle"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # AI REPORT (Fix image_b891d6)
                model = get_ai_brain()
                if model:
                    st.subheader(f"🤖 {lang} Expert Report")
                    try: st.write(model.generate_content(f"Deep analysis: {query} ({m_target}). Price: {p_now}. RSI: {df['RSI'].iloc[-1]:.2f}. Lang: {lang}.").text)
                    except: st.warning("AI Quota limit. Report unavailable.")
            else: st.error("Data Not Found.")
