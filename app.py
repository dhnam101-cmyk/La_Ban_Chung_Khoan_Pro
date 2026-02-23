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

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="La Bàn Chứng Khoán PRO", page_icon="📈", layout="wide")
st.title("📈 La Bàn Chứng Khoán PRO: Pháo Đài Dữ Liệu")
st.markdown("Hệ thống đa luồng quét dữ liệu từ 4 nguồn nội địa (TCBS, SSI, VND, DNSE) và quốc tế.")

# --- KẾT NỐI AI ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("🔴 LỖI API KEY: Vui lòng kiểm tra lại mục Secrets.")
    st.stop()

# --- CÔNG CỤ QUÉT DỮ LIỆU CƠ BẢN ĐA NGUỒN (P/E, P/B, NGÀNH) ---
def fetch_from_tcbs(symbol):
    url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview"
    res = requests.get(url, timeout=3).json()
    return {'pe': res.get('pe'), 'pb': res.get('pb'), 'industry': res.get('industry'), 'source': 'TCBS'}

def fetch_from_ssi(symbol):
    # Giả lập gọi API SSI (Dạng dự phòng cấu trúc tương đương)
    url = f"https://gateway.ssi.com.vn/api/v1/StockQuotes/GetFundamental?symbol={symbol}"
    res = requests.get(url, timeout=3).json()
    data = res.get('data', {})
    return {'pe': data.get('Pe'), 'pb': data.get('Pb'), 'industry': data.get('IndustryName'), 'source': 'SSI'}

def fetch_from_vnd(symbol):
    url = f"https://finfo-api.vndirect.com.vn/v4/stocks?q=code:{symbol}"
    res = requests.get(url, timeout=3).json()
    data = res.get('data', [{}])[0]
    return {'pe': None, 'pb': None, 'industry': data.get('industryName'), 'source': 'VND'}

def get_fundamental_multi_sources(symbol):
    sources = [fetch_from_tcbs, fetch_from_ssi, fetch_from_vnd]
    final_data = {'pe': 'N/A', 'pb': 'N/A', 'industry': 'N/A', 'source': 'None'}
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_url = {executor.submit(func, symbol): func for func in sources}
        for future in as_completed(future_to_url):
            try:
                res = future.result()
                # Nếu tìm thấy dữ liệu hợp lệ, ưu tiên cập nhật ngay
                if res['pe'] and final_data['pe'] == 'N/A': 
                    final_data['pe'] = res['pe']
                    final_data['source'] = res['source']
                if res['pb'] and final_data['pb'] == 'N/A': 
                    final_data['pb'] = res['pb']
                if res['industry'] and final_data['industry'] == 'N/A': 
                    final_data['industry'] = res['industry']
            except:
                continue
    return final_data

# --- TRẠM LẤY BIỂU ĐỒ NẾN ---
def get_stock_data(ticker):
    symbol = ticker.split('.')[0].upper()
    end_time = int(time.time())
    start_time = end_time - (90 * 24 * 60 * 60)
    
    # Lấy biểu đồ nến từ DNSE
    url_hist = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={start_time}&to={end_time}&symbol={symbol}&resolution=1D"
    res = requests.get(url_hist).json()
    df = pd.DataFrame({'date': pd.to_datetime(res['t'], unit='s'), 'open': res['o'], 'high': res['h'], 'low': res['l'], 'close': res['c'], 'volume': res['v']}).set_index('date')
    
    # Quy đổi giá VN
    current_price = df['close'].iloc[-1] * 1000 if df['close'].iloc[-1] < 1000 else df['close'].iloc[-1]
    
    # Quét đa nguồn lấy P/E, P/B
    fundamentals = get_fundamental_multi_sources(symbol)
    
    return df, current_price, fundamentals['pe'], fundamentals['pb'], fundamentals['industry'], fundamentals['source']

# --- GIAO DIỆN ---
ticker_input = st.text_input("Mã cổ phiếu:", "FPT.VN").upper()
btn_run = st.button("🚀 PHÂN TÍCH ĐA NGUỒN")

if btn_run:
    with st.spinner("Đang quét toàn bộ hệ thống tài chính..."):
        try:
            hist, price, pe, pb, ind, src = get_stock_data(ticker_input)
            
            st.success(f"Dữ liệu được tóm gọn từ: {src}")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá", f"{price:,.0f}")
            c2.metric("P/B", pb)
            c3.metric("P/E", pe)
            c4.metric("Ngành", ind)

            # Biểu đồ đồng nhất
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Candlestick(x=hist.index, open=hist['open'], high=hist['high'], low=hist['low'], close=hist['close'], name='Nến giá'), secondary_y=True)
            fig.add_trace(go.Bar(x=hist.index, y=hist['volume'], name='Khối lượng', marker_color='blue', opacity=0.2), secondary_y=False)
            fig.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

            # AI Phân tích
            prompt = f"Phân tích mã {ticker_input}, giá {price}, P/E {pe}, P/B {pb}. Dòng tiền 10 phiên: {hist['volume'].tail(10).tolist()}. Đưa ra nhận định Mua/Bán."
            response = model.generate_content(prompt)
            st.write(response.text)
            
        except Exception as e:
            st.error(f"Lỗi: {e}")
