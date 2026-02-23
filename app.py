import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP & TRANSLATION ENGINE (Yêu cầu 12, 17) ---
st.set_page_config(page_title="AI Terminal V64: Sovereign Final", layout="wide")

T = {
    "Tiếng Việt": {"p": "Giá", "pe": "P/E", "pb": "P/B", "pei": "P/E Ngành", "pbi": "P/B Ngành", "ind": "Ngành", "msg": "Nhập mã/câu hỏi lọc mã và nhấn ENTER:"},
    "English": {"p": "Price", "pe": "P/E", "pb": "P/B", "pei": "Ind. P/E", "pbi": "Ind. P/B", "ind": "Industry", "msg": "Enter symbol/screening query and press ENTER:"},
    "日本語": {"p": "価格", "pe": "収益率", "pb": "純資産倍率", "pei": "業界収益率", "pbi": "業界純資産倍率", "ind": "業界", "msg": "シンボルを入力してENTERを押してください:"}
}

with st.sidebar:
    st.header("⚙️ Configuration")
    lang = st.selectbox("🌐 Ngôn ngữ / Language", list(T.keys()))
    m_config = {
        "Việt Nam": {"suffix": ".VN", "is_intl": False},
        "Mỹ (USA)": {"suffix": "", "is_intl": True}
    }
    m_target = st.selectbox("🌍 Thị trường / Market", list(m_config.keys()))

# --- 2. KHÁNG SẬP AI (Sửa lỗi ResourceExhausted tại image_b891d6) ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Ép sử dụng gemini-1.5-flash: Nhanh hơn, ổn định hơn và ít tốn tài nguyên hơn Pro
        return genai.GenerativeModel('models/gemini-1.5-flash')
    except: return None

# --- 3. DATA MATRIX (Xóa sổ N/A cho Ngành - Yêu cầu 15) ---
def fetch_omnipotent_data(ticker, market):
    sym = ticker.upper().strip()
    cfg = m_config[market]
    df, p, pe, pb, pei, pbi, ind, is_vn = None, 0, "N/A", "N/A", "N/A", "N/A", "N/A", not cfg["is_intl"]

    if is_vn:
        try:
            # Snapshot VNDirect
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", timeout=5).json()
            if r_p: p = r_p[0]['lastPrice'] * 1000
            
            # Fundamental TCBS (Lấy P/E, P/B Ngành - Sửa image_b891a0)
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", timeout=5).json()
            pe, pb, ind = r_f.get('pe', "N/A"), r_f.get('pb', "N/A"), r_f.get('industry', "N/A")
            # CƯƠNG HÓA CHỈ SỐ NGÀNH (Sử dụng industryPe/industryPb từ TCBS)
            pei = r_f.get('industryPe') or "N/A"
            pbi = r_f.get('industryPb') or "N/A"
            
            # Entrade Chart
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", timeout=5).json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
        except: pass

    # QUỐC TẾ HOẶC FALLBACK DỮ LIỆU TRỐNG
    if df is None or pe == "N/A":
        try:
            s = yf.Ticker(sym + cfg["suffix"]); info = s.info
            if df is None:
                h = s.history(period="6mo").reset_index()
                if not h.empty: df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
            pe = pe if pe != "N/A" else info.get('trailingPE', "N/A")
            pb = pb if pb != "N/A" else info.get('priceToBook', "N/A")
            ind = ind if ind != "N/A" else info.get('industry', "N/A")
        except: pass
            
    return df, p, pe, pb, pei, pbi, ind, is_vn

# --- 4. GIAO DIỆN PHÍM ENTER (Yêu cầu 16) ---
query = st.text_input(f"🔍 {T[lang]['msg']}:", "GEX").upper()

if query:
    # CHẾ ĐỘ CHATBOT LỌC MÃ THỰC TẾ (Yêu cầu 13)
    if len(query.split()) > 2:
        model = get_ai_brain()
        if model:
            with st.spinner("AI Sovereign is scanning real-time market data..."):
                try:
                    # Ép AI liệt kê mã cụ thể, không lý thuyết (image_acbc18)
                    instr = f"Act as a tycoon. For the {m_target} market, provide a SPECIFIC LIST OF 10 TICKERS for: {query}. INCLUDE REAL SYMBOLS AND PRICES. NO THEORY. Reply in {lang}."
                    st.write(model.generate_content(instr).text)
                except Exception as e: st.error(f"AI Quota Reached: {e}")
    else: # CHẾ ĐỘ PHÂN TÍCH MÃ CHI TIẾT
        with st.spinner(f"Loading {query} data..."):
            df, p_now, pe, pb, pei, pbi, ind, is_vn = fetch_omnipotent_data(query, m_target)
            if df is not None and not df.empty:
                df['MA20'] = ta.sma(df['close'], 20); df['MA200'] = ta.sma(df['close'], 200)
                df['RSI'] = ta.rsi(df['close'], 14)
                
                st.success(f"📌 {query} | {m_target}")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric(T[lang]['p'], f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
                c2.metric(T[lang]['pe'], f"{pe:.2f}" if isinstance(pe, (float, int)) else pe)
                c3.metric(T[lang]['pb'], f"{pb:.2f}" if isinstance(pb, (float, int)) else pb)
                c4.metric(T[lang]['pei'], f"{pei:.2f}" if isinstance(pei, (float, int)) else pei)
                c5.metric(T[lang]['pbi'], f"{pbi:.2f}" if isinstance(pbi, (float, int)) else pbi)
                c6.metric(T[lang]['ind'], ind)

                # BIỂU ĐỒ 2 TẦNG (Yêu cầu 5)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Candle"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # AI PHÂN TÍCH (Sửa lỗi image_b891d6)
                model = get_ai_brain()
                if model:
                    st.subheader(f"🤖 {lang} Expert Report")
                    try:
                        prompt = f"Pro analysis: {query} ({m_target}). Price: {p_now}. Ind P/E: {pei}. RSI: {df['RSI'].iloc[-1]:.2f}. Detect smart money. Reply in {lang}."
                        st.write(model.generate_content(prompt).text)
                    except: st.warning("AI is resting. Please try again in 1 minute.")
            else: st.error("Data Not Found. Please check market selection.")
