import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP ---
st.set_page_config(page_title="AI Terminal V30: Global Sovereign", layout="wide")
L = st.sidebar.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"])

# --- 2. TỰ VÁ LỖI AI (SELF-HEALING) ---
@st.cache_resource
def get_ai_expert():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-pro']
        for m in priority:
            if m in available: return genai.GenerativeModel(m)
        return genai.GenerativeModel(available[0])
    except: return None

# --- 3. RADAR TỔNG LỰC (YÊU CẦU 14: ƯU TIÊN VN > US) ---
def fetch_sovereign_v30(ticker_raw):
    symbol = ticker_raw.upper()
    df, p_real, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    # BƯỚC 1: KIỂM TRA VIỆT NAM TRƯỚC (FIX LỖI GEX)
    try:
        # Gọi Snapshot VNDirect - Nếu có giá thì chắc chắn là mã VN
        snap = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}", timeout=2).json()
        if snap and snap[0]['lastPrice'] != 0:
            is_vn = True
            p_real = snap[0]['lastPrice'] * 1000 # Quy đổi VND
            # Lấy nến & cơ bản
            end = int(time.time())
            res_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={end-15552000}&to={end}&symbol={symbol}&resolution=1D").json()
            df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=2).json()
            pe, pb, ind = r_f.get('pe', 'N/A'), r_f.get('pb', 'N/A'), r_f.get('industry', 'N/A')
    except: pass

    # BƯỚC 2: KHÔNG NGẮT QUỐC TẾ - TÌM MỸ/THẾ GIỚI (NẾU VN KHÔNG CÓ HOẶC LÀ MÃ MỸ)
    if df is None:
        try:
            s = yf.Ticker(symbol)
            h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]
                p_real = df['close'].iloc[-1]; pe = s.info.get('trailingPE', 'N/A'); pb = s.info.get('priceToBook', 'N/A'); ind = s.info.get('industry', 'N/A')
                is_vn = False
        except: pass
        
    return df, p_real, pe, pb, ind, is_vn

# --- 4. VĨ MÔ & HÀNG HÓA (CHỈ GỌI KHI LIÊN QUAN) ---
def fetch_context_intel(industry):
    intel = {"macro": {}, "commodity": {}}
    for k, s in {"S&P 500": "^GSPC", "DXY": "DX-Y.NYB", "Fed 10Y": "^TNX"}.items():
        try: intel["macro"][k] = round(yf.download(s, period="2d", progress=False)['Close'].iloc[-1], 2)
        except: pass
    if any(x in str(industry) for x in ["Thép", "Steel", "Dầu", "Oil"]):
        for k, s in {"Quặng Sắt": "TIO=F", "Thép HRC": "HRC=F", "Dầu Brent": "BZ=F"}.items():
            try: intel["commodity"][k] = round(yf.download(s, period="2d", progress=False)['Close'].iloc[-1], 2)
            except: pass
    return intel

# --- 5. GIAO DIỆN ---
query = st.text_input("Mã (GEX, NVDA, 7203.T) hoặc Câu hỏi:", "GEX").upper()

if st.button("🚀 KÍCH HOẠT TỔNG LỰC"):
    with st.spinner("Đang định vị mã và dữ liệu toàn cầu..."):
        if len(query.split()) == 1: # Xử lý mã CK
            df, p_now, pe, pb, ind, is_vn = fetch_sovereign_v30(query)
            if df is not None:
                # Chỉ báo Kỹ thuật 13 yêu cầu
                df['MA20']=ta.sma(df['close'],20); df['MA50']=ta.sma(df['close'],50); df['MA200']=ta.sma(df['close'],200)
                df['RSI']=ta.rsi(df['close'],14); m=ta.macd(df['close']); df['MACD']=m.iloc[:,0]
                intel = fetch_context_intel(ind)
                
                # Dashboard
                st.info(f"🌐 Thị trường: {('Việt Nam' if is_vn else 'Quốc tế')} | Ngành: {ind}")
                c1,c2,c3,c4 = st.columns(4); c1.metric("Giá", f"{p_now:,.0f}" if is_vn else f"{p_now:,.2f}")
                c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Vĩ mô", str(intel['macro']))
                
                # BIỂU ĐỒ 2 TẦNG (FIX LỖI MẤT BIỂU ĐỒ)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Nến"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False,
