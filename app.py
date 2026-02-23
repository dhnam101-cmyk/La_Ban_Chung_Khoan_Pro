import streamlit as st
import yfinance as yf
from yahooquery import Ticker as YQTicker
import google.generativeai as genai
import pandas as pd
import requests
import time

# --- CẤU HÌNH ---
st.set_page_config(page_title="La Bàn Chứng Khoán PRO", page_icon="📈", layout="wide")
st.title("📈 La Bàn Chứng Khoán PRO: AI Phân Tích Toàn Diện")
st.markdown("Hệ thống Đa Nguồn kết hợp Tự động cập nhật Bộ não AI.")

# --- KẾT NỐI AI (TỰ ĐỘNG DÒ TÌM MODEL MỚI NHẤT) ---
@st.cache_resource(show_spinner="Đang khởi động radar quét hệ thống AI của Google...")
def get_best_ai_model(api_key):
    genai.configure(api_key=api_key)
    # Tự động xin danh sách các bộ não hiện có từ Google
    try:
        for m in genai.list_models():
            # Tìm bộ não thuộc dòng 1.5-pro và có hỗ trợ tạo nội dung
            if 'generateContent' in m.supported_generation_methods and 'gemini-1.5-pro' in m.name:
                return genai.GenerativeModel(m.name)
    except Exception as e:
        pass
    # Trở về phương án dự phòng an toàn nhất nếu lỗi quét
    return genai.GenerativeModel('gemini-1.5-pro-latest')

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    model = get_best_ai_model(API_KEY)
except Exception as e:
    st.error("🔴 Chưa tìm thấy API Key hoặc API Key bị sai. Vui lòng dán lại vào mục Secrets!")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}

# --- TRẠM 1: VIỆT NAM ---
def get_source_1_vietnam(ticker):
    symbol = ticker.replace(".VN", "").replace(".HM", "").replace(".HN", "")
    end_time = int(time.time() * 1000)
    start_time = end_time - (90 * 24 * 60 * 60 * 1000)
    
    url_hist = f"https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term?ticker={symbol}&type=stock&resolution=D&from={start_time}&to={end_time}"
    res = requests.get(url_hist, headers=HEADERS)
    if res.status_code != 200: raise ValueError("Lỗi API VN")
        
    data = res.json().get('data', [])
    if not data: raise ValueError("Dữ liệu rỗng")
        
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['tradingDate'])
    df = df.set_index('date')
    current_price = df['close'].iloc[-1]
    
    try:
        url_over = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview"
        res_over = requests.get(url_over, headers=HEADERS).json()
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

# --- TRẠM 3: YFINANCE ---
def get_source_3_yfinance(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="3mo")
    if hist.empty: raise ValueError("YF rỗng")
    
    current_price = hist['Close'].iloc[-1]
    hist.columns = [c.lower() for c in hist.columns] 
    try:
        pe_ratio = stock.info.get('trailingPE', 'N/A')
        pb_ratio = stock.info.get('priceToBook', 'N/A')
        industry = stock.info.get('industry', 'N/A')
    except:
        pe_ratio, pb_ratio, industry = 'N/A', 'N/A', 'N/A'
    return hist, current_price, pe_ratio, pb_ratio, industry

# --- GIAO DIỆN CHÍNH ---
ticker_input = st.text_input("Nhập mã cổ phiếu (VD: FPT.VN, VCB.VN hoặc AAPL):", "FPT.VN").upper()

if st.button("Kích Hoạt AI & Quét Dữ Liệu 🚀"):
    with st.spinner("Hệ thống radar đang quét..."):
        data_success = False
        source_name = ""
        
        try:
            hist, current_price, pe_ratio, pb_ratio, industry = get_source_1_vietnam(ticker_input)
            source_name = "🟢 TRẠM 1: Việt Nam (TCBS)"
            data_success = True
        except:
            try:
                hist, current_price, pe_ratio, pb_ratio, industry = get_source_2_yahooquery(ticker_input)
                source_name = "🟡 TRẠM 2: YahooQuery"
                data_success = True
            except:
                try:
                    hist, current_price, pe_ratio, pb_ratio, industry = get_source_3_yfinance(ticker_input)
                    source_name = "🟠 TRẠM 3: YFinance"
                    data_success = True
                except:
                    st.error("🔴 KHÔNG THỂ LẤY DỮ LIỆU. Bạn nhớ thêm đuôi .VN (VD: FPT.VN)")

        if data_success:
            st.success(f"Kết nối thành công: {source_name}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Giá hiện tại", f"{current_price:,.0f}" if current_price > 1000 else f"{current_price:,.2f}")
            col2.metric("Chỉ số P/B", f"{pb_ratio}")
            col3.metric("Chỉ số P/E", f"{pe_ratio}")
            col4.metric("Ngành", industry)
            
            st.line_chart(hist['close'])
            st.bar_chart(hist['volume']) 
            
            with st.spinner("Bộ não AI đang tổng hợp và phân tích..."):
                prompt = f"""
                Bạn là Giám đốc phân tích Đầu tư. Phân tích mã {ticker_input} (Thuộc ngành: {industry}):
                - Giá: {current_price}, P/B: {pb_ratio}, P/E: {pe_ratio}
                - Lịch sử giá/khối lượng: {hist[['close', 'volume']].tail(10).to_string()}
                
                Viết báo cáo 4 phần:
                1. Dòng tiền (Gom hàng hay Xả hàng?).
                2. Kỹ thuật (Xu hướng, Hỗ trợ/Kháng cự).
                3. ĐỊNH GIÁ & SO SÁNH NGÀNH: Phân tích P/E và P/B. Cổ phiếu này đang đắt hay rẻ so với mặt bằng chung ngành {industry}?
                4. Khuyến nghị (Mua/Bán/Giữ).
                """
                try:
                    response = model.generate_content(prompt)
                    st.write(response.text)
                except Exception as e:
                    st.error(f"🔴 AI TỪ CHỐI KẾT NỐI. Mã lỗi: {e}")
