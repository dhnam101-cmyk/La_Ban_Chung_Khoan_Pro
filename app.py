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
st.set_page_config(page_title="Hệ Thống Phân Tích Pro V25", layout="wide")

# --- 2. TỰ VÁ LỖI AI ---
@st.cache_resource
def get_ai_brain():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m in ['models/gemini-1.5-pro', 'models/gemini-1.5-flash', 'models/gemini-pro']:
            if m in available: return genai.GenerativeModel(m)
        return genai.GenerativeModel(available[0])
    except: return None

# --- 3. DỮ LIỆU NGÀNH & HÀNG HÓA (CHỈ GỌI KHI CẦN) ---
def fetch_commodity_for_ai(industry):
    relevant = {}
    mapping = {
        "Thép": {"Quặng Sắt": "TIO=F", "Thép HRC": "HRC=F"},
        "Dầu khí": {"Dầu Brent": "BZ=F", "Khí Gas": "NG=F"}
    }
    target = None
    for key in mapping:
        if key in str(industry): target = mapping[key]; break
    
    if target:
        for name, sym in target.items():
            try:
                val = yf.download(sym, period="1d", progress=False)['Close'].iloc[-1]
                relevant[name] = round(float(val), 2)
            except: pass
    return relevant

# --- 4. HỆ THỐNG QUÉT DỮ LIỆU (VIETNAM STRICT - FIX LỖI GIÁ) ---
def fetch_verified_v25(ticker):
    symbol = ticker.upper()
    df, p_real, pe, pb, ind, is_vn = None, 0, "N/A", "N/A", "N/A", False
    
    # Ưu tiên kiểm tra Việt Nam qua cổng Entrade/VNDirect
    try:
        # Check giá snapshot trước để xác định mã VN
        snap = requests.get(f"https://api-price.vndirect.com.vn/stocks/snapshot?symbols={symbol}", timeout=2).json()
        if snap and snap[0]['lastPrice'] != 0:
            is_vn = True
            p_real = snap[0]['lastPrice'] * 1000
            # Lấy nến
            end = int(time.time())
            res_h = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={end-15552000}&to={end}&symbol={symbol}&resolution=1D").json()
            df = pd.DataFrame({'date': pd.to_datetime(res_h['t'], unit='s'), 'open': res_h['o'], 'high': res_h['h'], 'low': res_h['l'], 'close': res_h['c'], 'volume': res_h['v']})
            # Lấy cơ bản
            r_f = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview", timeout=2).json()
            pe, pb, ind = r_f.get('pe', 'N/A'), r_f.get('pb', 'N/A'), r_f.get('industry', 'N/A')
    except: pass

    # Nếu không phải mã VN, mới dùng Yahoo Finance
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

# --- 5. GIAO DIỆN ---
query = st.text_input("Nhập mã chứng khoán hoặc câu hỏi chiến lược (VD: GEX, HPG):", "GEX").upper()

if st.button("🚀 PHÂN TÍCH CHUYÊN GIA"):
    with st.spinner("Đang truy xuất dữ liệu thực tế..."):
        df, p_now, pe, pb, ind, is_vn = fetch_verified_v25(query)
        
        if df is not None:
            # Dashboard tài chính (Giá Real-time khớp 100%)
            st.success(f"🌐 Thị trường: {('Việt Nam' if is_vn else 'Quốc tế')} | Ngành: {ind}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá Khớp Lệnh", f"{p_now:,.0f}" if is_vn else f"{p_now:,.2f}")
            c2.metric("P/E", pe)
            c3.metric("P/B", pb)
            c4.metric("Dòng tiền", "Đang theo dõi")

            # BIỂU ĐỒ 2 TẦNG (TÁCH BIỆT)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Giá"), row=1, col=1)
            colors = ['#EF5350' if df['open'].iloc[i] > df['close'].iloc[i] else '#26A69A' for i in range(len(df))]
            fig.add_trace(go.Bar(x=df['date'], y=df['volume'], marker_color=colors, name="Khối lượng"), row=2, col=1)
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # AI BÁO CÁO (TÍCH HỢP HÀNG HÓA VÀO ĐÂY)
            comm_info = fetch_commodity_for_ai(ind)
            model = get_ai_brain()
            if model:
                st.subheader("🤖 BÁO CÁO CHIẾN LƯỢC CHUYÊN GIA")
                prompt = f"""Phân tích mã {query}. Ngành: {ind}. Giá thực tế: {p_now}. 
                Dữ liệu hàng hóa thế giới liên quan (nếu có): {comm_info}.
                Yêu cầu: Chỉ rõ dòng tiền cá mập, kỹ thuật chi tiết, và tác động vĩ mô."""
                st.write(model.generate_content(prompt).text)
        else:
            st.error("Không tìm thấy mã này. Radar đang quét lại...")
