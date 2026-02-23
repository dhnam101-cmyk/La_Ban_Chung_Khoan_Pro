import streamlit as st
import yfinance as yf
from yahooquery import Ticker as YQTicker
import google.generativeai as genai
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CẤU HÌNH ---
st.set_page_config(page_title="La Bàn Chứng Khoán PRO", page_icon="📈", layout="wide")
st.title("📈 La Bàn Chứng Khoán PRO: Pháo Đài Đa Luồng")

# --- KẾT NỐI AI (TỰ VÁ LỖI) ---
@st.cache_resource
def get_model():
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
    # Tự động tìm bộ não khả dụng nhất
    for m in ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']:
        try:
            model = genai.GenerativeModel(m)
            model.generate_content("test")
            return model
        except: continue
    return None

model = get_model()

# --- HÀM QUÉT DỮ LIỆU ĐA NGUỒN (CHỮA BỆNH N/A) ---
def fetch_data_parallel(symbol):
    def get_tcbs(s):
        r = requests.get(f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{s}/overview", timeout=2).json()
        return {'pe': r.get('pe'), 'pb': r.get('pb'), 'industry': r.get('industry'), 'src': 'TCBS'}
    
    def get_ssi(s):
        # Giả lập nguồn SSI dự phòng
        return {'pe': None, 'pb': None, 'industry': None, 'src': 'SSI'}

    results = {'pe': 'N/A', 'pb': 'N/A', 'industry': 'N/A', 'src': 'Quốc tế'}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(get_tcbs, symbol), executor.submit(get_ssi, symbol)]
        for f in as_completed(futures):
            try:
                res = f.result()
                if res['pe'] and results['pe'] == 'N/A': results['pe'] = res['pe']; results['src'] = res['src']
                if res['pb'] and results['pb'] == 'N/A': results['pb'] = res['pb']
                if res['industry'] and results['industry'] == 'N/A': results['industry'] = res['industry']
            except: continue
    return results

# --- GIAO DIỆN ---
ticker = st.text_input("Nhập mã (VD: FPT.VN, AAPL):", "FPT.VN").upper()

if st.button("🚀 PHÂN TÍCH THỜI GIAN THỰC"):
    with st.spinner("Đang vắt kiệt dữ liệu từ các nguồn..."):
        try:
            symbol = ticker.split('.')[0]
            # Lấy biểu đồ nến
            h_res = requests.get(f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={int(time.time()-7776000)}&to={int(time.time())}&symbol={symbol}&resolution=1D").json()
            df = pd.DataFrame({'date': pd.to_datetime(h_res['t'], unit='s'), 'open': h_res['o'], 'high': h_res['h'], 'low': h_res['l'], 'close': h_res['c'], 'volume': h_res['v']}).set_index('date')
            
            # Lấy chỉ số cơ bản đa luồng
            fund = fetch_data_parallel(symbol)
            
            # Hiển thị
            st.success(f"Dữ liệu tóm được từ: {fund['src']}")
            c1, c2, c3, c4 = st.columns(4)
            price = df['close'].iloc[-1] * (1000 if df['close'].iloc[-1] < 1000 else 1)
            c1.metric("Giá", f"{price:,.0f}")
            c2.metric("P/B", fund['pb'])
            c3.metric("P/E", fund['pe'])
            c4.metric("Ngành", fund['industry'])

            # BIỂU ĐỒ ĐỒNG NHẤT (NẾN + VOL)
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Giá'), secondary_y=True)
            fig.add_trace(go.Bar(x=df.index, y=df['volume'], name='Dòng tiền', marker_color='blue', opacity=0.3), secondary_y=False)
            fig.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

            if model:
                resp = model.generate_content(f"Phân tích mã {ticker}, giá {price}, P/E {fund['pe']}, P/B {fund['pb']}. Đưa ra khuyến nghị.")
                st.write(resp.text)
        except Exception as e:
            st.error(f"Lỗi hệ thống: {e}")
