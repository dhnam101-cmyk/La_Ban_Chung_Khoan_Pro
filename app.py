import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP HỆ THỐNG ---
st.set_page_config(page_title="AI Terminal V58: Sovereign Vanguard", layout="wide")

# --- 2. SIDEBAR CONFIG (Yêu cầu 1, 17) ---
with st.sidebar:
    st.header("⚙️ Configuration")
    lang = st.selectbox("🌐 Language / Ngôn ngữ", ["Tiếng Việt", "English", "日本語", "한국어", "中文"])
    m_config = {
        "Việt Nam": {"suffix": "", "is_intl": False},
        "Mỹ (USA)": {"suffix": "", "is_intl": True},
        "Nhật Bản": {"suffix": ".T", "is_intl": True},
        "Hàn Quốc": {"suffix": ".KS", "is_intl": True},
        "Trung Quốc": {"suffix": ".SS", "is_intl": True}
    }
    m_target = st.selectbox("🌍 Thị trường / Market:", list(m_config.keys()))

# --- 3. FIX LỖI ResourceExhausted (Yêu cầu 11) ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        priority = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        models = [m.name for m in genai.list_models()]
        for p in priority:
            if p in models: return genai.GenerativeModel(p)
        return None
    except: return None

# --- 4. GIAO THỨC VANGUARD (VƯỢT RÀO CẢN DỮ LIỆU) ---
def fetch_vanguard_data(ticker, market_name):
    sym = ticker.upper().strip()
    cfg = m_config[market_name]
    df, p, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    # Header giả lập người dùng thật để tránh bị chặn
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    if not cfg["is_intl"]: # CHẾ ĐỘ VIỆT NAM: KHÓA CHẶT QUỐC TẾ
        is_vn = True
        try:
            # 1. Snapshot VNDirect (Vòi chính)
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", headers=headers, timeout=10).json()
            if r_p: p = r_p[0]['lastPrice'] * 1000
            
            # 2. Nến & Volume Entrade
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", headers=headers, timeout=10).json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
            
            # 3. Chỉ số tài chính TCBS
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", headers=headers, timeout=10).json()
            pe, pb, ind = r_f.get('pe', "N/A"), r_f.get('pb', "N/A"), r_f.get('industry', "N/A")
        except Exception as e:
            print(f"VN Error: {e}")
    else: # QUỐC TẾ
        target = sym + cfg["suffix"]
        try:
            s = yf.Ticker(target); h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
                pe = s.info.get('trailingPE') or "N/A"; pb = s.info.get('priceToBook') or "N/A"
                ind = s.info.get('industry') or "N/A"
        except: pass
    return df, p, pe, pb, ind, is_vn

# --- 5. GIAO DIỆN PHÍM ENTER (Yêu cầu 16) ---
query = st.text_input(f"🔍 {'Mã hoặc Câu hỏi và ENTER' if lang == 'Tiếng Việt' else 'Symbol or Query and ENTER'}:", "GEX").upper()

if query:
    if len(query.split()) > 1: # CHATBOT CHIẾN LƯỢC (Yêu cầu 13)
        model = get_ai_brain()
        if model:
            with st.spinner("AI Sovereign is scanning market for specific stocks..."):
                prompt = f"Act as a professional financial expert. For the {m_target} market, provide a specific list of 10 stocks for this query: {query}. INCLUDE SYMBOLS AND PRICES. No general theory. Language: {lang}."
                st.write(model.generate_content(prompt).text)
    else: # PHÂN TÍCH MÃ ĐƠN LẺ
        with st.spinner(f"Synchronizing {query} real-time data..."):
            df, p_now, pe, pb, ind, is_vn = fetch_vanguard_data(query, m_target)
            if df is not None and not df.empty:
                for m in [10, 20, 50, 100, 200]: df[f'MA{m}'] = ta.sma(df['close'], m)
                df['RSI'] = ta.rsi(df['close'], 14)
                
                st.success(f"📌 {query} | {m_target}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá / Price", f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
                c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Ngành / Industry", ind)

                # BIỂU ĐỒ 2 TẦNG (Yêu cầu 5)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['date'], y=df['MA200'], line=dict(color='red', width=1.5), name="MA200"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # BÁO CÁO AI (Yêu cầu 10)
                model = get_ai_brain()
                if model:
                    st.subheader(f"🤖 AI Expert Report ({lang})")
                    st.write(model.generate_content(f"Pro analysis of {query} ({m_target}). Price {p_now}. Sector {ind}. Language: {lang}.").text)
            else:
                st.error("Data Not Found. Please check market selection or ticker symbol.")
