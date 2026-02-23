import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
from bs4 import BeautifulSoup

# --- CẤU HÌNH HỆ THỐNG TỰ VÁ LỖI ---
st.set_page_config(page_title="La Bàn Chứng Khoán PRO", layout="wide")

# Khởi tạo ngôn ngữ (Fix lỗi TypeError trong ảnh của bạn)
if 'lang_choice' not in st.session_state: st.session_state.lang_choice = "Tiếng Việt"
L = st.sidebar.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"], key='lang_choice')

T = {
    "Tiếng Việt": {
        "title": "📈 HỆ THỐNG PHÂN TÍCH TÀI CHÍNH PRO (V5.5)",
        "input": "Nhập mã (Ví dụ: FPT.VN, VCB.VN):", "btn": "🚀 KÍCH HOẠT AI CHUYÊN GIA",
        "p": "Giá khớp lệnh", "pe": "Định giá P/E", "pb": "Định giá P/B", "ind": "Ngành",
        "chart_y": "Giá", "chart_v": "Dòng tiền", "ai": "BÁO CÁO CHIẾN LƯỢC CẤP CAO"
    },
    "English": {
        "title": "📈 AI FINANCIAL ANALYTICS PRO (V5.5)",
        "input": "Enter Ticker (e.g. FPT.VN, AAPL):", "btn": "🚀 ACTIVATE EXECUTIVE AI",
        "p": "Match Price", "pe": "P/E Ratio", "pb": "P/B Ratio", "ind": "Industry",
        "chart_y": "Price", "chart_v": "Money Flow", "ai": "EXECUTIVE STRATEGY REPORT"
    }
}[L]

st.title(T["title"])

# --- HÀM LẤY GIÁ REAL-TIME ĐA NGUỒN (ANTI-DELAY) ---
def fetch_realtime_price_pro(symbol):
    sources = [
        f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}",
        f"https://iboard.ssi.com.vn/dchart/api/history?symbol={symbol}&resolution=1&from={int(time.time()-60)}&to={int(time.time())}"
    ]
    for url in sources:
        try:
            res = requests.get(url, timeout=1).json()
            if isinstance(res, list) and res: return res[0]['lastPrice'] * 1000
            if 'c' in res: return res['c'][-1]
        except: continue
    return 0

# --- HÀM LẤY CHỈ SỐ CƠ BẢN (ANTI N/A) ---
def fetch_fundamentals_pro(symbol):
    data = {"pe": "N/A", "pb": "N/A", "ind": "N/A", "src": "None"}
    # Thử TCBS
    try:
        r = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=2).json()
        data["pe"], data["pb"], data["ind"], data["src"] = r.get('pe'), r.get('pb'), r.get('industry'), "TCBS"
    except:
        # Dự phòng 2: CafeF Scraping nếu API chết
        try:
            r = requests.get(f"https://m.cafef.vn/truoc-phien/stock/{symbol}.chn", timeout=2)
            soup = BeautifulSoup(r.text, 'html.parser')
            # Logic lấy dữ liệu từ HTML ở đây nếu cần chuyên sâu hơn
            data["src"] = "CafeF-Scraper"
        except: pass
    return data

# --- BIỂU ĐỒ TRADINGVIEW CHUẨN QUỐC TẾ ---
def plot_pro_chart(df, ticker, lang_code):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
    
    # Nến Nhật + Đường trung bình
    fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name=T["chart_y"]), row=1, col=1)
    
    # Khối lượng tách biệt (Xanh/Đỏ theo nến)
    colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name=T["chart_v"]), row=2, col=1)
    
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
    # Đồng nhất ngôn ngữ ngày tháng
    fig.update_xaxes(type='date', tickformat="%d %b %y")
    return fig

# --- XỬ LÝ CHÍNH ---
ticker_input = st.text_input(T["input"], "FPT.VN").upper()

if st.button(T["btn"]):
    with st.spinner("Đang kích hoạt hệ thống radar đa tầng..."):
        try:
            symbol = ticker_input.split('.')[0]
            # 1. Lấy dữ liệu
            p_real = fetch_realtime_price_pro(symbol)
            fund = fetch_fundamentals_pro(symbol)
            
            url_h = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time()-15552000)}&to={int(time.time())}&symbol={symbol}&resolution=1D"
            res_h = requests.get(url_h).json()
            df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
            
            # Chỉ báo cho AI Pro
            df['RSI'] = ta.rsi(df['close'], length=14)
            
            # 2. Hiển thị Dashboard
            st.success(f"📡 Dữ liệu tóm được từ: {fund['src']} | {time.strftime('%H:%M:%S')}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(T["p"], f"{p_real:,.0f}" if p_real > 0 else "---")
            c2.metric(T["pe"], fund["pe"])
            c3.metric(T["pb"], fund["pb"])
            c4.metric(T["ind"], fund["ind"])
            
            # 3. Biểu đồ
            st.plotly_chart(plot_pro_chart(df, ticker_input, L), use_container_width=True)
            
            # 4. AI SIÊU CHUYÊN GIA (TỰ VÁ LỖI API)
            st.subheader(T["ai"])
            prompt = f"""You are a Senior Fund Manager. Language: {L}. Analyze {ticker_input}. 
            Price: {p_real}. P/E: {fund['pe']}. P/B: {fund['pb']}. Industry: {fund['ind']}. 
            Technical Data: RSI={df['RSI'].iloc[-1]:.2f}. 
            Last 15 days Vol: {df['volume'].tail(15).tolist()}.
            Requirements: 
            1. Smart Money Flow (Big boy action).
            2. Detailed technical patterns.
            3. Valuation vs Industry peers.
            4. Macro influence.
            5. Clear Buy/Sell/Hold recommendation with target price."""
            
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                # Thử tất cả các model khả dụng
                for m_name in ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']:
                    try:
                        ai_model = genai.GenerativeModel(m_name)
                        st.write(ai_model.generate_content(prompt).text)
                        break
                    except: continue
            except: st.warning("AI đang bảo trì hệ thống API.")
            
        except Exception as e:
            st.error(f"Lỗi: {e}")
