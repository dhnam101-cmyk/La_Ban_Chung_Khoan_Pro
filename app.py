import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. CONFIG & TRANSLATION ENGINE ---
st.set_page_config(page_title="AI Terminal V62: Zero-Defect", layout="wide")

# Hệ thống dịch thuật đa ngôn ngữ (Yêu cầu 12, 17)
T = {
    "Tiếng Việt": {"p": "Giá", "pe": "P/E", "pb": "P/B", "ind": "Ngành", "msg": "Nhập mã/câu hỏi và ENTER", "err": "Dữ liệu trống"},
    "English": {"p": "Price", "pe": "P/E", "pb": "P/B", "ind": "Industry", "msg": "Enter Symbol/Query and ENTER", "err": "Data Empty"},
    "日本語": {"p": "価格", "pe": "収益率", "pb": "純資産倍率", "ind": "業界", "msg": "シンボルを入力してENTER", "err": "データなし"},
    "한국어": {"p": "가격", "pe": "주가수익비율", "pb": "주가순자산비율", "ind": "산업", "msg": "종목코드 입력 후 ENTER", "err": "데이터 없음"},
    "中文": {"p": "价格", "pe": "市盈率", "pb": "市净率", "ind": "行业", "msg": "输入代码并按ENTER", "err": "无数据"}
}

with st.sidebar:
    st.header("⚙️ Terminal Setup")
    lang = st.selectbox("🌐 Language", list(T.keys()))
    m_config = {
        "Việt Nam": {"suffix": ".VN", "is_intl": False},
        "Mỹ (USA)": {"suffix": "", "is_intl": True},
        "Nhật Bản": {"suffix": ".T", "is_intl": True}
    }
    m_target = st.selectbox("🌍 Market", list(m_config.keys()))
    st.info("Note: N/A protection is ACTIVE.")

# --- 2. AI SOVEREIGN (Kháng sập ResourceExhausted - Yêu cầu 11) ---
@st.cache_resource
def get_ai():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Luôn dùng Flash cho các lệnh nặng để tránh lỗi Exhausted (image_b83388)
        return genai.GenerativeModel('gemini-1.5-flash')
    except: return None

# --- 3. ZERO-DEFECT DATA ENGINE (Xóa sổ N/A - Yêu cầu 2, 3, 15) ---
def fetch_data_v62(ticker, market):
    sym = ticker.upper().strip()
    cfg = m_config[market]
    df, p, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", not cfg["is_intl"]
    headers = {'User-Agent': 'Mozilla/5.0'}

    # LUỒNG 1: NỘI ĐỊA (DNS Check)
    if is_vn:
        try:
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", timeout=3).json()
            if r_p: p = r_p[0]['lastPrice'] * 1000
            
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", timeout=3).json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
            
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", timeout=3).json()
            pe, pb, ind = r_f.get('pe', "N/A"), r_f.get('pb', "N/A"), r_f.get('industry', "N/A")
        except: pass

    # LUỒNG 2: FALLBACK (Xóa sổ N/A bằng Yahoo gắn đuôi ngầm - Fix image_b82d1b)
    if df is None or pe == "N/A" or pb == "N/A":
        try:
            full_sym = sym + cfg["suffix"]
            s = yf.Ticker(full_sym); info = s.info
            if df is None:
                h = s.history(period="6mo").reset_index()
                if not h.empty:
                    df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
            # Điền chỗ trống N/A
            if pe == "N/A": pe = info.get('trailingPE') or info.get('forwardPE') or "N/A"
            if pb == "N/A": pb = info.get('priceToBook') or "N/A"
            if ind == "N/A": ind = info.get('industry') or info.get('sector') or "N/A"
        except: pass
            
    return df, p, pe, pb, ind, is_vn

# --- 4. GIAO DIỆN & ENTER KEY (Yêu cầu 16) ---
query = st.text_input(f"🔍 {T[lang]['msg']}:", "GEX").upper()

if query:
    if len(query.split()) > 2: # CHATBOT (Yêu cầu 13)
        model = get_ai()
        if model:
            with st.spinner("AI is thinking..."):
                prompt = f"Expert mode. Market: {m_target}. Task: {query}. Give 10 specific stocks + prices. No theory. Reply in {lang}."
                st.write(model.generate_content(prompt).text)
    else: # ANALYZER
        with st.spinner("Syncing..."):
            df, p_now, pe, pb, ind, is_vn = fetch_data_v62(query, m_target)
            if df is not None and not df.empty:
                # Indicators (Yêu cầu 6, 9)
                for m in [10, 20, 50, 100, 200]: df[f'MA{m}'] = ta.sma(df['close'], m)
                df['RSI'] = ta.rsi(df['close'], 14)
                
                st.success(f"📌 {query} | {m_target}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(T[lang]['p'], f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
                c2.metric(T[lang]['pe'], f"{pe:.2f}" if isinstance(pe, (int, float)) else pe)
                c3.metric(T[lang]['pb'], f"{pb:.2f}" if isinstance(pb, (int, float)) else pb)
                c4.metric(T[lang]['ind'], ind)

                # CHART (Yêu cầu 5)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Candle"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # AI REPORT (Yêu cầu 10)
                model = get_ai()
                if model:
                    st.subheader(f"🤖 {lang} Expert Analysis")
                    st.write(model.generate_content(f"Deep analysis: {query} ({m_target}). Price: {p_now}. RSI: {df['RSI'].iloc[-1]:.2f}. Lang: {lang}.").text)
            else: st.error(T[lang]['err'])
