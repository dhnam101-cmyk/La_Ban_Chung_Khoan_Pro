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
st.set_page_config(page_title="AI Terminal V38: Omni-Nexus", layout="wide")

# --- 2. THANH CHỌN THỊ TRƯỜNG ---
m_select = st.sidebar.selectbox("🌍 Chọn thị trường / Market", ["Việt Nam", "Mỹ", "Nhật Bản", "Hàn Quốc", "Trung Quốc"])

# --- 3. TỰ VÁ LỖI AI ---
@st.cache_resource
def get_ai_expert():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m in ['models/gemini-1.5-pro', 'models/gemini-1.5-flash']:
            if m in available: return genai.GenerativeModel(m)
        return genai.GenerativeModel(available[0])
    except: return None

# --- 4. CƠ CHẾ ĐA NỀN TẢNG "BẤT TỬ" ---
def fetch_omnipotent_data(ticker, market):
    sym = ticker.upper().strip()
    df, p, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    if market == "Việt Nam":
        is_vn = True
        try:
            # Ưu tiên lấy giá snapshot VNDirect
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", timeout=2).json()
            if r_p: p = r_p[0]['lastPrice'] * 1000
            # Lấy nến DNSE
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", timeout=2).json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
            # Lấy cơ bản TCBS
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", timeout=2).json()
            pe, pb, ind = r_f.get('pe', 'N/A'), r_f.get('pb', 'N/A'), r_f.get('industry', 'N/A')
        except: pass
    else:
        suffix = {"Mỹ": "", "Nhật Bản": ".T", "Hàn Quốc": ".KS", "Trung Quốc": ".SS"}
        target = sym + suffix[market]
        try:
            s = yf.Ticker(target); h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
                pe, pb, ind = s.info.get('trailingPE', 'N/A'), s.info.get('priceToBook', 'N/A'), s.info.get('industry', 'N/A')
        except: pass
    return df, p, pe, pb, ind, is_vn

# --- 5. GIAO DIỆN XỬ LÝ ---
query = st.text_input(f"Nhập mã tại {m_select}:", "GEX").upper()

if st.button("🚀 KÍCH HOẠT NEXUS"):
    with st.spinner("Đang đồng bộ dữ liệu đa quốc gia..."):
        df, p_now, pe, pb, ind, is_vn = fetch_omnipotent_data(query, m_select)
        
        if df is not None and not df.empty:
            # Chỉ báo Kỹ thuật
            df['MA20'] = ta.sma(df['close'], 20); df['MA200'] = ta.sma(df['close'], 200); df['RSI'] = ta.rsi(df['close'], 14)
            
            st.success(f"📌 Đã khóa mục tiêu: {query} | Nguồn: Đa kênh {m_select}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá", f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
            c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Ngành", ind)

            # BIỂU ĐỒ 2 TẦNG (TÁCH BIỆT 100%)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Nến"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
            fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # AI BÁO CÁO
            model = get_ai_expert()
            if model:
                st.subheader("🤖 BÁO CÁO CHUYÊN GIA")
                st.write(model.generate_content(f"Phân tích {query} tại {m_select}. Giá {p_now}. RSI {df['RSI'].iloc[-1]:.2f}. Soi dòng tiền cá mập.").text)
        else:
            st.error("Lỗi dữ liệu. Vui lòng kiểm tra mã chứng khoán hoặc đổi thị trường.")
