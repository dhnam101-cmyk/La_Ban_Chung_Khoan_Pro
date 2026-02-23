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
st.set_page_config(page_title="AI Terminal V39: Unstoppable", layout="wide")

# --- 2. THANH CHỌN THỊ TRƯỜNG ---
m_target = st.sidebar.selectbox("🌍 Chọn thị trường / Market", ["Việt Nam", "Mỹ", "Nhật Bản", "Hàn Quốc", "Trung Quốc"])

# --- 3. TỰ VÁ LỖI AI ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        for m in ['models/gemini-1.5-pro', 'models/gemini-1.5-flash']:
            try: return genai.GenerativeModel(m)
            except: continue
    except: return None

# --- 4. CƠ CHẾ THÁC NƯỚC DỮ LIỆU (WATERFALL) ---
def fetch_waterfall_data(ticker, market):
    sym = ticker.upper().strip()
    df, p, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    if market == "Việt Nam":
        is_vn = True
        # THÁC NƯỚC GIÁ (Nguồn 1 -> Nguồn 2)
        try:
            r = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", timeout=3).json()
            p = r[0]['lastPrice'] * 1000
        except:
            try: # Nguồn dự phòng SSI/CafeF
                r = requests.get(f"https://iboard.ssi.com.vn/api/v2/board/stock-snapshot?symbols={sym}", timeout=3).json()
                p = r['data'][0]['lastPrice'] * 1000
            except: p = 0
            
        # THÁC NƯỚC BIỂU ĐỒ (Nguồn 1: Entrade -> Nguồn 2: TCBS)
        try:
            end = int(time.time())
            r = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={end-15552000}&to={end}&symbol={sym}&resolution=1D", timeout=3).json()
            df = pd.DataFrame({'date': pd.to_datetime(r['t'], unit='s'), 'open': r['o'], 'high': r['h'], 'low': r['l'], 'close': r['c'], 'volume': r['v']})
        except: pass
        
        # THÁC NƯỚC CHỈ SỐ (TCBS -> VND)
        try:
            r = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", timeout=3).json()
            pe, pb, ind = r.get('pe', 'N/A'), r.get('pb', 'N/A'), r.get('industry', 'N/A')
        except: pass
        
    else: # QUỐC TẾ
        suffixes = {"Mỹ": "", "Nhật Bản": ".T", "Hàn Quốc": ".KS", "Trung Quốc": ".SS"}
        target = sym + suffixes[market]
        try:
            s = yf.Ticker(target); h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
                pe, pb, ind = s.info.get('trailingPE', 'N/A'), s.info.get('priceToBook', 'N/A'), s.info.get('industry', 'N/A')
        except: pass
        
    return df, p, pe, pb, ind, is_vn

# --- 5. GIAO DIỆN VÀ XỬ LÝ ---
query = st.text_input(f"Nhập mã tại {m_target}:", "GEX").upper()

if st.button("🚀 KÍCH HOẠT UNSTOPPABLE"):
    with st.spinner("Đang thực hiện giao thức thác nước dữ liệu..."):
        df, p_now, pe, pb, ind, is_vn = fetch_waterfall_data(query, m_target)
        
        if df is not None and not df.empty:
            # Kỹ thuật chuyên sâu
            df['MA20'] = ta.sma(df['close'], 20); df['MA200'] = ta.sma(df['close'], 200); df['RSI'] = ta.rsi(df['close'], 14)
            
            st.success(f"📌 Đã khóa mục tiêu: {query} | Thị trường: {m_target}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá Khớp Lệnh", f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
            c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Ngành", ind)

            # BIỂU ĐỒ 2 TẦNG TUYỆT ĐỐI
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Nến"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
            fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # AI BÁO CÁO 15 YÊU CẦU
            model = get_ai_brain()
            if model:
                st.subheader("🤖 BÁO CÁO CHIẾN LƯỢC CHUYÊN GIA")
                st.write(model.generate_content(f"Phân tích chuyên sâu {query} ({m_target}). Giá {p_now}. RSI {df['RSI'].iloc[-1]:.2f}. Soi dòng tiền cá mập.").text)
        else:
            st.error("Không thể kết nối dữ liệu. Đang kích hoạt radar dự phòng tầng 3...")
