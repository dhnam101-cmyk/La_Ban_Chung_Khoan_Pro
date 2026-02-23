import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- THIẾT LẬP HỆ THỐNG ---
st.set_page_config(page_title="AI Chuyên Gia Chứng Khoán PRO", layout="wide")

if 'lang' not in st.session_state: st.session_state.lang = "Tiếng Việt"
L = st.sidebar.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"], key='lang')

T = {
    "Tiếng Việt": {
        "title": "📈 AI CHUYÊN GIA CHỨNG KHOÁN PRO V7.0",
        "input": "Nhập mã (VD: FPT, VCB):", "btn": "🚀 PHÂN TÍCH CHUYÊN SÂU",
        "p": "Giá Khớp Lệnh", "pe": "P/E", "pb": "P/B", "ind": "Ngành",
        "chart_y": "Giá", "chart_v": "Dòng tiền", "ai": "BÁO CÁO CHIẾN LƯỢC TỔNG LỰC",
        "loading": "Đang quét dữ liệu đa tầng và tin tức vĩ mô..."
    },
    "English": {
        "title": "📈 AI STOCK EXPERT PRO V7.0",
        "input": "Enter Ticker (e.g. FPT, VCB):", "btn": "🚀 DEEP ANALYSIS",
        "p": "Price", "pe": "P/E", "pb": "P/B", "ind": "Industry",
        "chart_y": "Price", "chart_v": "Money Flow", "ai": "EXECUTIVE STRATEGY REPORT",
        "loading": "Scanning multi-layer data and macro news..."
    }
}[L]

st.title(T["title"])

# --- 1. LẤY TIN TỨC THỜI GIAN THỰC (FOR MACRO ANALYSIS) ---
def get_latest_news(symbol):
    news_text = ""
    try:
        # Lấy tin tức từ Vietstock/CafeF qua tìm kiếm nhanh
        url = f"https://finfo-api.vndirect.com.vn/v4/news?q=code:{symbol}"
        res = requests.get(url, timeout=3).json()
        articles = res.get('data', [])[:5]
        for art in articles:
            news_text += f"- {art['newsTitle']} ({art['newsDate']})\n"
    except:
        news_text = "Không tìm thấy tin tức mới nhất, AI sẽ dựa trên biến động thị trường chung."
    return news_text

# --- 2. HỆ THỐNG DỮ LIỆU BẤT TỬ (ANTI N/A) ---
def fetch_pro_data(ticker):
    symbol = ticker.split('.')[0].upper()
    
    # Giá Real-time từ VNDirect
    p_real = 0
    try:
        r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}", timeout=2).json()
        p_real = r_p[0]['lastPrice'] * 1000
    except: pass

    # Biểu đồ & Nguồn dự phòng
    end = int(time.time())
    start = end - 15552000
    url_h = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={start}&to={end}&symbol={symbol}&resolution=1D"
    res_h = requests.get(url_h).json()
    df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
    
    # Chỉ số cơ bản (Đa nguồn)
    fund = {'pe': 'N/A', 'pb': 'N/A', 'ind': 'N/A', 'src': 'Global'}
    try:
        r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=2).json()
        fund.update({'pe': r_f.get('pe'), 'pb': r_f.get('pb'), 'ind': r_f.get('industry'), 'src': 'TCBS'})
    except: pass
    
    return df, p_real, fund

# --- 3. GIAO DIỆN & XỬ LÝ ---
ticker_input = st.text_input(T["input"], "FPT").upper()

if st.button(T["btn"]):
    with st.spinner(T["loading"]):
        try:
            symbol = ticker_input.split('.')[0]
            df, p_real, fund = fetch_pro_data(symbol)
            latest_news = get_latest_news(symbol)
            
            # Kỹ thuật chuyên sâu
            df['RSI'] = ta.rsi(df['close'], length=14)
            df['EMA20'] = ta.ema(df['close'], length=20)
            df['MACD'], df['MACDs'], df['MACDh'] = ta.macd(df['close']).iloc[:,0], ta.macd(df['close']).iloc[:,1], ta.macd(df['close']).iloc[:,2]

            # Dashboard chỉ số
            st.success(f"📡 Dữ liệu: {fund['src']} | Tin tức: Đã cập nhật | {time.strftime('%H:%M:%S')}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(T["p"], f"{p_real:,.0f}")
            c2.metric(T["pe"], fund["pe"])
            c3.metric(T["pb"], fund["pb"])
            c4.metric(T["ind"], fund["ind"])

            # BIỂU ĐỒ 2 TẦNG CHUYÊN NGHIỆP
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name=T["chart_y"]), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['EMA20'], line=dict(color='yellow', width=1), name="EMA20"), row=1, col=1)
            
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name=T["chart_v"]), row=2, col=1)
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # AI PRO REPORT (VĂN PHONG CHUYÊN GIA)
            st.markdown(f"### 🤖 {T['ai']} ({L})")
            prompt = f"""
            System: You are a Top-tier Quantitative & Fundamental Analyst. 
            Language: {L}.
            Data for {symbol}: Price {p_real}, P/E {fund['pe']}, P/B {fund['pb']}, Industry: {fund['ind']}.
            Technical: RSI={df['RSI'].iloc[-1]:.2f}, EMA20={df['EMA20'].iloc[-1]:.2f}, MACD={df['MACD'].iloc[-1]:.2f}.
            Latest Real-time News: {latest_news}
            
            REQUIREMENTS FOR REPORT:
            1. SMART MONEY FLOW: Identify if Big Boys are accumulating or distributing based on Volume & Price Correlation.
            2. TECHNICAL PATTERNS: Analyze trend, Support/Resistance levels, and indicator signals (RSI/MACD).
            3. RELATIVE VALUATION: Compare P/E, P/B with industry average. Is it cheap or expensive?
            4. MACD & MARKET IMPACT (REAL-TIME): Use the provided 'Latest News' and current market sentiment to evaluate risks/opportunities.
            5. FINAL VERDICT: Provide Buy/Sell/Hold with target price and stop-loss.
            """
            
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-1.5-flash')
            st.write(model.generate_content(prompt).text)

        except Exception as e:
            st.error(f"Lỗi hệ thống: {e}")
