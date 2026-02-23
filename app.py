import streamlit as st
import yfinance as yf
from yahooquery import Ticker as YQTicker
import google.generativeai as genai
import pandas as pd
import requests
import time

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="La Bàn Chứng Khoán PRO", page_icon="📈", layout="wide")
st.title("📈 La Bàn Chứng Khoán PRO: Hệ Thống 3 Lớp")
st.markdown("Tích hợp dữ liệu Nội địa (VN) và Quốc tế với tính năng Tự phục hồi lỗi.")

# --- BẢO MẬT API KEY ---
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
}

# ==========================================
# TRẠM 1: DỮ LIỆU VIỆT NAM (TCBS)
# ==========================================
def get_source_1_vietnam(ticker):
    symbol = ticker.replace(".VN", "").replace(".HM", "").replace(".HN", "")
    end_time = int(time.time())
    start_time = end_time - (90 * 24 * 60 * 60)
    
    url_hist = f"https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term?ticker={symbol}&type=stock&resolution=D&from={start_time}&to={end_time}"
    res = requests.get(url_hist, headers=HEADERS)
    
    if res.status_code != 200:
        raise ValueError(f"Lỗi {res.status_code}")
        
    res_hist = res.json()
    if 'data' not in res_hist or not res_hist['data']:
        raise ValueError("Dữ liệu rỗng")
        
    df = pd.DataFrame(res_hist['data'])
    df['date'] = pd.to_datetime(df['tradingDate'])
    df = df.set_index('date')
    current_price = df['close'].iloc[-1]
    
    # Bọc lỗi riêng cho phần chỉ số cơ bản
    try:
        url_over = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview"
        res_over = requests.get(url_over, headers=HEADERS).json()
        pe_ratio = res_over.get('pe', 'Không có')
        pb_ratio = res_over.get('pb', 'Không có')
        industry = res_over.get('industry', 'Không xác định')
    except:
        pe_ratio, pb_ratio, industry = 'Không có', 'Không có', 'Không xác định'
    
    return df, current_price, pe_ratio, pb_ratio, industry

# ==========================================
# TRẠM 2: QUỐC TẾ (YAHOO QUERY)
# ==========================================
def get_source_2_yahooquery(ticker):
    stock = YQTicker(ticker)
    hist = stock.history(period="3mo")
    if isinstance(hist, dict) or hist.empty:
        raise ValueError("YahooQuery không tìm thấy mã này")
    
    hist = hist.reset_index().set_index('date')
    current_price = hist['close'].iloc[-1]
    
    # Sửa lỗi string dictionary
    detail = stock.summary_detail
    if isinstance(detail, dict) and isinstance(detail.get(ticker), dict):
        pe_ratio = detail[ticker].get('trailingPE', 'Không có')
    else:
        pe_ratio = 'Không có'
        
    stats = stock.default_key_statistics
    if isinstance(stats, dict) and isinstance(stats.get(ticker), dict):
        pb_ratio = stats[ticker].get('priceToBook', 'Không có')
    else:
        pb_ratio = 'Không có'
        
    profile = stock.asset_profile
    if isinstance(profile, dict) and isinstance(profile.get(ticker), dict):
        industry = profile[ticker].get('industry', 'Không xác định')
    else:
        industry = 'Không xác định'
    
    return hist, current_price, pe_ratio, pb_ratio, industry

# ==========================================
# TRẠM 3: DỰ PHÒNG CỨNG (YFINANCE)
# ==========================================
def get_source_3_yfinance(ticker):
    # CHÍNH THỨC SỬA LỖI YFINANCE: Không ép mặt nạ nữa, để YF tự dùng công nghệ của nó
    stock = yf.Ticker(ticker)
    hist = stock.history(period="3mo")
    if hist.empty:
        raise ValueError("YFinance không tìm thấy mã này")
    
    current_price = hist['Close'].iloc[-1]
    hist.columns = [c.lower() for c in hist.columns] 
    
    info = stock.info
    pe_ratio = info.get('trailingPE', 'Không có')
    pb_ratio = info.get('priceToBook', 'Không có')
    industry = info.get('industry', 'Không xác định')
    
    return hist, current_price, pe_ratio, pb_ratio, industry

# --- GIAO DIỆN CHÍNH ---
ticker_input = st.text_input("Nhập mã cổ phiếu (VD: FPT.VN, VCB.VN hoặc cổ phiếu Mỹ AAPL, TSLA):", "FPT.VN").upper()

if st.button("Kích Hoạt AI & Quét Dữ Liệu 🚀"):
    with st.spinner(f"Radar đang dò tìm các trạm dữ liệu cho {ticker_input}..."):
        
        data_success = False
        source_name = ""
        error_logs = []
        
        try:
            hist, current_price, pe_ratio, pb_ratio, industry = get_source_1_vietnam(ticker_input)
            source_name = "🟢 TRẠM 1: Máy chủ Việt Nam (TCBS)"
            data_success = True
        except Exception as e1:
            error_logs.append(f"Trạm 1 (VN): {e1}")
            try:
                hist, current_price, pe_ratio, pb_ratio, industry = get_source_2_yahooquery(ticker_input)
                source_name = "🟡 TRẠM 2: YahooQuery"
                data_success = True
            except Exception as e2:
                error_logs.append(f"Trạm 2 (YQ): {e2}")
                try:
                    hist, current_price, pe_ratio, pb_ratio, industry = get_source_3_yfinance(ticker_input)
                    source_name = "🟠 TRẠM 3: YFinance Backup"
                    data_success = True
                except Exception as e3:
                    error_logs.append(f"Trạm 3 (YF): {e3}")
                    data_success = False

        if not data_success:
            st.error("🔴 KHÔNG THỂ LẤY DỮ LIỆU. Chi tiết lỗi từ các trạm:")
            for err in error_logs:
                st.warning(err)
            st.info("💡 Bạn nhớ gõ thêm đuôi .VN với cổ phiếu Việt Nam nhé (Ví dụ: FPT.VN, HPG.VN)")

        else:
            st.success(f"Kết nối thành công: {source_name}")
            
            st.subheader(f"Tổng quan chỉ số {ticker_input}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Giá hiện tại", f"{current_price:,.0f}" if current_price > 1000 else f"{current_price:,.2f}")
            col2.metric("Chỉ số P/B", f"{pb_ratio}")
            col3.metric("Chỉ số P/E", f"{pe_ratio}")
            col4.metric("Ngành", industry)
            
            st.markdown("**Biểu đồ Giá (Close)**")
            st.line_chart(hist['close'])
            st.markdown("**Biểu đồ Dòng tiền (Volume)**")
            st.bar_chart(hist['volume']) 
            
            with st.spinner("AI đang tính toán chiến lược..."):
                prompt = f"""
                Bạn là Giám đốc phân tích Đầu tư. Phân tích mã {ticker_input} (Ngành: {industry}):
                - Giá hiện tại: {current_price}, P/B: {pb_ratio}, P/E: {pe_ratio}
                - Dữ liệu giá/khối lượng: {hist[['close', 'volume']].tail(15).to_string()}
                
                Viết báo cáo gồm 4 phần chuyên nghiệp, súc tích:
                1. Dòng tiền (Nhận diện Cá mập).
                2. Kỹ thuật (Xu hướng, Hỗ trợ/Kháng cự).
                3. Cơ bản (Định giá đắt/rẻ).
                4. Khuyến nghị (Mua/Bán/Giữ).
                """
                try:
                    response = model.generate_content(prompt)
                    st.write(response.text)
                except Exception as e:
                    st.error(f"Lỗi kết nối AI: {e}")
