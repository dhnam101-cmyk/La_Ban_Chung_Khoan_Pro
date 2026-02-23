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
st.markdown("Hệ thống Đa Nguồn kết hợp Định giá và Phân tích Kỹ thuật.")

# --- KẾT NỐI AI ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
    # Đã cập nhật đúng tên bộ não AI ổn định và thông minh nhất hiện tại của Google
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error("Chưa tìm thấy API Key trong mục Secrets của Streamlit!")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}

# --- TRẠM 1: CHUYÊN DỤNG CHO CỔ PHIẾU VIỆT NAM ---
def get_source_1_vietnam(ticker):
    # Lọc đuôi .VN
    symbol = ticker.split('.')[0].upper()
    end_time = int(time.time())
    start_time = end_time - (90 * 24 * 60 * 60)
    
    # Lấy biểu đồ từ DNSE (Siêu ổn định)
    url_hist = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from={start_time}&to={end_time}&symbol={symbol}&resolution=1D"
    res = requests.get(url_hist).json()
    if 't' not in res or not res['t']: raise ValueError("Không có biểu đồ VN")
        
    df = pd.DataFrame({
        'date': pd.to_datetime(res['t'], unit='s'),
        'close': res['c'],
        'volume': res['v']
    }).set_index('date')
    current_price = df['close'].iloc[-1] * 1000 # Đổi về giá thực tế (VD: 94.3 -> 94300)
    if current_price < 1000: current_price = df['close'].iloc[-1] # Dành cho mã vốn đã chuẩn giá
    
    # Lấy P/E, P/B từ TCBS
    try:
        url_over = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{symbol}/overview"
        res_over = requests.get(url_over, headers=HEADERS, timeout=5).json()
        pe_ratio = res_over.get('pe', 'N/A')
        pb_ratio = res_over.get('pb', 'N/A')
        industry = res_over.get('industry', 'N/A')
    except:
        pe_ratio, pb_ratio, industry = 'N/A', 'N/A', 'N/A'
        
    return df, current_price, pe_ratio, pb_ratio, industry

# --- TRẠM 2: QUỐC TẾ (YAHOO QUERY) ---
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
ticker_input = st.text_input("Nhập mã cổ phiếu (VD: FPT.VN, VCB.VN hoặc cổ phiếu Mỹ AAPL):", "FPT.VN").upper()

if st.button("Kích Hoạt AI & Quét Dữ Liệu 🚀"):
    with st.spinner("Đang kết nối hệ thống dữ liệu..."):
        data_success = False
        source_name = ""
        
        # Nếu là mã Việt Nam (có chữ .VN) thì ưu tiên vào thẳng Trạm 1
        if ".VN" in ticker_input:
            try:
                hist, current_price, pe_ratio, pb_ratio, industry = get_source_1_vietnam(ticker_input)
                source_name = "🟢 TRẠM 1: Máy chủ Nội địa Việt Nam"
                data_success = True
            except:
                pass # Bỏ qua để chạy xuống dự phòng

        # Nếu không phải mã VN, hoặc Trạm 1 lỗi, dùng Yahoo
        if not data_success:
            try:
                hist, current_price, pe_ratio, pb_ratio, industry = get_source_2_yahooquery(ticker_input)
                source_name = "🟡 TRẠM 2: Máy chủ Quốc tế Yahoo"
                data_success = True
            except Exception as e:
                st.error("🔴 LỖI: Không lấy được dữ liệu. Vui lòng kiểm tra lại mã cổ phiếu (Cổ phiếu VN phải thêm đuôi .VN, VD: FPT.VN)")

        if data_success:
            st.success(f"Kết nối thành công: {source_name}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Giá hiện tại", f"{current_price:,.0f}" if current_price > 1000 else f"{current_price:,.2f}")
            col2.metric("Chỉ số P/B", f"{pb_ratio}")
            col3.metric("Chỉ số P/E", f"{pe_ratio}")
            col4.metric("Ngành", industry)
            
            st.line_chart(hist['close'])
            st.bar_chart(hist['volume']) 
            
            with st.spinner("AI đang soạn thảo báo cáo. Vui lòng đợi trong giây lát..."):
                prompt = f"""
                Bạn là một Giám đốc phân tích Đầu tư Chứng khoán. Hãy phân tích mã {ticker_input} (Ngành: {industry}):
                - Giá hiện tại: {current_price}, P/B: {pb_ratio}, P/E: {pe_ratio}
                - Dữ liệu giá/khối lượng 10 ngày qua: {hist[['close', 'volume']].tail(10).to_string()}
                
                Hãy viết báo cáo theo 4 phần:
                1. Dòng tiền: Đang gom hàng hay xả hàng?
                2. Kỹ thuật: Xu hướng chính, hỗ trợ/kháng cự.
                3. Định giá: Nếu P/E hoặc P/B là 'N/A', hãy bỏ qua định giá cơ bản và tập trung dự phóng xu hướng. Nếu có số liệu, hãy nhận xét đắt/rẻ.
                4. Khuyến nghị: Mua/Bán/Giữ kèm lý do ngắn gọn.
                """
                try:
                    response = model.generate_content(prompt)
                    st.write(response.text)
                except Exception as e:
                    st.error(f"🔴 AI BÁO LỖI: {e}")
                    st.info("Hãy kiểm tra lại API Key xem đã chính xác chưa nhé!")
