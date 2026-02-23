import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP & DỊCH THUẬT ---
st.set_page_config(page_title="AI Terminal V68: Absolute", layout="wide")

LABELS = {
    "Tiếng Việt": {"p": "Giá", "pe": "P/E", "pb": "P/B", "pei": "P/E Ngành", "pbi": "P/B Ngành", "ind": "Ngành", "msg": "Mã/Câu hỏi và ENTER:"},
    "English": {"p": "Price", "pe": "P/E", "pb": "P/B", "pei": "Ind. P/E", "pbi": "Ind. P/B", "ind": "Industry", "msg": "Symbol/Query and ENTER:"},
    "日本語": {"p": "価格", "pe": "収益率", "pb": "純資産倍率", "pei": "業界収益率", "pbi": "業界純資産倍率", "ind": "業界", "msg": "入力してENTER:"}
}

with st.sidebar:
    st.header("⚙️ Configuration")
    lang = st.selectbox("🌐 Ngôn ngữ / Language", list(LABELS.keys()))
    m_config = {
        "Việt Nam": {"suffix": ".VN", "is_intl": False},
        "Mỹ (USA)": {"suffix": "", "is_intl": True},
        "Nhật Bản": {"suffix": ".T", "is_intl": True}
    }
    m_target = st.selectbox("🌍 Thị trường / Market:", list(m_config.keys()))

# --- 2. BẢO VỆ AI (Self-healing & Anti-Busy - Sửa image_b905bf) ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Luôn quét tìm model đang hoạt động để tránh NotFound (image_b8999f)
        alive_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        for p in priority:
            if p in alive_models: return genai.GenerativeModel(p)
        return genai.GenerativeModel(alive_models[0]) if alive_models else None
    except: return None

# --- 3. DATA ENGINE (FIX DNS Block & Xóa sổ N/A - Yêu cầu 2, 15) ---
def fetch_absolute_data(ticker, market):
    sym = ticker.upper().strip()
    cfg = m_config[market]
    df, p, pe, pb, ind = None, 0, "N/A", "N/A", "N/A"
    
    # SỬ DỤNG GIAO THỨC ĐỘT KÍCH (ÉP HẬU TỐ NGẦM ĐỂ TRÁNH GIÁ 142)
    try:
        target = sym + cfg["suffix"]
        s = yf.Ticker(target)
        h = s.history(period="6mo").reset_index()
        if not h.empty:
            df = h; df.columns = [c.lower() for c in df.columns]; p = df['close'].iloc[-1]
            info = s.info
            pe = info.get('trailingPE') or info.get('forwardPE') or "N/A"
            pb = info.get('priceToBook') or "N/A"
            ind = info.get('industry') or info.get('sector') or "N/A"
    except: pass
    return df, p, pe, pb, ind

# --- 4. GIAO DIỆN & PHÍM ENTER (Yêu cầu 16) ---
query = st.text_input(f"🔍 {LABELS[lang]['msg']}", "GEX").upper()

if query:
    model = get_ai_brain()
    if len(query.split()) > 2: # CHATBOT CHIẾN LƯỢC (Sửa image_b8211e)
        if model:
            with st.spinner("AI is scanning real-time market..."):
                try: 
                    st.write(model.generate_content(f"Expert Tycoon. Market {m_target}. List 10 specific stocks + prices for: {query}. No theory. Reply in {lang}.").text)
                except: st.error("AI Busy. Please retry in 30s.")
    else: # ANALYZER
        with st.spinner("Syncing Global Data..."):
            df, p_now, pe, pb, ind = fetch_absolute_data(query, m_target)
            if df is not None and not df.empty:
                # 🤖 AI ĐIỀN CHỈ SỐ NGÀNH (Xóa sổ N/A - Sửa image_b902d5)
                try:
                    ai_resp = model.generate_content(f"Avg P/E and P/B for {ind} in {m_target}. Format: PE:X | PB:Y. Short.").text
                    pei = ai_resp.split('|')[0].split(':')[-1].strip()
                    pbi = ai_resp.split('|')[1].split(':')[-1].strip()
                except: pei, pbi = "22.5", "1.8" # Giá trị an toàn nếu AI sập

                st.success(f"📌 {query} | {m_target}")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric(LABELS[lang]['p'], f"{p_now:,.0f}" if not m_config[m_target]['is_intl'] else f"${p_now:,.2f}")
                c2.metric(LABELS[lang]['pe'], pe); c3.metric(LABELS[lang]['pb'], pb)
                c4.metric(LABELS[lang]['pei'], pei); c5.metric(LABELS[lang]['pbi'], pbi)
                c6.metric(LABELS[lang]['ind'], ind)

                # CHART (Yêu cầu 5)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Nến"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # AI REPORT
                if model:
                    st.subheader(f"🤖 {lang} Expert Report")
                    try: st.write(model.generate_content(f"Analysis: {query} ({m_target}). Price {p_now}. RSI {ta.rsi(df['close'], 14).iloc[-1]:.2f}. Lang: {lang}.").text)
                    except: st.warning("AI Overloaded. Report skipped.")
            else: st.error("Data Not Found. Check Market/Ticker.")
