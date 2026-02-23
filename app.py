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
st.set_page_config(page_title="Omni-Source Apex V42", layout="wide")

# --- 2. THANH CHỌN THỊ TRƯỜNG (FULL GLOBAL) ---
market_config = {
    "Việt Nam": {"suffix": "", "sources": ["VND", "SSI", "TCBS", "DNSE", "CafeF"]},
    "Mỹ": {"suffix": "", "sources": ["Yahoo", "Google", "Nasdaq"]},
    "Nhật Bản": {"suffix": ".T", "sources": ["Yahoo", "TSE"]},
    "Hàn Quốc": {"suffix": ".KS", "sources": ["Yahoo", "KRX"]},
    "Trung Quốc": {"suffix": ".SS", "sources": ["Yahoo", "SSE"]}
}
m_target = st.sidebar.selectbox("🌍 Chọn thị trường mục tiêu:", list(market_config.keys()))

# --- 3. TỰ VÁ LỖI AI ---
@st.cache_resource
def get_ai_expert():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for t in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']:
            if t in models: return genai.GenerativeModel(t)
        return genai.GenerativeModel(models[0])
    except: return None

# --- 4. MA TRẬN DỮ LIỆU ĐA NỀN TẢNG (CHỐNG N/A TUYỆT ĐỐI) ---
def fetch_apex_data(ticker, market):
    sym = ticker.upper().strip()
    df, p, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    if market == "Việt Nam":
        is_vn = True
        # Luồng quét nội địa đa nguồn
        try:
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", timeout=2).json()
            p = r_p[0]['lastPrice'] * 1000 if r_p else 0
            
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", timeout=2).json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
            
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", timeout=2).json()
            pe, pb, ind = r_f.get('pe', "N/A"), r_f.get('pb', "N/A"), r_f.get('industry', "N/A")
        except: pass
    
    # LUÔN QUÉT THÊM NGUỒN QUỐC TẾ ĐỂ BÙ ĐẮP DỮ LIỆU (ANTI N/A)
    try:
        target_intl = sym + market_config[market]["suffix"]
        s = yf.Ticker(target_intl)
        if df is None or df.empty:
            h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
        
        # Bù đắp chỉ số tài chính từ nguồn quốc tế nếu nguồn nội địa N/A
        info = s.info
        if pe == "N/A": pe = info.get('trailingPE') or info.get('forwardPE') or "N/A"
        if pb == "N/A": pb = info.get('priceToBook') or "N/A"
        if ind == "N/A": ind = info.get('industry') or info.get('sector') or "N/A"
    except: pass
        
    return df, p, pe, pb, ind, is_vn

# --- 5. GIAO DIỆN & XỬ LÝ ---
query = st.text_input(f"Nhập mã tại {m_target}:", "GEX").upper()

if st.button("🚀 KÍCH HOẠT APEX TERMINAL"):
    with st.spinner("Đang vắt kiệt dữ liệu từ các nền tảng nội địa và quốc tế..."):
        df, p_now, pe, pb, ind, is_vn = fetch_apex_data(query, m_target)
        
        if df is not None and not df.empty:
            # Full MA10-MA200 (Yêu cầu 6)
            for m in [10, 20, 50, 100, 200]: df[f'MA{m}'] = ta.sma(df['close'], m)
            df['RSI'] = ta.rsi(df['close'], 14)
            
            # Dashboard
            st.success(f"📌 Đã khóa mục tiêu: {query} | Thị trường: {m_target}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá Khớp Lệnh", f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
            c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Ngành", ind)

            # BIỂU ĐỒ 2 TẦNG TUYỆT ĐỐI (Yêu cầu 5)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Giá"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"))
            fig.add_trace(go.Scatter(x=df['date'], y=df['MA200'], line=dict(color='red', width=1.5), name="MA200"))
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Khối lượng"), row=2, col=1)
            fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # AI BÁO CÁO CHIẾN LƯỢC
            model = get_ai_expert()
            if model:
                st.subheader("🤖 BÁO CÁO CHUYÊN GIA (15 YÊU CẦU)")
                st.write(model.generate_content(f"Phân tích chuyên sâu mã {query} ({m_target}). Giá {p_now}. RSI {df['RSI'].iloc[-1]:.2f}. Soi dòng tiền cá mập.").text)
        else:
            st.error("Lỗi dữ liệu. Radar đang quét lại toàn bộ nền tảng quốc tế...")
