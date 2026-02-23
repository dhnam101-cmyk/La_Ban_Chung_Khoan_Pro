import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
import yfinance as yf

# --- 1. SETUP & THEME ---
st.set_page_config(page_title="AI Terminal V31: Final Sovereign", layout="wide")
L = st.sidebar.selectbox("🌐 Ngôn ngữ / Language", ["Tiếng Việt", "English"])

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

# --- 3. RADAR TICKET THÔNG MINH (Yêu cầu 14: Ưu tiên VN > US) ---
def fetch_verified_v31(ticker_raw):
    symbol = ticker_raw.upper()
    df, p_real, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    # ƯU TIÊN SỐ 1: KIỂM TRA VIỆT NAM (DÙ TRÙNG MÃ QUỐC TẾ CŨNG LẤY VN)
    try:
        # Gọi thẳng Snapshot VNDirect để kiểm tra mã VN
        snap = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}", timeout=2).json()
        if snap and snap[0]['lastPrice'] != 0:
            is_vn = True
            p_real = snap[0]['lastPrice'] * 1000
            # Lấy nến lịch sử
            end = int(time.time())
            res_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={end-15552000}&to={end}&symbol={symbol}&resolution=1D").json()
            df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
            # Lấy thông số cơ bản
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=2).json()
            pe, pb, ind = r_f.get('pe', 'N/A'), r_f.get('pb', 'N/A'), r_f.get('industry', 'N/A')
    except: pass

    # ƯU TIÊN SỐ 2: KHÔNG NGẮT QUỐC TẾ - TÌM MỸ/THẾ GIỚI (NẾU VN KHÔNG CÓ)
    if df is None:
        try:
            s = yf.Ticker(symbol)
            h = s.history(period="6mo").reset_index()
            if not h.empty:
                df = h; df.columns = [c.lower() for c in df.columns]
                p_real = df['close'].iloc[-1]
                pe = s.info.get('trailingPE', 'N/A')
                pb = s.info.get('priceToBook', 'N/A')
                ind = s.info.get('industry', 'N/A')
                is_vn = False
        except: pass
        
    return df, p_real, pe, pb, ind, is_vn

# --- 4. GIAO DIỆN & XỬ LÝ ---
query = st.text_input("Mã (GEX, NVDA, 7203.T) hoặc Câu hỏi chiến lược:", "GEX").upper()

if st.button("🚀 KÍCH HOẠT HỆ THỐNG"):
    with st.spinner("Radar đang quét dữ liệu toàn cầu..."):
        if len(query.split()) == 1: # Phân tích mã
            df, p_now, pe, pb, ind, is_vn = fetch_verified_v31(query)
            if df is not None:
                # Tính chỉ báo Kỹ thuật
                df['MA20'] = ta.sma(df['close'], 20)
                df['MA50'] = ta.sma(df['close'], 50)
                df['MA200'] = ta.sma(df['close'], 200)
                df['RSI'] = ta.rsi(df['close'], 14)
                
                st.success(f"🌐 Thị trường: {('Việt Nam' if is_vn else 'Quốc tế')} | Ngành: {ind}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá", f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
                c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Dòng tiền", "Đang phân tích")

                # BIỂU ĐỒ 2 TẦNG (Sửa lỗi SyntaxError)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Nến"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
                
                colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Volume"), row=2, col=1)
                
                # CHỐT CÚ PHÁP TẠI ĐÂY - ĐẢM BẢO KHÔNG THIẾU DẤU NGOẶC
                fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                # AI BÁO CÁO CHUYÊN GIA
                model = get_ai_expert()
                if model:
                    prompt = f"Phân tích chuyên sâu mã {query} ({'VN' if is_vn else 'Global'}). Giá {p_now}. Chỉ rõ dòng tiền cá mập, kỹ thuật (MA, RSI, MACD), và vĩ mô thế giới (DXY, S&P 500)."
                    st.write(model.generate_content(prompt).text)
            else: st.error("Mã không hợp lệ hoặc lỗi dữ liệu.")
        else:
            # CHATBOT (Yêu cầu 13)
            model = get_ai_expert()
            if model: st.write(model.generate_content(f"Trả lời câu hỏi tài chính: {query}").text)
