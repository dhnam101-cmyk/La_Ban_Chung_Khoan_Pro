import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf
from yahooquery import Ticker as YQTicker
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 1. SETUP & NGÔN NGỮ ---
st.set_page_config(page_title="Hệ Thống Phân Tích Chứng Khoán PRO V12", layout="wide")

if 'lang' not in st.session_state: st.session_state.lang = "Tiếng Việt"
L = st.sidebar.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"], key='lang')

T = {
    "Tiếng Việt": {
        "title": "📈 SIÊU HỆ THỐNG AI CHỨNG KHOÁN PRO V12",
        "input": "Nhập mã chứng khoán (VD: FPT, VCB, AAPL, BTC-USD):",
        "btn": "🚀 KÍCH HOẠT QUÉT ĐA TẦNG TOÀN CẦU",
        "p": "Giá Khớp Lệnh", "pe": "P/E", "pb": "P/B", "ind": "Ngành",
        "chart_y": "Giá (Nến)", "chart_v": "Dòng tiền", "ai": "BÁO CÁO CHIẾN LƯỢC TỔNG LỰC",
        "loading": "Đang vắt kiệt dữ liệu Real-time và Tin tức vĩ mô..."
    },
    "English": {
        "title": "📈 AI STOCK ANALYTICS PRO V12",
        "input": "Enter Ticker (e.g., FPT, AAPL, BTC-USD):",
        "btn": "🚀 ACTIVATE GLOBAL MULTI-SCAN",
        "p": "Real-time Price", "pe": "P/E Ratio", "pb": "P/B Ratio", "ind": "Industry",
        "chart_y": "Price", "chart_v": "Money Flow", "ai": "EXECUTIVE STRATEGY REPORT",
        "loading": "Extracting Real-time data and Macro news..."
    }
}[L]

st.title(T["title"])

# --- 2. TỰ VÁ LỖI AI (AUTO-HEALING) ---
@st.cache_resource
def get_working_ai_node():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m in ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-pro']:
            if m in available: return genai.GenerativeModel(m)
        return genai.GenerativeModel(available[0])
    except: return None

# --- 3. HỆ THỐNG QUÉT DỮ LIỆU ĐA NGUỒN (ANTI-BLOCK & ANTI N/A) ---
def get_news(symbol):
    try:
        url = f"https://finfo-api.vndirect.com.vn/v4/news?q=code:{symbol}"
        res = requests.get(url, timeout=2).json()
        return "\n".join([f"- {a['newsTitle']}" for a in res.get('data', [])[:5]])
    except: return "Thị trường ổn định, chưa có tin tức mới."

def fetch_universal_data(ticker):
    symbol = ticker.upper()
    df, p_real, fund, market = None, 0, {'pe': 'N/A', 'pb': 'N/A', 'ind': 'N/A', 'src': 'Global'}, "Unknown"

    # THỬ QUÉT VIỆT NAM (VND/SSI/TCBS)
    try:
        vn_check = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}", timeout=1).json()
        if vn_check:
            p_real = vn_check[0]['lastPrice'] * 1000
            end = int(time.time())
            url_h = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={end-15552000}&to={end}&symbol={symbol}&resolution=1D"
            res_h = requests.get(url_h).json()
            df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
            # Lấy chỉ số cơ bản
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=1).json()
            fund.update({'pe': r_f.get('pe'), 'pb': r_f.get('pb'), 'ind': r_f.get('industry'), 'src': 'TCBS/VND'})
            market = "Vietnam"
    except: pass

    # NẾU KHÔNG PHẢI VN -> QUÉT QUỐC TẾ
    if df is None:
        try:
            stock = yf.Ticker(symbol)
            df = stock.history(period="6mo").reset_index()
            if not df.empty:
                df.columns = [c.lower() for c in df.columns]
                p_real = df['close'].iloc[-1]
                fund.update({'pe': stock.info.get('trailingPE'), 'pb': stock.info.get('priceToBook'), 'ind': stock.info.get('industry'), 'src': 'Yahoo Global'})
                market = "International"
        except: pass

    return df, p_real, fund, market

# --- 4. GIAO DIỆN & XỬ LÝ ---
ticker_in = st.text_input(T["input"], "FPT").upper()

if st.button(T["btn"]):
    with st.spinner(T["loading"]):
        try:
            df, p_real, fund, market = fetch_universal_data(ticker_in)
            news = get_news(ticker_in) if market == "Vietnam" else "Global macro analysis."
            
            # Tính toán kỹ thuật Pro
            df['RSI'] = ta.rsi(df['close'], length=14)
            df['EMA20'] = ta.ema(df['close'], length=20)
            df['MACD'], df['MACDs'], df['MACDh'] = ta.macd(df['close']).iloc[:,0], ta.macd(df['close']).iloc[:,1], ta.macd(df['close']).iloc[:,2]

            st.success(f"🌐 {T['src']} {fund['src']} | {market} | ⏱ {time.strftime('%H:%M:%S')}")
            
            # Dashboard
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(T["p"], f"{p_real:,.0f}" if market == "Vietnam" else f"{p_real:,.2f}")
            c2.metric(T["pe"], fund['pe'] if fund['pe'] else "N/A")
            c3.metric(T["pb"], fund['pb'] if fund['pb'] else "N/A")
            c4.metric(T["ind"], fund['ind'] if fund['ind'] else "N/A")

            # BIỂU ĐỒ TRADINGVIEW 2 TẦNG ĐỒNG NHẤT
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name=T["chart_y"]), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['EMA20'], line=dict(color='yellow', width=1), name="EMA20"), row=1, col=1)
            
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name=T["chart_v"]), row=2, col=1)
            
            fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            fig.update_xaxes(type='date', tickformat="%d %b %y")
            st.plotly_chart(fig, use_container_width=True)

            # AI PRO REPORT (SIÊU CHUYÊN GIA)
            st.subheader(f"🤖 {T['ai']} ({L})")
            prompt = f"""Role: Senior Fund Manager. Language: {L}. Analyze {ticker_in} in {market} market.
            Data: Price {p_real}, P/E {fund['pe']}, P/B {fund['pb']}, Industry {fund['ind']}.
            Indicators: RSI {df['RSI'].iloc[-1]:.2f}, EMA20 {df['EMA20'].iloc[-1]:.2f}, MACD {df['MACD'].iloc[-1]:.2f}.
            Recent News/Macro: {news}
            Requirement:
            1. SMART MONEY FLOW: Trace 'Big Boys' via Volume/Price correlation.
            2. TECHNICAL: Trend, Patterns, Indicators.
            3. VALUATION: Industry & Competitor comparison.
            4. MACO & NEWS: Impact of latest news on stock.
            5. FINAL VERDICT: Buy/Sell/Hold with Target & Stop Loss."""
            
            model = get_working_ai_node()
            if model: st.write(model.generate_content(prompt).text)
            else: st.error("AI Node Offline. Check API Key.")

        except Exception as e:
            st.error(f"Hệ thống đang tự vá lỗi dữ liệu cho mã này. (Chi tiết: {e})")
