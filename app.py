import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="La Bàn Chứng Khoán PRO", layout="wide")

# --- HỆ THỐNG NGÔN NGỮ ĐỒNG NHẤT ---
if 'lang' not in st.sidebar: st.sidebar.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"], key='lang')
L = st.session_state.lang
T = {
    "Tiếng Việt": {
        "title": "📈 SIÊU HỆ THỐNG AI CHỨNG KHOÁN PRO", "input": "Nhập mã (FPT.VN, VCB.VN, AAPL):",
        "btn": "🚀 KÍCH HOẠT QUÉT ĐA TẦNG", "p": "Giá Khớp Lệnh", "ai": "BÁO CÁO CHIẾN LƯỢC CẤP CAO",
        "src": "Nguồn dữ liệu tóm được:", "loading": "Đang vắt kiệt dữ liệu từ 4 nguồn nội địa..."
    },
    "English": {
        "title": "📈 AI STOCK ANALYTICS PRO", "input": "Enter Ticker:",
        "btn": "🚀 ACTIVATE MULTI-LAYER SCAN", "p": "Match Price", "ai": "EXECUTIVE AI STRATEGY REPORT",
        "src": "Data captured from:", "loading": "Extracting data from 4 domestic sources..."
    }
}[L]

st.title(T["title"])

# --- CƠ CHẾ TỰ VÁ LỖI AI (AUTO-HEALING) ---
def get_pro_ai_response(prompt):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Tự động nhảy model nếu lỗi 404
        for m_name in ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']:
            try:
                model = genai.GenerativeModel(m_name)
                return model.generate_content(prompt).text
            except: continue
        return "System Busy. Please try again."
    except: return "Check API Key in Secrets."

# --- HỆ THỐNG QUÉT ĐA NGUỒN (ANTI N/A) ---
def fetch_realtime_price(symbol):
    urls = [
        f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}",
        f"https://iboard.ssi.com.vn/dchart/api/history?symbol={symbol}&resolution=1&from={int(time.time()-60)}&to={int(time.time())}"
    ]
    for url in urls:
        try:
            res = requests.get(url, timeout=1).json()
            if isinstance(res, list): return res[0]['lastPrice'] * 1000
            if 'c' in res: return res['c'][-1]
        except: continue
    return 0

def fetch_fundamentals(symbol):
    # Quét song song TCBS và Vietstock để lấy P/E, P/B
    def get_tcbs(s):
        r = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{s}/overview", timeout=2).json()
        return {'pe': r.get('pe'), 'pb': r.get('pb'), 'ind': r.get('industry'), 'src': 'TCBS'}
    
    def get_d_entry(s):
        # Nguồn dự phòng 2
        r = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={s}&resolution=1D", timeout=2).json()
        return {'pe': 'N/A', 'pb': 'N/A', 'ind': 'VN-Stock', 'src': 'DNSE'}

    final = {'pe': 'N/A', 'pb': 'N/A', 'ind': 'N/A', 'src': 'None'}
    with ThreadPoolExecutor(max_workers=2) as exe:
        futures = [exe.submit(get_tcbs, symbol), exe.submit(get_d_entry, symbol)]
        for f in as_completed(futures):
            try:
                res = f.result()
                if res['pe'] and final['pe'] == 'N/A': final['pe'] = res['pe']; final['src'] = res['src']
                if res['pb'] and final['pb'] == 'N/A': final['pb'] = res['pb']
                if res['ind'] and final['ind'] == 'N/A': final['ind'] = res['ind']
            except: continue
    return final

# --- LẤY BIỂU ĐỒ NẾN ---
def get_chart_data(symbol):
    end = int(time.time())
    start = end - 15552000
    url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={start}&to={end}&symbol={symbol}&resolution=1D"
    res = requests.get(url).json()
    return pd.DataFrame({'date': pd.to_datetime(res['t'], unit='s'), 'open': res['o'], 'high': res['h'], 'low': res['l'], 'close': res['c'], 'volume': res['v']})

# --- GIAO DIỆN & XỬ LÝ ---
ticker = st.text_input(T["input"], "FPT.VN").upper()
if st.button(T["btn"]):
    with st.spinner(T["loading"]):
        symbol = ticker.split('.')[0]
        df = get_chart_data(symbol)
        p_now = fetch_realtime_price(symbol)
        fund = fetch_fundamentals(symbol)
        
        # Chỉ báo kỹ thuật cho AI
        df['RSI'] = ta.rsi(df['close'], length=14)
        df['EMA20'] = ta.ema(df['close'], length=20)
        
        st.success(f"{T['src']} {fund['src']} | ⏱ {time.strftime('%H:%M:%S')}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(T["p"], f"{p_now:,.0f}")
        c2.metric("P/E", fund['pe'])
        c3.metric("P/B", fund['pb'])
        c4.metric(T.get('ind', 'Ngành'), fund['ind'])

        # BIỂU ĐỒ 2 TẦNG CHUYÊN NGHIỆP
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Nến"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['date'], y=df['EMA20'], line=dict(color='yellow', width=1), name="EMA20"), row=1, col=1)
        
        colors = ['red' if df['open'].iloc[i] > df['close'].iloc[i] else 'green' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
        
        fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
        fig.update_xaxes(type='date', tickformat="%d %b %y")
        st.plotly_chart(fig, use_container_width=True)

        # AI SIÊU CHUYÊN GIA (PRO PROMPT)
        st.subheader(T["ai"])
        prompt = f"""
        Language: {L}. Acting as a Senior Fund Manager. 
        Analyze {ticker} (Industry: {fund['ind']}). 
        Real-time Price: {p_now}. P/E: {fund['pe']}. P/B: {fund['pb']}.
        RSI: {df['RSI'].iloc[-1]:.2f}. EMA20: {df['EMA20'].iloc[-1]:.2f}.
        Recent 15-day Vol: {df['volume'].tail(15).tolist()}.
        
        Requirement:
        1. SMART MONEY: Deep dive into Volume price action to find Big Boy footprints.
        2. TECHNICAL: Trend analysis using RSI and EMA.
        3. VALUATION: Compare P/E, P/B with industry.
        4. MACD & MARKET INFLUENCE: How current macro affects this stock.
        5. EXECUTIVE SUMMARY: Clear Buy/Sell/Hold with target price.
        """
        st.write(get_pro_ai_response(prompt))
