import streamlit as st
import yfinance as yf
from yahooquery import Ticker as YQTicker
import google.generativeai as genai
import pandas as pd
import requests
import time

st.set_page_config(page_title="La Bàn Chứng Khoán PRO", page_icon="📈", layout="wide")
st.title("📈 La Bàn Chứng Khoán PRO: Auto-Pilot")
st.markdown("Hệ thống tự động dò tìm AI, tự vá lỗi và thích ứng với dữ liệu.")

# --- BỘ RADAR TỰ ĐỘNG TÌM AI PHÙ HỢP NHẤT ---
@st.cache_resource(show_spinner="Đang dò tìm phiên bản AI tốt nhất cho API Key của bạn...")
def get_auto_ai_model(api_key):
    genai.configure(api_key=api_key)
    try:
        # Lấy toàn bộ danh sách AI mà Google cho phép tài khoản này dùng
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        if not available_models:
            raise ValueError("Tài khoản của bạn chưa được cấp quyền dùng AI tạo chữ.")

        # Xếp hạng ưu tiên: Thích Pro nhất, sau đó đến Flash, cuối cùng là bản thường
        priority_list = ['models/gemini-1.5-pro', 'models/gemini-1.5-pro-latest', 'models/gemini-1.5-flash', 'models/gemini-pro']
        
        for best_model in priority_list:
            if best_model in available_models:
                return genai.GenerativeModel(best_model), best_model
                
        # Nếu không có tên nào trong danh sách ưu tiên, tự động bốc con AI đầu tiên trong danh sách cho phép
        return genai.GenerativeModel(available_models[0]), available_models[0]
        
    except Exception as e:
        raise ValueError(f"Lỗi dò tìm: {e}")

# Kích hoạt Radar
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    model, model_name_used = get_auto_ai_model(API_KEY)
except Exception as e:
    st.error(f"🔴 LỖI API KEY: {e}")
    st.stop()

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}

# --- TRẠM 1: VIỆT NAM ---
def get_source_1_vietnam(ticker):
    symbol = ticker.split('.')[0].upper()
    end_time = int(time.time())
    start_time = end_time - (90 * 24 * 60 * 60)
    
    url_hist = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={start_time}&to={end_time}&symbol={symbol}&resolution=1D"
    res = requests.get(url_hist).json()
    if 't' not in res or not res['t']: raise ValueError("Không có biểu đồ VN")
        
    df = pd.DataFrame({
        'date': pd.to_datetime(res['t'], unit='s'),
        'close': res['c'],
        'volume': res['v']
    }).set_index('date')
    current_price = df['close'].iloc[-1] * 1000 
    if current_price < 1000: current_price = df['close'].iloc[-1] 
    
    try:
        url_over = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview"
        res_over = requests.get(url_over, headers=HEADERS, timeout=3).json()
        pe_ratio = res_over.get('pe', 'N/A')
        pb_ratio = res_over.get('pb', 'N/A')
        industry = res_over.get('industry', 'N/A')
    except:
        pe_ratio, pb_ratio, industry = 'N/A', 'N/A', 'N/A'
        
    return df, current_price, pe_ratio, pb_ratio, industry

# --- TRẠM 2: YAHOO QUERY ---
def get_source_2_yahooquery(ticker):
    stock = YQTicker(ticker)
    hist = stock.history(period="3mo")
    if isinstance(hist, dict) or hist.empty: raise ValueError("YQ rỗng")
    
    hist = hist.reset_index().set_index('date')
    current_price = hist['close'].iloc[-1]
    
    try: pe_ratio = stock.summary_detail[ticker].get('trailingPE', 'N/A')
    except: pe_ratio = 'N/A'
    try: pb_ratio = stock.key_stats[ticker].get('priceToBook', 'N/A')
    except: pb_ratio = 'N/A'
    try: industry = stock.asset_profile[ticker].get('industry', 'N/A')
    except: industry = 'N/A'
    
    return hist, current_price, pe_ratio, pb_ratio, industry

# --- GIAO DIỆN CHÍNH ---
ticker_input = st.text_input("Nhập mã cổ phiếu (VD: FPT.VN, VCB.VN hoặc AAPL):", "FPT.VN").upper()

if st.button("Kích Hoạt AI & Quét Dữ Liệu 🚀"):
    st.info(f"🤖 Đang sử dụng Bộ não tự động dò tìm: **{model_name_used}**")
    
    with st.spinner("Đang kết nối hệ thống dữ liệu..."):
        data_success = False
        source_name = ""
        
        if ".VN" in ticker_input:
            try:
                hist, current_price, pe_ratio, pb_ratio, industry = get_source_1_vietnam(ticker_input)
                source_name = "🟢 TRẠM 1: Nội địa Việt Nam"
                data_success = True
            except: pass

        if not data_success:
            try:
                hist, current_price, pe_ratio, pb_ratio, industry = get_source_2_yahooquery(ticker_input)
                source_name = "🟡 TRẠM 2: Quốc tế Yahoo"
                data_success = True
            except:
                st.error("🔴 LỖI: Cổ phiếu không tồn tại. Nhớ thêm đuôi .VN với cổ phiếu Việt Nam!")

        if data_success:
            st.success(f"Kết nối thành công: {source_name}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Giá hiện tại", f"{current_price:,.0f}" if current_price > 1000 else f"{current_price:,.2f}")
            col2.metric("Chỉ số P/B", f"{pb_ratio}")
            col3.metric("Chỉ số P/E", f"{pe_ratio}")
            col4.metric("Ngành", industry)
            
            st.line_chart(hist['close'])
            st.bar_chart(hist['volume']) 
            
            with st.spinner("AI đang thiết lập chiến lược đầu tư..."):
                prompt = f"""
                Mã {ticker_input} (Ngành: {industry}). 
                Giá: {current_price}. P/B: {pb_ratio}. P/E: {pe_ratio}.
                Giá/Khối lượng 10 ngày qua: {hist[['close', 'volume']].tail(10).to_string()}
                
                Nhiệm vụ:
                1. Dòng tiền: Cá mập đang gom hay xả?
                2. Kỹ thuật: Kháng cự, hỗ trợ, xu hướng.
                3. Cơ bản: Nếu P/E hoặc P/B hiện 'N/A' (Do công ty chứng khoán che giấu dữ liệu), hãy BỎ QUA ĐỊNH GIÁ CƠ BẢN và chỉ tập trung vào PTKT. Nếu có số liệu thì so sánh đắt/rẻ.
                4. Khuyến nghị: Mua/Bán/Giữ.
                """
                try:
                    response = model.generate_content(prompt)
                    st.write(response.text)
                except Exception as e:
                    st.error(f"🔴 AI BÁO LỖI LÚC TẠO VĂN BẢN: {e}")
