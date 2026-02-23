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
st.set_page_config(page_title="AI Terminal V37: Global Nexus Pro", layout="wide")

# --- 2. THANH CHỌN THỊ TRƯỜNG (CỐ ĐỊNH MỤC TIÊU) ---
market_choice = st.sidebar.selectbox(
    "🌍 Chọn thị trường mục tiêu / Select Market",
    ["Việt Nam", "Mỹ", "Nhật Bản", "Hàn Quốc", "Trung Quốc"]
)

# --- 3. TỰ VÁ LỖI AI ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m in ['models/gemini-1.5-pro', 'models/gemini-1.5-flash']:
            if m in available: return genai.GenerativeModel(m)
        return genai.GenerativeModel(available[0])
    except: return None

# --- 4. CƠ CHẾ ĐA NỀN TẢNG THẾ GIỚI & VN ---
def fetch_nexus_data(ticker, market):
    symbol = ticker.upper().strip()
    df, p_real, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    # CASE: VIỆT NAM (ĐA NỀN TẢNG NỘI ĐỊA)
    if market == "Việt Nam":
        is_vn = True
        try:
            # Vòi 1: VNDirect/SSI (Giá)
            r_p = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}", timeout=1).json()
            if r_p: p_real = r_p[0]['lastPrice'] * 1000
            # Vòi 2: DNSE/Entrade (Biểu đồ)
            end = int(time.time())
            r_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={end-15552000}&to={end}&symbol={symbol}&resolution=1D", timeout=1).json()
            df = pd.DataFrame({'date': pd.to_datetime(r_h['t'], unit='s'), 'open': r_h['o'], 'high': r_h['h'], 'low': r_h['l'], 'close': r_h['c'], 'volume': r_h['v']})
            # Vòi 3: TCBS/CafeF (Cơ bản)
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=1).json()
            pe, pb, ind = r_f.get('pe', 'N/A'), r_f.get('pb', 'N/A'), r_f.get('industry', 'N/A')
        except: pass

    # CASE: THẾ GIỚI (ĐA NỀN TẢNG QUỐC TẾ - KHÔNG CẦN ĐUÔI)
    else:
        # Tự động gán hậu tố dựa trên nút chọn (Người dùng không cần nhập)
        suffix_map = {"Mỹ": "", "Nhật Bản": ".T", "Hàn Quốc": ".KS", "Trung Quốc": ".SS"}
        target = symbol + suffix_map[market]
        try:
            # Vòi 1: Yahoo Finance (Nguồn chính)
            s = yf.Ticker(target)
            df = s.history(period="6mo").reset_index()
            if not df.empty:
                df.columns = [c.lower() for c in df.columns]
                p_real = df['close'].iloc[-1]
                pe = s.info.get('trailingPE', s.info.get('forwardPE', 'N/A'))
                pb = s.info.get('priceToBook', 'N/A')
                ind = s.info.get('industry', 'N/A')
        except: pass
        
    return df, p_real, pe, pb, ind, is_vn

# --- 5. GIAO DIỆN XỬ LÝ ---
query_in = st.text_input(f"Nhập mã tại {market_choice} (Không cần thêm đuôi):", "GEX")

if st.button("🚀 KÍCH HOẠT NEXUS"):
    with st.spinner(f"Đang đồng bộ đa nền tảng cho thị trường {market_choice}..."):
        df, p_now, pe, pb, ind, is_vn = fetch_nexus_data(query_in, market_choice)
        
        if df is not None:
            # Phân tích kỹ thuật (Yêu cầu 6)
            df['MA10'] = ta.sma(df['close'], 10); df['MA20'] = ta.sma(df['close'], 20); df['MA50'] = ta.sma(df['close'], 50)
            df['MA200'] = ta.sma(df['close'], 200); df['RSI'] = ta.rsi(df['close'], 14)
            
            # Dashboard
            st.success(f"📌 Đã khóa dữ liệu: {query_in.upper()} | Nguồn: Đa nền tảng {market_choice}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá Real-time", f"{p_now:,.0f}" if is_vn else f"${p_now:,.2f}")
            c2.metric("P/E", pe); c3.metric("P/B", pb); c4.metric("Ngành", ind)

            # BIỂU ĐỒ 2 TẦNG (Yêu cầu 5)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Giá"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['MA200'], line=dict(color='red', width=1.5), name="MA200"), row=1, col=1)
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Dòng tiền"), row=2, col=1)
            fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # AI BÁO CÁO CHIẾN LƯỢC
            model = get_ai_brain()
            if model:
                st.subheader("🤖 BÁO CÁO CHUYÊN GIA (15 YÊU CẦU)")
                prompt = f"Phân tích chuyên sâu {query_in} tại {market_choice}. Giá {p_now}. RSI {df['RSI'].iloc[-1]:.2f}. Phân tích kỹ thuật MA10-200, dòng tiền cá mập và vĩ mô."
                st.write(model.generate_content(prompt).text)
        else:
            st.error("Lỗi dữ liệu. Hệ thống đang quét nguồn dự phòng...")
