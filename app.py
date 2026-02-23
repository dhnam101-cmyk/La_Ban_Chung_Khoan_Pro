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
st.set_page_config(page_title="AI Chứng Khoán Toàn Cầu V17", layout="wide")

if 'lang' not in st.session_state: st.session_state.lang = "Tiếng Việt"
L = st.sidebar.selectbox("🌐 Ngôn ngữ", ["Tiếng Việt", "English"], key='lang')

T = {
    "Tiếng Việt": {
        "title": "📈 AI CHỨNG KHOÁN V17: INDUSTRIAL INTELLIGENCE",
        "input": "Nhập mã (HPG, FPT, AAPL, BTC-USD):",
        "btn": "🚀 QUÉT ĐA TẦNG & NGÀNH THẾ GIỚI",
        "p": "Giá Khớp Lệnh", "pe": "P/E", "pb": "P/B", "ind": "Ngành",
        "ai": "BÁO CÁO CHIẾN LƯỢC LIÊN THỊ TRƯỜNG & HÀNG HÓA"
    },
    "English": {
        "title": "📈 AI STOCK V17: INDUSTRIAL INTELLIGENCE",
        "input": "Enter Ticker (HPG, AAPL, etc.):",
        "btn": "🚀 GLOBAL INDUSTRY SCAN",
        "p": "Real-time Price", "pe": "P/E", "pb": "P/B", "ind": "Industry",
        "ai": "COMMODITY & INTER-MARKET REPORT"
    }
}[L]

st.title(T["title"])

# --- 2. TỰ VÁ LỖI AI ---
@st.cache_resource
def get_working_ai_node():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-pro']
        for m in priority:
            if m in available: return genai.GenerativeModel(m)
        return genai.GenerativeModel(available[0])
    except: return None

# --- 3. DỮ LIỆU HÀNG HÓA & VĨ MÔ TOÀN CẦU (COMMODITY RADAR) ---
def fetch_global_industrial_data():
    industrial_data = {}
    # Quét các chỉ số hàng hóa và vĩ mô trọng yếu
    tickers = {
        "Quặng Sắt (Iron Ore)": "TIO=F", 
        "Thép HRC (US)": "HRC=F",
        "Vàng (Gold)": "GC=F",
        "Dầu Brent": "BZ=F",
        "S&P 500": "^GSPC",
        "DXY (Dollar Index)": "DX-Y.NYB"
    }
    for name, sym in tickers.items():
        try:
            val = yf.Ticker(sym).history(period="1d")['Close'].iloc[-1]
            industrial_data[name] = round(val, 2)
        except: industrial_data[name] = "N/A"
    return industrial_data

# --- 4. HỆ THỐNG DỮ LIỆU ĐA NGUỒN ---
def fetch_pro_v17(ticker):
    symbol = ticker.upper()
    is_vn = True
    df, p_real, pe, pb, ind = None, 0, "N/A", "N/A", "N/A"
    
    try:
        # Check VN Market
        check = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}", timeout=1).json()
        if not check: is_vn = False
        else:
            p_real = check[0]['lastPrice'] * 1000
            end = int(time.time())
            url_h = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={end-15552000}&to={end}&symbol={symbol}&resolution=1D"
            res_h = requests.get(url_h).json()
            df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=2).json()
            pe, pb, ind = r_f.get('pe', 'N/A'), r_f.get('pb', 'N/A'), r_f.get('industry', 'N/A')
    except: is_vn = False

    if not is_vn:
        try:
            s = yf.Ticker(symbol)
            df = s.history(period="6mo").reset_index()
            df.columns = [c.lower() for c in df.columns]
            p_real = df['close'].iloc[-1]
            pe, pb, ind = s.info.get('trailingPE', 'N/A'), s.info.get('priceToBook', 'N/A'), s.info.get('industry', 'N/A')
        except: pass

    return df, p_real, pe, pb, ind, is_vn

# --- 5. GIAO DIỆN & XỬ LÝ CHÍNH ---
ticker_in = st.text_input(T["input"], "HPG").upper()

if st.button(T["btn"]):
    with st.spinner("🚀 Đang truy vấn dữ liệu hàng hóa và vĩ mô thế giới..."):
        df, p_now, pe, pb, ind, is_vn = fetch_pro_v17(ticker_in)
        global_data = fetch_global_industrial_data()
        
        if df is not None:
            # Kỹ thuật
            df['MA20'] = ta.sma(df['close'], length=20)
            df['RSI'] = ta.rsi(df['close'], length=14)
            
            # 🌍 TRÌNH DIỄN VĨ MÔ & HÀNG HÓA THẾ GIỚI
            st.markdown("### 🌍 Dữ liệu Hàng hóa & Vĩ mô Thế giới (Thời gian thực)")
            cols = st.columns(len(global_data))
            for i, (name, val) in enumerate(global_data.items()):
                cols[i].metric(name, val)
            
            st.markdown("---")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(T["p"], f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
            c2.metric("P/E", pe)
            c3.metric("P/B", pb)
            c4.metric(T["ind"], ind)

            # ĐỒ THỊ 2 TẦNG
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Nến"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1.5), name="MA20"), row=1, col=1)
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # AI PRO REPORT (GLOBAL INDUSTRIAL SENTINEL)
            st.subheader(f"🤖 {T['ai']} ({L})")
            prompt = f"""Role: Executive Investment Strategist. Language: {L}. 
            Asset: {ticker_in}. Industry: {ind}.
            Real-time Price: {p_now}. P/E: {pe}. P/B: {pb}.
            Indicators: RSI {df['RSI'].iloc[-1]:.2f}, MA20 {df['MA20'].iloc[-1]:.2f}.
            Global Industrial & Macro Context: {global_data}
            
            Requirements:
            1. INDUSTRY CORRELATION: How world commodity prices (Steel/Iron Ore for HPG, Crude Oil for GAS, etc.) impact this stock.
            2. SMART MONEY: Footprints of institutional investors.
            3. TECHNICAL: Chart patterns and RSI/MA20 signals.
            4. GLOBAL MACRO: Impact of S&P500, DXY, and Fed stance on this market.
            5. FINAL VERDICT: Clear Buy/Sell/Hold with target and stop-loss."""
            
            model = get_working_ai_node()
            if model: st.write(model.generate_content(prompt).text)
        else:
            st.error("Không tìm thấy mã này trên mạng lưới dữ liệu.")
