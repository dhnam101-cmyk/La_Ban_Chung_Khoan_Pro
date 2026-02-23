import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- SETUP HỆ THỐNG ---
st.set_page_config(page_title="Hệ Thống Phân Tích Pro V8.0", layout="wide")

if 'lang' not in st.session_state: st.session_state.lang = "Tiếng Việt"
L = st.sidebar.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"], key='lang')

T = {
    "Tiếng Việt": {
        "title": "📈 SIÊU HỆ THỐNG AI CHỨNG KHOÁN PRO V8.0",
        "input": "Nhập mã cổ phiếu (VD: FPT, VCB, HPG, AAPL):",
        "btn": "🚀 KÍCH HOẠT AI CHUYÊN GIA",
        "p": "Giá Khớp Lệnh", "pe": "Chỉ số P/E", "pb": "Chỉ số P/B", "ind": "Ngành",
        "chart_y": "Giá", "chart_v": "Dòng tiền", "ai": "BÁO CÁO CHIẾN LƯỢC TỔNG LỰC",
        "loading": "Đang quét tin tức vĩ mô và dữ liệu đa tầng..."
    },
    "English": {
        "title": "📈 AI STOCK EXPERT PRO V8.0",
        "input": "Enter Ticker (e.g. FPT, VCB, AAPL):",
        "btn": "🚀 ACTIVATE EXECUTIVE AI",
        "p": "Real-time Price", "pe": "P/E Ratio", "pb": "P/B Ratio", "ind": "Industry",
        "chart_y": "Price", "chart_v": "Money Flow", "ai": "EXECUTIVE STRATEGY REPORT",
        "loading": "Scanning macro news and multi-layer data..."
    }
}[L]

st.title(T["title"])

# --- HÀM TỰ VÁ LỖI AI (CHỐNG LỖI 404) ---
@st.cache_resource
def get_working_model():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']:
            if m in available: return genai.GenerativeModel(m)
        return genai.GenerativeModel(available[0])
    except: return None

# --- HÀM LẤY TIN TỨC REAL-TIME ---
def get_macro_news(symbol):
    try:
        url = f"https://finfo-api.vndirect.com.vn/v4/news?q=code:{symbol}"
        res = requests.get(url, timeout=3).json()
        return "\n".join([f"- {a['newsTitle']}" for a in res.get('data', [])[:5]])
    except: return "Thị trường ổn định, chưa có tin tức chấn động."

# --- HỆ THỐNG DỮ LIỆU ĐA NGUỒN TỰ NHẬN DIỆN MÃ ---
def fetch_all_data(ticker):
    # Tự động nhận diện mã VN hay Quốc tế
    is_vn = True
    test_res = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={ticker}", timeout=1).json()
    if not test_res: is_vn = False
    
    symbol = ticker.upper()
    p_real, pe, pb, ind, src = 0, "N/A", "N/A", "N/A", "Global"
    
    if is_vn:
        # 1. Giá Real-time khớp bảng điện
        try: p_real = test_res[0]['lastPrice'] * 1000
        except: pass
        
        # 2. Chỉ số cơ bản (TCBS/SSI)
        try:
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=3).json()
            pe, pb, ind, src = r_f.get('pe'), r_f.get('pb'), r_f.get('industry'), "Nội địa (VN)"
        except: pass
        
        # 3. Biểu đồ nến
        end = int(time.time())
        url_h = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={end-15552000}&to={end}&symbol={symbol}&resolution=1D"
        res_h = requests.get(url_h).json()
        df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
    else:
        # Cổ phiếu quốc tế (Yahoo)
        import yfinance as yf
        s = yf.Ticker(symbol)
        df = s.history(period="6mo").reset_index()
        df.columns = [c.lower() for c in df.columns]
        p_real = df['close'].iloc[-1]
        pe, pb, ind, src = s.info.get('trailingPE'), s.info.get('priceToBook'), s.info.get('industry'), "Quốc tế (US)"
        
    return df, p_real, pe, pb, ind, src

# --- GIAO DIỆN XỬ LÝ ---
ticker_in = st.text_input(T["input"], "FPT").upper()

if st.button(T["btn"]):
    with st.spinner(T["loading"]):
        try:
            df, p_real, pe, pb, ind, src = fetch_all_data(ticker_in)
            news = get_macro_news(ticker_in.split('.')[0])
            
            # Chỉ báo kỹ thuật
            df['RSI'] = ta.rsi(df['close'], length=14)
            df['EMA20'] = ta.ema(df['close'], length=20)
            
            st.success(f"📡 Dữ liệu: {src} | ⏱ {time.strftime('%H:%M:%S')}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(T["p"], f"{p_real:,.0f}" if p_real > 1000 else f"{p_real:,.2f}")
            c2.metric(T["pe"], pe if pe else "N/A")
            c3.metric(T["pb"], pb if pb else "N/A")
            c4.metric(T["ind"], ind if ind else "N/A")

            # BIỂU ĐỒ TRADINGVIEW 2 TẦNG ĐỒNG NHẤT
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name=T["chart_y"]), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['EMA20'], line=dict(color='yellow', width=1), name="EMA20"), row=1, col=1)
            
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name=T["chart_v"]), row=2, col=1)
            
            fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            fig.update_xaxes(type='date', tickformat="%d %b %y")
            st.plotly_chart(fig, use_container_width=True)

            # AI SIÊU CHUYÊN GIA (PRO PROMPT)
            st.subheader(f"🤖 {T['ai']} ({L})")
            prompt = f"""Role: Senior Fund Manager. Language: {L}. Analyze {ticker_in}.
            Current Price: {p_real}. P/E: {pe}. P/B: {pb}. Industry: {ind}.
            Technical: RSI={df['RSI'].iloc[-1]:.2f}, EMA20={df['EMA20'].iloc[-1]:.2f}.
            Last 10d Volume: {df['volume'].tail(10).tolist()}.
            News context: {news}
            Requirement: 1. SMART MONEY (Big boys). 2. Technical pattern. 3. Relative valuation vs industry. 4. Macro & News impact. 5. Verdict Buy/Sell/Hold with Target."""
            
            ai_model = get_working_model()
            if ai_model: st.write(ai_model.generate_content(prompt).text)
            else: st.error("AI Error: Please check Gemini API Key in Secrets.")

        except Exception as e:
            st.error(f"Hệ thống đang bảo trì nguồn dữ liệu cho mã này. Lỗi: {e}")
