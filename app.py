import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP & FORENSIC LOG ---
st.set_page_config(page_title="AI Terminal V59: Forensic Vanguard", layout="wide")
debug_container = st.expander("📝 NHẬT KÝ LỖI HỆ THỐNG (DEBUG LOG)", expanded=False)

# --- 2. SIDEBAR CONFIG (Yêu cầu 1, 17) ---
with st.sidebar:
    st.header("⚙️ Configuration")
    lang = st.selectbox("🌐 Language / Ngôn ngữ", ["Tiếng Việt", "English", "日本語", "한국어", "中文"])
    m_config = {
        "Việt Nam": {"suffix": "", "is_intl": False},
        "Mỹ (USA)": {"suffix": "", "is_intl": True},
        "Nhật Bản": {"suffix": ".T", "is_intl": True}
    }
    m_target = st.selectbox("🌍 Thị trường / Market:", list(m_config.keys()))

# --- 3. FIX ResourceExhausted (Yêu cầu 11) ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        priority = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        models = [m.name for m in genai.list_models()]
        for p in priority:
            if p in models: return genai.GenerativeModel(p)
        return None
    except Exception as e:
        debug_container.error(f"AI Setup Error: {e}")
        return None

# --- 4. VANGUARD DATA PROTOCOL (VỚI NOTE LỖI CHI TIẾT) ---
def fetch_vanguard_data(ticker, market_name):
    sym = ticker.upper().strip()
    cfg = m_config[market_name]
    df, p, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    if not cfg["is_intl"]:
        is_vn = True
        try:
            # Snapshot VNDirect
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={sym}", headers=headers, timeout=10)
            if r_p.status_code == 200:
                data = r_p.json()
                if data: p = data[0]['lastPrice'] * 1000
                else: debug_container.warning(f"Note: VNDirect không có mã {sym}")
            else: debug_container.error(f"Note: VNDirect bị chặn (Code {r_p.status_code})")
            
            # Entrade Chart
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time())-15552000}&to={int(time.time())}&symbol={sym}&resolution=1D", headers=headers, timeout=10)
            if r_h.status_code == 200:
                h = r_h.json()
                df = pd.DataFrame({'date': pd.to_datetime(h['t'], unit='s'), 'open': h['o'], 'high': h['h'], 'low': h['l'], 'close': h['c'], 'volume': h['v']})
            else: debug_container.error(f"Note: Entrade bị chặn (Code {r_h.status_code})")
            
            # TCBS Fundamentals
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{sym}/overview", headers=headers, timeout=10)
            if r_f.status_code == 200:
                f = r_f.json()
                pe, pb, ind = f.get('pe', "N/A"), f.get('pb', "N/A"), f.get('industry', "N/A")
            else: debug_container.warning(f"Note: TCBS không phản hồi cho mã {sym}")
        except Exception as e:
            debug_container.error(f"Lỗi truy xuất VN: {e}")
    else:
        try:
            target = sym + cfg["suffix"]
            s = yf.Ticker(target); h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
                pe = s.info.get('trailingPE') or "N/A"; ind = s.info.get('industry') or "N/A"
            else: debug_container.error(f"Note: Yahoo Finance không thấy mã {target}")
        except Exception as e: debug_container.error(f"Lỗi Yahoo: {e}")
    return df, p, pe, pb, ind, is_vn

# --- 5. INTERFACE & ENTER KEY (Yêu cầu 16) ---
query = st.text_input(f"🔍 {'Mã hoặc Câu hỏi và ENTER' if lang == 'Tiếng Việt' else 'Symbol or Query and ENTER'}:", "GEX").upper()

if query:
    if len(query.split()) > 1: # CHATBOT (Yêu cầu 13)
        model = get_ai_brain()
        if model:
            with st.spinner("AI is scanning..."):
                try:
                    prompt = f"Act as a professional financial expert. List 10 specific stocks for: {query} in {m_target}. Symbol and Price only. Reply in {lang}."
                    st.write(model.generate_content(prompt).text)
                except Exception as e: st.error(f"AI Resource Error: {e}")
    else: # ANALYZER
        with st.spinner(f"Synchronizing {query}..."):
            df, p_now, pe, pb, ind, is_vn = fetch_vanguard_data(query, m_target)
            if df is not None and not df.empty:
                for m in [10, 20, 50, 100, 200]: df[f'MA{m}'] = ta.sma(df['close'], m)
                df['RSI'] = ta.rsi(df['close'], 14)
                
                st.success(f"📌 {query} | {m_target}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá / Price", f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
                c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Ngành / Industry", ind)

                # CHART (Yêu cầu 5)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Dữ liệu trống. Hãy nhấn vào 'NHẬT KÝ LỖI HỆ THỐNG' bên dưới để xem chi tiết.")
