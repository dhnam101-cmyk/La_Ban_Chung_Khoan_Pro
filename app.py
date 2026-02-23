import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 1. SETUP HỆ THỐNG ---
st.set_page_config(page_title="AI Chứng Khoán PRO V13", layout="wide")

if 'lang' not in st.session_state: st.session_state.lang = "Tiếng Việt"
L = st.sidebar.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"], key='lang')

T = {
    "Tiếng Việt": {
        "title": "📈 SIÊU HỆ THỐNG AI CHỨNG KHOÁN PRO V13",
        "input": "Nhập mã (VD: FPT, HPG, AAPL, BTC-USD):",
        "btn": "🚀 KÍCH HOẠT QUÉT ĐA TẦNG TOÀN CẦU",
        "p": "Giá Khớp Lệnh", "pe": "P/E", "pb": "P/B", "ind": "Ngành",
        "chart_y": "Giá", "chart_v": "Dòng tiền", "ai": "BÁO CÁO CHIẾN LƯỢC TỔNG LỰC",
        "loading": "Đang quét dữ liệu đa nguồn và vĩ mô..."
    },
    "English": {
        "title": "📈 AI STOCK EXPERT PRO V13",
        "input": "Enter Ticker (e.g., FPT, AAPL, BTC-USD):",
        "btn": "🚀 ACTIVATE GLOBAL MULTI-SCAN",
        "p": "Real-time Price", "pe": "P/E", "pb": "P/B", "ind": "Industry",
        "chart_y": "Price", "chart_v": "Volume", "ai": "EXECUTIVE STRATEGY REPORT",
        "loading": "Scanning multi-source and macro data..."
    }
}[L]

st.title(T["title"])

# --- 2. TỰ VÁ LỖI AI (CHỐNG LỖI 404) ---
@st.cache_resource
def get_ai_node():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m in ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-pro']:
            if m in available: return genai.GenerativeModel(m)
        return genai.GenerativeModel(available[0]) if available else None
    except: return None

# --- 3. HỆ THỐNG DỮ LIỆU ĐA NGUỒN (ANTI-BLOCK & NO N/A) ---
def get_vn_data(symbol):
    # Lấy nến từ DNSE
    end = int(time.time())
    url_h = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={end-15552000}&to={end}&symbol={symbol}&resolution=1D"
    res_h = requests.get(url_h, timeout=3).json()
    df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
    
    # Lấy giá Real-time từ VND (Snapshot)
    p_real = df['close'].iloc[-1] * 1000 # Giá dự phòng
    try:
        r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}", timeout=2).json()
        if r_p: p_real = r_p[0]['lastPrice'] * 1000
    except: pass

    # Lấy cơ bản từ TCBS
    pe, pb, ind = "N/A", "N/A", "N/A"
    try:
        r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=2).json()
        pe, pb, ind = r_f.get('pe', 'N/A'), r_f.get('pb', 'N/A'), r_f.get('industry', 'N/A')
    except: pass
    
    return df, p_real, pe, pb, ind

def get_global_data(symbol):
    s = yf.Ticker(symbol)
    df = s.history(period="6mo").reset_index()
    df.columns = [c.lower() for c in df.columns]
    p_real = df['close'].iloc[-1]
    info = s.info
    return df, p_real, info.get('trailingPE', 'N/A'), info.get('priceToBook', 'N/A'), info.get('industry', 'N/A')

# --- 4. GIAO DIỆN & XỬ LÝ ---
ticker_in = st.text_input(T["input"], "FPT").upper()

if st.button(T["btn"]):
    with st.spinner(T["loading"]):
        try:
            # Tự động nhận diện thị trường
            is_vn = True
            try:
                # Kiểm tra xem mã có trên sàn VN không bằng cách gọi thử API rẻ tiền nhất
                check = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={ticker_in}&resolution=1D", timeout=1).json()
                if 't' not in check: is_vn = False
            except: is_vn = False

            if is_vn:
                df, p_now, pe, pb, ind = get_vn_data(ticker_in)
                market_label = "Vietnam Stock"
            else:
                df, p_now, pe, pb, ind = get_global_data(ticker_in)
                market_label = "Global Stock"

            # Chỉ báo kỹ thuật
            df['RSI'] = ta.rsi(df['close'], length=14)
            df['EMA20'] = ta.ema(df['close'], length=20)
            
            st.success(f"🌐 {market_label} | ⏱ {time.strftime('%H:%M:%S')}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(T["p"], f"{p_now:,.0f}" if is_vn else f"{p_now:,.2f}")
            c2.metric(T["pe"], pe)
            c3.metric(T["pb"], pb)
            c4.metric(T["ind"], ind)

            # BIỂU ĐỒ 2 TẦNG CHUẨN TRADINGVIEW
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name=T["chart_y"]), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['EMA20'], line=dict(color='yellow', width=1), name="EMA20"), row=1, col=1)
            
            # Cột Volume màu sắc chuẩn nến
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name=T["chart_v"]), row=2, col=1)
            
            fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            fig.update_xaxes(type='date', tickformat="%d %b %y")
            st.plotly_chart(fig, use_container_width=True)

            # AI SIÊU CHUYÊN GIA (EXPERT PROMPT)
            st.subheader(f"🤖 {T['ai']} ({L})")
            prompt = f"""Role: Executive Fund Manager. Language: {L}. Analyze {ticker_in}.
            Data: Price {p_now}, P/E {pe}, P/B {pb}, Industry {ind}.
            Technical: RSI {df['RSI'].iloc[-1]:.2f}, EMA20 {df['EMA20'].iloc[-1]:.2f}.
            Last 10 days Vol list: {df['volume'].tail(10).tolist()}.
            Requirements: 
            1. SMART MONEY: Find Big Boy accumulation/distribution.
            2. TECHNICAL: Detailed trend & patterns.
            3. VALUATION: Peer comparison.
            4. MACD & NEWS: Impact of latest global/local macro news on this stock.
            5. VERDICT: Clear Buy/Sell/Hold with target and stop-loss."""
            
            model = get_ai_node()
            if model: st.write(model.generate_content(prompt).text)
            else: st.error("AI Node Offline. Check API Key.")

        except Exception as e:
            st.error(f"Hệ thống đang tự khắc phục dữ liệu mã này. (Error: {e})")
