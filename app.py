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
st.markdown("Tích hợp dữ liệu Nội địa (VN) và Quốc tế với tính năng Tàng hình (Anti-Bot).")

# --- BẢO MẬT API KEY ---
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

# --- MẶT NẠ TÀNG HÌNH (FAKE BROWSER HEADERS) ---
# Đánh lừa máy chủ tưởng đây là người thật đang dùng Google Chrome
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
}

# ==========================================
# TRẠM 1: DỮ LIỆU VIỆT NAM (TCBS)
# ==========================================
def get_source_1_vietnam(ticker):
    symbol = ticker.replace(".VN", "").replace(".HM", "").replace(".HN", "")
    end_time = int(time.time())
    start_time = end_time - (90 * 24 * 60 * 60)
    
    # Lấy lịch sử giá
    url_hist = f"https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term?ticker={symbol}&type=stock&resolution=D&from={start_time}&to={end_time}"
    res = requests.get(url_hist, headers=HEADERS)
    
    if res.status_code != 200:
        raise ValueError(f"Máy chủ TCBS chặn kết nối (Lỗi {res.status_code})")
        
    res_hist = res.json()
    if 'data' not in res_hist or not res_hist['data']:
        raise ValueError("TCBS trả về dữ liệu trống")
        
    df = pd.DataFrame(res_hist['data'])
    df['date'] = pd.to_datetime(df['tradingDate'])
    df = df.set_index('date')
    current_price = df['close'].iloc[-1]
    
    # Lấy chỉ số cơ bản
    url_over = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview"
    res_over = requests.get(url_over, headers=HEADERS).json()
    
    pe_ratio = res_over.get('pe', 'Không có')
    pb_ratio = res_over.get('pb', 'Không có')
    industry = res_over.get('industry', 'Không xác định')
    
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
    
    pe_ratio = stock.summary_detail.get(ticker, {}).get('trailingPE', 'Không có') if isinstance(stock.summary_detail, dict) else 'Không có'
    pb_ratio = stock.default_key_statistics.get(ticker, {}).get('priceToBook', 'Không có') if isinstance(stock.default_key_statistics, dict) else 'Không có'
    industry = stock.asset_profile.get(ticker, {}).get('industry', 'Không xác định') if isinstance(stock.asset_profile, dict) else 'Không xác định'
    
    return hist, current_price, pe_ratio, pb_ratio, industry

# ==========================================
# TRẠM 3: DỰ PHÒNG CỨNG (YFINANCE)
# ==========================================
def get_source_3_yfinance(ticker):
    session = requests.Session()
    session.headers.update(HEADERS)
    stock = yf.Ticker(ticker, session=session)
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
    with st.spinner(f"Đang sử dụng Mặt nạ tàng hình để lấy dữ liệu cho {ticker_input}..."):
        
        data_success = False
        source_name = ""
        error_logs = [] # Bộ nhớ lưu lại nguyên nhân lỗi để báo cáo
        
        # Thử Trạm 1
        try:
            hist, current_price, pe_ratio, pb_ratio, industry = get_source_1_vietnam(ticker_input)
            source_name = "🟢 TRẠM 1: Máy chủ Việt Nam (TCBS)"
            data_success = True
        except Exception as e1:
            error_logs.append(f"Trạm 1 (VN): {e1}")
            # Thử Trạm 2
            try:
                hist, current_price, pe_ratio, pb_ratio, industry = get_source_2_yahooquery(ticker_input)
                source_name = "🟡 TRẠM 2: YahooQuery"
                data_success = True
            except Exception as e2:
                error_logs.append(f"Trạm 2 (YQ): {e2}")
                # Thử Trạm 3
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
            st.info("💡 Lời khuyên: Đợi 1-2 phút rồi bấm lại, hoặc đảm bảo bạn gõ đúng tên mã (Ví dụ mã VN phải có đuôi .VN như FPT.VN)")

        else:
            st.success(f"Radar kết nối thành công: {source_name}")
            
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
            
            with st.spinner("AI đang giải mã tín hiệu mua/bán từ các con số..."):
                prompt = f"""
                Bạn là Giám đốc phân tích Đầu tư. Phân tích mã {ticker_input} (Ngành: {industry}):
                - Giá hiện tại: {current_price}, P/B (Giá/Sổ sách): {pb_ratio}, P/E: {pe_ratio}
                - Dữ liệu giá/khối lượng: {hist[['close', 'volume']].tail(15).to_string()}
                
                Viết báo cáo gồm 4 phần chuyên nghiệp, súc tích:
                1. Dòng tiền: Phân tích khối lượng, có dấu hiệu gom hàng hay xả hàng của cá mập không?
                2. Kỹ thuật: Xu hướng chính, điểm hỗ trợ/kháng cự.
                3. Cơ bản: Định giá P/B và P/E hiện tại là đắt hay rẻ so với tiềm năng?
                4. Khuyến nghị: Mua/Bán/Giữ và chiến lược giao dịch rõ ràng.
                """
                try:
                    response = model.generate_content(prompt)
                    st.write(response.text)
                except Exception as e:
                    st.error(f"Lỗi kết nối AI: {e}")
