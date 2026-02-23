import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP & FORENSIC ENGINE ---
st.set_page_config(page_title="AI Terminal V61: Finality", layout="wide")
debug_panel = st.expander("📝 BẢNG PHÂN TÍCH LỖI (SYSTEM NOTE)", expanded=False)

# --- 2. SIDEBAR CONFIG (Yêu cầu 1, 12, 17) ---
with st.sidebar:
    st.header("⚙️ Terminal Config")
    lang = st.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English", "日本語", "한국어", "中文"])
    m_config = {
        "Việt Nam": {"suffix": ".VN", "is_intl": False},
        "Mỹ (USA)": {"suffix": "", "is_intl": True},
        "Nhật Bản": {"suffix": ".T", "is_intl": True},
        "Hàn Quốc": {"suffix": ".KS", "is_intl": True}
    }
    m_target = st.selectbox("🌍 Thị trường / Market:", list(m_config.keys()))

# --- 3. KHÁNG SẬP AI (Self-healing - Yêu cầu 11) ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for t in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']:
            if t in models: return genai.GenerativeModel(t)
        return genai.GenerativeModel(models[0])
    except Exception as e:
        debug_panel.error(f"Note: Lỗi khởi tạo AI ({e})")
        return None

# --- 4. GIAO THỨC DỮ LIỆU ĐỘT KÍCH (Vượt chặn DNS & Fix giá 142) ---
def fetch_omnipotent_data(ticker, market_name):
    sym = ticker.upper().strip()
    cfg = m_config[market_name]
    df, p, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    headers = {'User-Agent': 'Mozilla/5.0'}

    # LUỒNG 1: NỘI ĐỊA (Ưu tiên tuyệt đối để tránh giá 142)
    if not cfg["is_intl"]:
        is_vn = True
        try:
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", headers=headers, timeout=5)
            if r_p.status_code == 200 and r_p.json(): p = r_p.json()[0]['lastPrice'] * 1000
            
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", headers=headers, timeout=5)
            if r_h.status_code == 200:
                h = r_h.json()
                df = pd.DataFrame({'date': pd.to_datetime(h['t'], unit='s'), 'open': h['o'], 'high': h['h'], 'low': h['l'], 'close': h['c'], 'volume': h['v']})
            
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", headers=headers, timeout=5)
            if r_f.status_code == 200:
                f = r_f.json()
                pe, pb, ind = f.get('pe', "N/A"), f.get('pb', "N/A"), f.get('industry', "N/A")
        except Exception: 
            debug_panel.warning(f"Note: DNS nội địa bị nghẽn. Kích hoạt radar đột kích quốc tế gắn đuôi .VN")

    # LUỒNG 2: ĐỘT KÍCH QUỐC TẾ (Bù đắp dữ liệu N/A và vượt DNS)
    if df is None or df.empty:
        try:
            target_intl = sym + cfg["suffix"]
            s = yf.Ticker(target_intl)
            h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
                info = s.info
                pe = info.get('trailingPE') or "N/A"; ind = info.get('industry') or "N/A"
        except Exception as e:
            debug_panel.error(f"Note: Mất kết nối toàn phần cho mã {sym} ({e})")
            
    return df, p, pe, pb, ind, is_vn

# --- 5. INTERFACE & ENTER KEY (Yêu cầu 16) ---
q_label = "Mã hoặc Câu hỏi lọc cổ phiếu (Nhấn ENTER):" if lang == "Tiếng Việt" else "Symbol or Screening Query (ENTER):"
query = st.text_input(f"🔍 {q_label}", "GEX").upper()

if query:
    if len(query.split()) > 1: # CHATBOT LỌC MÃ (Yêu cầu 13)
        model = get_ai_brain()
        if model:
            with st.spinner("AI Sovereign is scanning market..."):
                prompt = f"Act as a tycoon. For {m_target}, LIST 10 SPECIFIC CODES for: {query}. Symbols and prices only. No theory. Language: {lang}."
                st.write(model.generate_content(prompt).text)
    else: # ANALYZER
        with st.spinner(f"Synchronizing {query} real-time..."):
            df, p_now, pe, pb, ind, is_vn = fetch_omnipotent_data(query, m_target)
            if df is not None and not df.empty:
                for m in [10, 20, 50, 100, 200]: df[f'MA{m}'] = ta.sma(df['close'], m)
                df['RSI'] = ta.rsi(df['close'], 14)
                
                st.success(f"📌 {query} | {m_target}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá / Price", f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
                c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Ngành / Industry", ind)

                # BIỂU ĐỒ (Yêu cầu 5)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # BÁO CÁO AI (Yêu cầu 10)
                model = get_ai_brain()
                if model:
                    st.subheader(f"🤖 Expert Analysis ({lang})")
                    st.write(model.generate_content(f"Pro analysis of {query} ({m_target}). Price {p_now}. RSI {df['RSI'].iloc[-1]:.2f}. Language: {lang}.").text)
            else:
                st.error("Dữ liệu trống. Hãy mở 'BẢNG PHÂN TÍCH LỖI' bên dưới để xem chi tiết.")
