import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP HỆ THỐNG ---
st.set_page_config(page_title="AI Terminal V33: Sovereign Gate", layout="wide")

# --- 2. TỰ VÁ LỖI AI ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-pro']
        for m in priority:
            if m in available: return genai.GenerativeModel(m)
        return genai.GenerativeModel(available[0])
    except: return None

# --- 3. RADAR KHÓA MÃ (VIETNAM FIRST - STRICT MODE) ---
def fetch_strict_sovereign(query_raw):
    raw = query_raw.upper().strip()
    df, p_real, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False

    # TRƯỜNG HỢP 1: NGƯỜI DÙNG CỐ Ý TRA MÃ MỸ (THÊM .US)
    if raw.endswith(".US"):
        ticker_us = raw.replace(".US", "")
        try:
            s = yf.Ticker(ticker_us)
            df = s.history(period="6mo").reset_index()
            if not df.empty:
                df.columns = [c.lower() for c in df.columns]; p_real = df['close'].iloc[-1]
                pe, pb, ind = s.info.get('trailingPE', 'N/A'), s.info.get('priceToBook', 'N/A'), s.info.get('industry', 'N/A')
                return df, p_real, pe, pb, ind, False
        except: pass

    # TRƯỜNG HỢP 2: ƯU TIÊN TUYỆT ĐỐI VIỆT NAM (DÀNH CHO MÃ 3 CHỮ CÁI)
    # Không cho phép Yahoo can thiệp vào giai đoạn này
    try:
        vn_price_url = f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={raw}"
        snap = requests.get(vn_price_url, timeout=2).json()
        if snap and snap[0]['lastPrice'] != 0:
            is_vn = True
            p_real = snap[0]['lastPrice'] * 1000
            # Lấy nến nội địa
            end_t = int(time.time())
            res_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={end_t-15552000}&to={end_t}&symbol={raw}&resolution=1D").json()
            df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
            # Lấy cơ bản
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{raw}/overview", timeout=2).json()
            pe, pb, ind = r_f.get('pe', 'N/A'), r_f.get('pb', 'N/A'), r_f.get('industry', 'N/A')
            return df, p_real, pe, pb, ind, True # THẤY VN LÀ KHÓA LUÔN, KHÔNG TÌM TIẾP
    except: pass

    # TRƯỜNG HỢP 3: TRA MÃ QUỐC TẾ (NẾU KHÔNG CÓ Ở VN)
    try:
        s_intl = yf.Ticker(raw)
        df_intl = s_intl.history(period="6mo").reset_index()
        if not df_intl.empty:
            df_intl.columns = [c.lower() for c in df_intl.columns]; p_real = df_intl['close'].iloc[-1]
            pe, pb, ind = s_intl.info.get('trailingPE', 'N/A'), s_intl.info.get('priceToBook', 'N/A'), s_intl.info.get('industry', 'N/A')
            return df_intl, p_real, pe, pb, ind, False
    except: pass
    
    return None, 0, "N/A", "N/A", "N/A", False

# --- 4. GIAO DIỆN CHÍNH ---
query_in = st.text_input("Mã (GEX, HPG, AAPL, GEX.US) hoặc Câu hỏi chiến lược:", "GEX")

if st.button("🚀 KÍCH HOẠT TỔNG LỰC"):
    with st.spinner("Đang thực hiện giao thức Sovereign..."):
        if len(query_in.split()) == 1:
            df, p_now, pe, pb, ind, is_vn = fetch_strict_sovereign(query_in)
            if df is not None:
                # Phân tích kỹ thuật đầy đủ
                df['MA20'] = ta.sma(df['close'], 20); df['MA50'] = ta.sma(df['close'], 50); df['MA200'] = ta.sma(df['close'], 200)
                df['RSI'] = ta.rsi(df['close'], 14)
                
                # Dashboard
                st.success(f"📌 Thị trường: {('Việt Nam (HOSE/HNX/UPCOM)' if is_vn else 'Quốc tế')} | Ngành: {ind}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá Khớp Lệnh", f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
                c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Xu hướng", "Đang phân tích")

                # BIỂU ĐỒ 2 TẦNG CHUẨN TRADINGVIEW
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Nến"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # AI BÁO CÁO (Sử dụng dữ liệu thật)
                model = get_ai_brain()
                if model:
                    st.subheader("🤖 BÁO CÁO CHIẾN LƯỢC CHUYÊN GIA")
                    prompt = f"Phân tích chuyên sâu mã {query_in} ({'VN' if is_vn else 'Global'}). Giá thực: {p_now}. Chỉ rõ dòng tiền cá mập, kỹ thuật (MA, RSI)."
                    st.write(model.generate_content(prompt).text)
            else: st.error("Không tìm thấy mã này. Radar đang quét lại...")
        else:
            model = get_ai_brain()
            if model: st.write(model.generate_content(f"Trả lời câu hỏi tài chính: {query_in}").text)
