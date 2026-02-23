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
st.set_page_config(page_title="AI Terminal V24: Precision", layout="wide")
if 'lang' not in st.session_state: st.session_state.lang = "Tiếng Việt"
L = st.session_state.lang

# --- 2. TỰ VÁ LỖI AI (SELF-HEALING) ---
@st.cache_resource
def get_ai_expert():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m in ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-pro']:
            if m in available: return genai.GenerativeModel(m)
        return genai.GenerativeModel(available[0])
    except: return None

# --- 3. DỮ LIỆU HÀNG HÓA THEO NGÀNH (CONTEXTUAL COMMODITIES) ---
def get_commodity_data(industry_name):
    comm_map = {
        "Thép": {"Quặng Sắt": "TIO=F", "Thép HRC": "HRC=F"},
        "Dầu khí": {"Dầu Brent": "BZ=F", "Khí Gas": "NG=F"},
        "Khai khoáng": {"Vàng": "GC=F", "Đồng": "HG=F"},
        "Tài chính": {"DXY": "DX-Y.NYB", "S&P 500": "^GSPC"}
    }
    
    # Xác định nhóm ngành
    selected_group = "Tài chính" # Mặc định lấy vĩ mô chung
    for key in comm_map.keys():
        if key in str(industry_name):
            selected_group = key
            break
            
    intel = {}
    for name, sym in comm_map[selected_group].items():
        try:
            val = yf.download(sym, period="2d", progress=False)['Close'].iloc[-1]
            intel[name] = round(float(val), 2)
        except: intel[name] = "N/A"
    return intel, selected_group

# --- 4. HỆ THỐNG QUÉT DỮ LIỆU CHÍNH XÁC (VIETNAM FIRST) ---
def fetch_precision_data(ticker):
    symbol = ticker.upper()
    df, p_real, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    # Ưu tiên Việt Nam để tránh nhầm mã quốc tế (Fix lỗi GEX)
    try:
        vn_snap = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}", timeout=2).json()
        if vn_snap and vn_snap[0]['lastPrice'] != 0:
            is_vn = True
            p_real = vn_snap[0]['lastPrice'] * 1000
            # Lấy nến & chỉ số
            end = int(time.time())
            res_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={end-15552000}&to={end}&symbol={symbol}&resolution=1D").json()
            df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=2).json()
            pe, pb, ind = r_f.get('pe', 'N/A'), r_f.get('pb', 'N/A'), r_f.get('industry', 'N/A')
    except: pass

    # Nếu không thấy ở VN mới tìm Quốc tế
    if not is_vn:
        try:
            s = yf.Ticker(symbol)
            df = s.history(period="6mo").reset_index()
            if not df.empty:
                df.columns = [c.lower() for c in df.columns]
                p_real = df['close'].iloc[-1]
                pe, pb, ind = s.info.get('trailingPE', 'N/A'), s.info.get('priceToBook', 'N/A'), s.info.get('industry', 'N/A')
        except: pass
    return df, p_real, pe, pb, ind, is_vn

# --- 5. GIAO DIỆN XỬ LÝ ---
ticker_in = st.text_input("Nhập mã chứng khoán (VD: GEX, HPG, FPT, AAPL):", "GEX").upper()

if st.button("🚀 PHÂN TÍCH"):
    with st.spinner("Đang định vị mã và dữ liệu liên quan..."):
        df, p_now, pe, pb, ind, is_vn = fetch_precision_data(ticker_in)
        
        if df is not None:
            # Chỉ hiển thị hàng hóa nếu đúng ngành
            comm_data, group_name = get_commodity_data(ind)
            
            # Dashboard tài chính
            st.success(f"🌐 Thị trường: {('Việt Nam' if is_vn else 'Quốc tế')} | Ngành: {ind}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá Khớp Lệnh", f"{p_now:,.0f}" if is_vn else f"{p_now:,.2f}")
            c2.metric("P/E", pe)
            c3.metric("P/B", pb)
            c4.metric("Dữ liệu Ngành", group_name)
            
            # Chỉ hiển thị Metrics hàng hóa nếu không phải "Tài chính" (vĩ mô chung)
            if group_name != "Tài chính":
                st.info(f"📊 **Biến số Ngành Thế giới:** " + " | ".join([f"{k}: {v}" for k, v in comm_data.items()]))

            # ĐỒ THỊ 2 TẦNG
            df['MA20'] = ta.sma(df['close'], 20)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Giá"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='orange', width=1), name="MA20"), row=1, col=1)
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Dòng tiền"), row=2, col=1)
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # AI PHÂN TÍCH (Lúc này AI sẽ tự lấy tin tức và vĩ mô vào báo cáo)
            model = get_ai_expert()
            if model:
                st.subheader("🤖 BÁO CÁO CHIẾN LƯỢC CHUYÊN GIA")
                prompt = f"Phân tích mã {ticker_in}, ngành {ind}. Giá {p_now}. Dữ liệu hàng hóa liên quan: {comm_data}. Hãy chỉ rõ tác động của vĩ mô thế giới và dòng tiền cá mập."
                st.write(model.generate_content(prompt).text)
