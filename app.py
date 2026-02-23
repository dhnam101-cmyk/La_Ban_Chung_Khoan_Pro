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
st.set_page_config(page_title="AI Terminal V57: Sovereign Iron Curtain", layout="wide")

# --- 2. SIDEBAR CONFIG (Yêu cầu 1, 17) ---
with st.sidebar:
    st.header("⚙️ Configuration")
    lang = st.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English", "日本語", "한국어", "中文"])
    m_config = {
        "Việt Nam": {"suffix": "", "is_intl": False},
        "Mỹ (USA)": {"suffix": "", "is_intl": True},
        "Nhật Bản": {"suffix": ".T", "is_intl": True},
        "Hàn Quốc": {"suffix": ".KS", "is_intl": True},
        "Trung Quốc": {"suffix": ".SS", "is_intl": True}
    }
    m_target = st.selectbox("🌍 Thị trường / Market:", list(m_config.keys()))

# --- 3. KHÁNG SẬP AI (Yêu cầu 11, 13) ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Ưu tiên bản Flash để tránh lỗi ResourceExhausted (429) khi lọc mã nặng
        priority = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        models = [m.name for m in genai.list_models()]
        for p in priority:
            if p in models: return genai.GenerativeModel(p)
        return None
    except: return None

# --- 4. CƠ CHẾ "BỨC MÀN SẮT" DỮ LIỆU (Yêu cầu 2, 3, 15) ---
def fetch_sovereign_data(ticker, market_name):
    sym = ticker.upper().strip()
    cfg = m_config[market_name]
    df, p, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    if not cfg["is_intl"]: # CHẾ ĐỘ VIỆT NAM: KHÓA CHẶT QUỐC TẾ
        is_vn = True
        try:
            # Snapshot thô từ VNDirect (Vòi chính)
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", timeout=5).json()
            if r_p: p = r_p[0]['lastPrice'] * 1000
            
            # Nến & Volume thô từ Entrade (Chống lỗi Data Not Found)
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", timeout=5).json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
            
            # Chỉ số tài chính thô từ TCBS
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", timeout=5).json()
            pe, pb, ind = r_f.get('pe', "N/A"), r_f.get('pb', "N/A"), r_f.get('industry', "N/A")
        except: pass
    else: # THẾ GIỚI
        target = sym + cfg["suffix"]
        try:
            s = yf.Ticker(target); h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
                pe = s.info.get('trailingPE') or "N/A"; pb = s.info.get('priceToBook') or "N/A"; ind = s.info.get('industry') or "N/A"
        except: pass
    return df, p, pe, pb, ind, is_vn

# --- 5. GIAO DIỆN PHÍM ENTER (Yêu cầu 16) ---
query = st.text_input(f"🔍 {'Mã hoặc Câu hỏi và ENTER' if lang == 'Tiếng Việt' else 'Symbol or Query and ENTER'}:", "GEX").upper()

if query:
    if len(query.split()) > 1: # CHATBOT CHIẾN LƯỢC (Yêu cầu 13)
        model = get_ai_brain()
        if model:
            with st.spinner("AI Sovereign is scanning real-time market data..."):
                try:
                    # Ép AI cung cấp mã thực tế, không lý thuyết
                    prompt = f"Act as a financial tycoon. In {m_target}, list 10 tickers for: {query}. GIVE SYMBOLS AND PRICES ONLY. No theory. Language: {lang}."
                    st.write(model.generate_content(prompt).text)
                except Exception as e: st.error(f"AI Limit Error: {e}")
    else: # PHÂN TÍCH MÃ ĐƠN LẺ
        with st.spinner(f"Locking target {query}..."):
            df, p_now, pe, pb, ind, is_vn = fetch_sovereign_data(query, m_target)
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
                    st.write(model.generate_content(f"Pro analysis of {query} ({m_target}). Price {p_now}. RSI {df['RSI'].iloc[-1]:.2f}. Sector {ind}. Language: {lang}.").text)
            else:
                st.error("Data Not Found. Please check market selection or ticker.")
