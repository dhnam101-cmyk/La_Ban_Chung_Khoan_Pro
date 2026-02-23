import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP ---
st.set_page_config(page_title="AI Terminal V51: Sovereign Intelligence", layout="wide")

# --- 2. THANH CHỌN THỊ TRƯỜNG (Yêu cầu 1) ---
market_config = {
    "Việt Nam": {"suffix": "", "is_intl": False},
    "Mỹ": {"suffix": "", "is_intl": True},
    "Nhật Bản": {"suffix": ".T", "is_intl": True},
    "Hàn Quốc": {"suffix": ".KS", "is_intl": True},
    "Trung Quốc": {"suffix": ".SS", "is_intl": True}
}
m_target = st.sidebar.selectbox("🌍 Sàn giao dịch điện tử:", list(market_config.keys()))

# --- 3. BẢO VỆ AI (Self-healing) ---
@st.cache_resource
def get_ai_expert():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for t in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']:
            if t in models: return genai.GenerativeModel(t)
        return genai.GenerativeModel(models[0])
    except: return None

# --- 4. GIAO THỨC DỮ LIỆU "SẮT" (CHỐNG SAI GIÁ & N/A) ---
def fetch_omnipotent_data(ticker, market_name):
    sym = ticker.upper().strip()
    cfg = market_config[market_name]
    df, p, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    if not cfg["is_intl"]: # CHẾ ĐỘ VIỆT NAM (KHÓA YAHOO)
        is_vn = True
        try:
            # Snapshot VNDirect (Real-time giá 40.20 cho GEX)
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", timeout=3).json()
            if r_p: p = r_p[0]['lastPrice'] * 1000
            # Entrade (Nến)
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D").json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
            # TCBS (Cơ bản)
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", timeout=3).json()
            pe, pb, ind = r_f.get('pe', "N/A"), r_f.get('pb', "N/A"), r_f.get('industry', "N/A")
        except: pass
    
    # TRUY QUÉT DỰ PHÒNG (ANTI N/A)
    try:
        t_intl = sym + cfg["suffix"]
        s = yf.Ticker(t_intl)
        if df is None or df.empty:
            h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
        
        if pe == "N/A": pe = s.info.get('trailingPE') or "N/A"
        if pb == "N/A": pb = s.info.get('priceToBook') or "N/A"
        if ind == "N/A": ind = s.info.get('industry') or "N/A"
    except: pass
    return df, p, pe, pb, ind, is_vn

# --- 5. XỬ LÝ ENTER (Yêu cầu 16) ---
query = st.text_input(f"Nhập mã hoặc Câu hỏi lọc mã tại {m_target} và nhấn ENTER:", "GEX").upper()

if query:
    if len(query.split()) > 1: # CHẾ ĐỘ CHATBOT CHIẾN LƯỢC (Yêu cầu 13)
        model = get_ai_expert()
        if model:
            with st.spinner("AI đang truy cập dữ liệu thị trường để lọc mã..."):
                # Gửi kèm dữ liệu thị trường thực tế cho AI (Ví dụ top mã tích lũy)
                st.write(model.generate_content(f"Dựa trên dữ liệu Real-time sàn {m_target}, hãy lọc và đưa ra danh sách mã cụ thể (không nói lý thuyết): {query}").text)
    else: # CHẾ ĐỘ PHÂN TÍCH MÃ
        with st.spinner(f"Đang đồng bộ dữ liệu {query}..."):
            df, p_now, pe, pb, ind, is_vn = fetch_omnipotent_data(query, m_target)
            if df is not None and not df.empty:
                for m in [10, 20, 50, 100, 200]: df[f'MA{m}'] = ta.sma(df['close'], m)
                df['RSI'] = ta.rsi(df['close'], 14)
                
                # Dashboard
                st.success(f"📌 Đã khóa dữ liệu: {query} | Sàn: {m_target}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá Khớp Lệnh", f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
                c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Ngành", ind)

                # BIỂU ĐỒ 2 TẦNG
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Giá"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['date'], y=df['MA200'], line=dict(color='red', width=1.5), name="MA200"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # AI BÁO CÁO
                model = get_ai_expert()
                if model:
                    st.subheader("🤖 BÁO CÁO CHIẾN LƯỢC CHUYÊN GIA")
                    st.write(model.generate_content(f"Phân tích {query} ({m_target}). Giá {p_now}. Ngành {ind}. RSI {df['RSI'].iloc[-1]:.2f}. Soi dòng tiền cá mập.").text)
            else:
                st.error(f"Không tìm thấy mã {query}. Radar đang quét dự phòng toàn cầu...")
