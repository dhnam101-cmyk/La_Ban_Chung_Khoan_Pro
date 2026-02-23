import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="La Bàn Chứng Khoán PRO", layout="wide")

# --- HỆ THỐNG NGÔN NGỮ ---
lang = st.sidebar.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"])
T = {
    "Tiếng Việt": {
        "title": "📈 LA BÀN CHỨNG KHOÁN PRO",
        "desc": "Hệ thống AI Phân tích Chuyên gia: Dòng tiền - Kỹ thuật - Định giá",
        "input": "Nhập mã cổ phiếu (VD: FPT.VN, VCB.VN, AAPL):",
        "btn": "🚀 PHÂN TÍCH CHUYÊN SÂU",
        "price": "Giá", "pb": "Chỉ số P/B", "pe": "Chỉ số P/E", "ind": "Ngành",
        "chart_price": "Giá (Nến Nhật)", "chart_vol": "Dòng tiền (Khối lượng)",
        "ai_loading": "Chuyên gia AI đang đọc dữ liệu...",
        "error": "🔴 Lỗi hệ thống: Không thể kết nối dữ liệu mã này."
    },
    "English": {
        "title": "📈 STOCK COMPASS PRO",
        "desc": "Expert AI Analysis: Cash Flow - Technical - Valuation",
        "input": "Enter Ticker (e.g., AAPL, FPT.VN):",
        "btn": "🚀 DEEP ANALYSIS",
        "price": "Price", "pb": "P/B Ratio", "pe": "P/E Ratio", "ind": "Industry",
        "chart_price": "Price (Candlestick)", "chart_vol": "Money Flow (Volume)",
        "ai_loading": "AI Expert is reading data...",
        "error": "🔴 System Error: Data not found for this ticker."
    }
}[lang]

st.title(T["title"])
st.markdown(f"*{T['desc']}*")

# --- KẾT NỐI AI ---
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- HÀM LẤY DỮ LIỆU ĐA NGUỒN ---
def get_pro_data(ticker):
    symbol = ticker.split('.')[0].upper()
    # Nguồn 1: DNSE (Biểu đồ)
    end = int(time.time())
    start = end - 15552000 # 6 tháng
    url_h = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={start}&to={end}&symbol={symbol}&resolution=1D"
    res_h = requests.get(url_h).json()
    df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
    
    # Nguồn 2: TCBS (Cơ bản)
    pe, pb, ind = "N/A", "N/A", "N/A"
    try:
        url_f = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview"
        res_f = requests.get(url_f, timeout=5).json()
        pe = res_f.get('pe', 'N/A')
        pb = res_f.get('pb', 'N/A')
        ind = res_f.get('industry', 'N/A')
    except: pass
    
    return df, pe, pb, ind

# --- GIAO DIỆN ---
ticker_input = st.text_input(T["input"], "FPT.VN").upper()

if st.button(T["btn"]):
    with st.spinner(T["ai_loading"]):
        try:
            df, pe, pb, ind = get_pro_data(ticker_input)
            p_now = df['close'].iloc[-1] * (1000 if df['close'].iloc[-1] < 1000 else 1)
            
            # 1. Dashboard chỉ số
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(T["price"], f"{p_now:,.0f}")
            c2.metric(T["pb"], pb)
            c3.metric(T["pe"], pe)
            c4.metric(T["ind"], ind)

            # 2. BIỂU ĐỒ CHUYÊN NGHIỆP (TÁCH LỚP)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=(T["chart_price"], T["chart_vol"]), row_heights=[0.7, 0.3])
            
            # Nến Nhật + Đường MA
            df['MA20'] = df['close'].rolling(20).mean()
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
            
            # Khối lượng
            colors = ['red' if row['open'] > row['close'] else 'green' for i, row in df.iterrows()]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
            
            fig.update_layout(height=700, template="plotly_dark", showlegend=False, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 3. AI PHÂN TÍCH CHUYÊN GIA (PRO PROMPT)
            prompt = f"""
            System: You are a Tier-1 Hedge Fund Analyst. Language: {lang}.
            Ticker: {ticker_input}. Industry: {ind}. 
            Price: {p_now}. P/E: {pe}. P/B: {pb}.
            Latest 15 days data (OHLCV): {df.tail(15).to_string()}
            
            Task: Provide a Professional Report including:
            1. Smart Money Flow: Identify if 'Big Boys' are accumulating or distributing based on Volume spikes.
            2. Detailed Technical: Trend, Support/Resistance, and RSI/MA signals.
            3. Deep Valuation: Compare this P/E and P/B with industry peers. Is it undervalued or a value trap?
            4. Market Factors: How current market trends affect this specific stock.
            5. Expert Recommendation: Buy/Sell/Hold with target price.
            """
            response = model.generate_content(prompt)
            st.markdown("---")
            st.markdown(f"### 🤖 AI EXPERT ANALYSIS ({lang})")
            st.write(response.text)
            
        except Exception as e:
            st.error(f"{T['error']} Details: {e}")
