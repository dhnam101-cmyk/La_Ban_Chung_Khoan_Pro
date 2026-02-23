import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP GIAO DIỆN ---
st.set_page_config(page_title="Omni-Nexus V45: Final", layout="wide")

# --- 2. NÚT CHỌN THỊ TRƯỜNG TOÀN CẦU (Yêu cầu mới: Đủ các sàn) ---
market_config = {
    "Việt Nam": {"suffix": "", "is_intl": False},
    "Mỹ (NYSE/NASDAQ)": {"suffix": "", "is_intl": True},
    "Nhật Bản (TSE)": {"suffix": ".T", "is_intl": True},
    "Hàn Quốc (KRX)": {"suffix": ".KS", "is_intl": True},
    "Trung Quốc (SSE/SZSE)": {"suffix": ".SS", "is_intl": True},
    "Hồng Kông (HKEX)": {"suffix": ".HK", "is_intl": True},
    "Anh (LSE)": {"suffix": ".L", "is_intl": True},
    "Đức (XETRA)": {"suffix": ".DE", "is_intl": True},
    "Pháp (Euronext)": {"suffix": ".PA", "is_intl": True},
    "Canada (TSX)": {"suffix": ".TO", "is_intl": True},
    "Úc (ASX)": {"suffix": ".AX", "is_intl": True},
    "Ấn Độ (NSE)": {"suffix": ".NS", "is_intl": True}
}
m_target = st.sidebar.selectbox("🌍 Chọn sàn giao dịch điện tử:", list(market_config.keys()))

# --- 3. FIX LỖI AI (Sửa lỗi NotFound tại image_ab6773) ---
@st.cache_resource
def get_ai_expert():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Quét động các model đang sống để tránh lỗi NotFound
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
        for target in priority:
            if target in models: return genai.GenerativeModel(target)
        return genai.GenerativeModel(models[0]) if models else None
    except: return None

# --- 4. GIAO THỨC ĐA NỀN TẢNG (CHỐNG N/A & SAI GIÁ GEX) ---
def fetch_nexus_data(ticker, market_name):
    sym = ticker.upper().strip()
    cfg = market_config[market_name]
    df, p, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    if not cfg["is_intl"]: # CHẾ ĐỘ VIỆT NAM (Fix GEX ra 142 tại image_ab7d3f)
        is_vn = True
        try:
            # Ưu tiên lấy giá snapshot VNDirect (Fix giá 0 tại image_ab6af9)
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", timeout=3).json()
            if r_p: p = r_p[0]['lastPrice'] * 1000
            # Lấy nến & chỉ số cơ bản
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", timeout=3).json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", timeout=3).json()
            pe, pb, ind = r_f.get('pe', "N/A"), r_f.get('pb', "N/A"), r_f.get('industry', "N/A")
            # Nếu VN trống, soi thêm nguồn quốc tế để bù đắp (Anti N/A)
            if pe == "N/A" or pb == "N/A":
                s_fb = yf.Ticker(f"{sym}.VN")
                pe = pe if pe != "N/A" else s_fb.info.get('trailingPE', "N/A")
                pb = pb if pb != "N/A" else s_fb.info.get('priceToBook', "N/A")
        except: pass
    else: # CHẾ ĐỘ QUỐC TẾ
        target = sym + cfg["suffix"]
        try:
            s = yf.Ticker(target); h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
                info = s.info
                pe = info.get('trailingPE') or info.get('forwardPE') or "N/A"
                pb = info.get('priceToBook') or "N/A"
                ind = info.get('industry') or info.get('sector') or "N/A"
        except: pass
    return df, p, pe, pb, ind, is_vn

# --- 5. GIAO DIỆN XỬ LÝ ---
query = st.text_input(f"Nhập mã tại {m_target}:", "GEX").upper()

if st.button("🚀 KÍCH HOẠT OMNI-NEXUS"):
    with st.spinner("Đang đồng bộ đa nền tảng..."):
        df, p_now, pe, pb, ind, is_vn = fetch_nexus_data(query, m_target)
        
        if df is not None and not df.empty:
            # Full bộ chỉ báo kỹ thuật (Yêu cầu 6)
            for m in [10, 20, 50, 100, 200]: df[f'MA{m}'] = ta.sma(df['close'], m)
            df['RSI'] = ta.rsi(df['close'], 14)
            
            # Dashboard (Fix N/A tại image_ab7d3f)
            st.success(f"📌 Đã khóa mục tiêu: {query} | Sàn: {m_target}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá", f"{p_now:,.0f}" if is_vn else f"{p_now:,.2f}")
            c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Ngành", ind)

            # BIỂU ĐỒ 2 TẦNG (Sửa lỗi Indentation tại image_ab819f)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Nến"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="
