import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP HỆ THỐNG & NGÔN NGỮ ĐỒNG NHẤT ---
st.set_page_config(page_title="AI Terminal V29: Ultimate", layout="wide")
if 'lang' not in st.session_state: st.session_state.lang = "Tiếng Việt"
L = st.session_state.lang

T = {
    "Tiếng Việt": {
        "title": "📈 AI FINANCIAL TERMINAL V29: ULTIMATE",
        "input": "Nhập mã (GEX, AAPL, 7203.T) hoặc câu hỏi chiến lược:",
        "btn": "🚀 KÍCH HOẠT HỆ THỐNG", "p": "Giá Khớp Lệnh",
        "ai_report": "BÁO CÁO CHIẾN LƯỢC CHUYÊN GIA (13 YÊU CẦU)"
    },
    "English": {
        "title": "📈 AI FINANCIAL TERMINAL V29: ULTIMATE",
        "input": "Enter ticker or strategic question:",
        "btn": "🚀 ACTIVATE SYSTEM", "p": "Real-time Price",
        "ai_report": "13-POINT EXECUTIVE STRATEGY REPORT"
    }
}[L]

st.title(T["title"])

# --- 2. TỰ VÁ LỖI AI (SELF-HEALING) ---
@st.cache_resource
def get_ai_expert():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-pro']
        for m in priority:
            if m in available: return genai.GenerativeModel(m)
        return genai.GenerativeModel(available[0])
    except: return None

# --- 3. DỮ LIỆU VĨ MÔ & HÀNG HÓA THẾ GIỚI (COMMODITY RADAR) ---
def fetch_global_intel(industry):
    intel = {"macro": {}, "commodity": {}}
    # Vĩ mô liên thị trường
    for k, s in {"S&P 500": "^GSPC", "DXY": "DX-Y.NYB", "Fed 10Y": "^TNX"}.items():
        try: intel["macro"][k] = round(yf.download(s, period="2d", progress=False)['Close'].iloc[-1], 2)
        except: intel["macro"][k] = "N/A"
    # Hàng hóa theo ngành (Ví dụ HPG)
    if any(x in str(industry) for x in ["Thép", "Steel", "Khai khoáng"]):
        for k, s in {"Thép HRC": "HRC=F", "Quặng Sắt": "TIO=F"}.items():
            try: intel["commodity"][k] = round(yf.download(s, period="2d", progress=False)['Close'].iloc[-1], 2)
            except: pass
    return intel

# --- 4. RADAR QUÉT DỮ LIỆU (VIETNAM & US PRIORITY) ---
def fetch_sovereign_v29(ticker_raw):
    symbol = ticker_raw.upper()
    df, p_real, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    # ƯU TIÊN 1: KIỂM TRA VIỆT NAM (DÙ TRÙNG MÃ MỸ CŨNG LẤY VN)
    try:
        snap = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}", timeout=2).json()
        if snap and snap[0]['lastPrice'] != 0:
            is_vn = True
            p_real = snap[0]['lastPrice'] * 1000
            res_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={symbol}&resolution=1D").json()
            df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=2).json()
            pe, pb, ind = r_f.get('pe', 'N/A'), r_f.get('pb', 'N/A'), r_f.get('industry', 'N/A')
    except: pass

    # ƯU TIÊN 2: MỸ & QUỐC TẾ (NẾU VN KHÔNG CÓ)
    if df is None:
        try:
            s = yf.Ticker(symbol); h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]
                p_real = df['close'].iloc[-1]; pe = s.info.get('trailingPE', 'N/A'); pb = s.info.get('priceToBook', 'N/A'); ind = s.info.get('industry', 'N/A')
        except: pass
    return df, p_real, pe, pb, ind, is_vn

# --- 5. GIAO DIỆN XỬ LÝ ---
query = st.text_input(T["input"], "GEX").upper()

if st.button(T["btn"]):
    with st.spinner("🚀 Radar đang quét dữ liệu đa quốc gia..."):
        is_q = len(query.split()) > 1
        if not is_q:
            df, p_now, pe, pb, ind, is_vn = fetch_sovereign_v29(query)
            if df is not None:
                # Tính toán Kỹ thuật (Full MA10-MA200, RSI, MACD)
                df['MA10']=ta.sma(df['close'],10); df['MA20']=ta.sma(df['close'],20); df['MA50']=ta.sma(df['close'],50); df['MA200']=ta.sma(df['close'],200)
                df['RSI']=ta.rsi(df['close'],14); m=ta.macd(df['close']); df['MACD']=m.iloc[:,0]
                intel = fetch_global_intel(ind)
                
                # Dashboard
                st.info(f"🌐 Thị trường: {('Việt Nam' if is_vn else 'Quốc tế')} | 🌍 Vĩ mô: {intel['macro']}")
                c1,c2,c3,c4 = st.columns(4); c1.metric(T["p"], f"{p_now:,.0f}" if is_vn else f"{p_now:,.2f}")
                c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Ngành", ind)
                
                # BIỂU ĐỒ 2 TẦNG CHUẨN QUỐC TẾ
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                # AI BÁO CÁO 13 YÊU CẦU
                model = get_ai_expert()
                if model:
                    st.subheader(f"🤖 {T['ai_report']}")
                    prompt = f"Phân tích chuyên sâu {query}, giá {p_now}. Chỉ rõ Dòng tiền cá mập, Kỹ thuật (MA10-200, RSI, MACD), Vĩ mô: {intel['macro']}, Hàng hóa: {intel['commodity']}. Khuyến nghị Mua/Bán rõ ràng."
                    st.write(model.generate_content(prompt).text)
            else: st.error("Mã không hợp lệ.")
        else:
            # CHATBOT CHIẾN LƯỢC
            model = get_ai_expert()
            if model: st.write(model.generate_content(f"Đóng vai chuyên gia chứng khoán, trả lời bằng {L}: {query}").text)
