import streamlit as st
import yfinance as yf
from yahooquery import Ticker as YQTicker
import google.generativeai as genai
import pandas as pd
import requests
import time

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="La Bàn Chứng Khoán PRO", page_icon="📈", layout="wide")
st.title("📈 La Bàn Chứng Khoán PRO: Hệ Thống Bất Tử")
st.markdown("Phiên bản đã vá lỗi máy chủ TCBS và bọc áo giáp thép chống sập API.")

# --- BẢO MẬT API KEY ---
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}

# ==========================================
# TRẠM 1: DỮ LIỆU VIỆT NAM (TCBS) - ĐÃ FIX LỖI 404
# ==========================================
def get_source_1_vietnam(ticker):
    symbol = ticker.replace(".VN", "").replace(".HM", "").replace(".HN", "")
    
    # BÍ QUYẾT FIX LỖI 404: Nhân 1000 để đổi ra mili-giây cho TCBS hiểu
    end_time = int(time.time() * 1000)
    start_time = end_time - (90 * 24 * 60 * 60 * 1000)
    
    url_hist = f"https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term?ticker={symbol}&type=stock&resolution=D&from={start_time}&to={end_time}"
    res = requests.get(url_hist, headers=HEADERS)
    
    if res.status_code != 200: raise ValueError(f"Lỗi {res.status_code}")
        
    data = res.json().get('data', [])
    if not data: raise ValueError("TCBS trả về dữ liệu rỗng")
        
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

# ==========================================
# TRẠM 2: QUỐC TẾ (YAHOO QUERY) - ĐÃ BỌC ÁO GIÁP
# ==========================================
def get_source_2_yahooquery(ticker):
    stock = YQTicker(ticker)
    hist = stock.history(period="3mo")
    if isinstance(hist, dict) or hist.empty: raise ValueError("YQ không tìm thấy")
    
    hist = hist.reset_index().set_index('date')
    current_price = hist['close'].iloc[-1]
    
    # Bọc Try-Except từng cái một để không bao giờ bị sập
    try: pe_ratio = stock.summary_detail[ticker].get('trailingPE', 'N/A')
    except: pe_ratio = 'N/A'
    
    try: pb_ratio = stock.key_stats[ticker].get('priceToBook', 'N/A')
    except: pb_ratio = 'N/A'
    
    try: industry = stock.asset_profile[ticker].get('industry', 'N/A')
    except: industry = 'N/A'
    
    return hist, current_price, pe_ratio, pb_ratio, industry

# ==========================================
# TRẠM 3: DỰ PHÒNG YFINANCE
# ==========================================
def get_source_3_yfinance(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="3mo")
    if hist.empty: raise ValueError("YF không tìm thấy")
    
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
    with st.spinner("Hệ thống radar đang quét các trạm..."):
        data_success = False
        error_logs = []
        source_name = ""
        
        try:
            hist, current_price, pe_ratio, pb_ratio, industry = get_source_1_vietnam(ticker_input)
            source_name = "🟢 TRẠM 1: Máy chủ Việt Nam (TCBS) - Cực Nhanh"
            data_success = True
        except Exception as e1:
            error_logs.append(f"Trạm 1: {e1}")
            try:
                hist, current_price, pe_ratio, pb_ratio, industry = get_source_2_yahooquery(ticker_input)
                source_name = "🟡 TRẠM 2: YahooQuery Quốc tế"
                data_success = True
            except Exception as e2:
                error_logs.append(f"Trạm 2: {e2}")
                try:
                    hist, current_price, pe_ratio, pb_ratio, industry = get_source_3_yfinance(ticker_input)
                    source_name = "🟠 TRẠM 3: YFinance Backup"
                    data_success = True
                except Exception as e3:
                    error_logs.append(f"Trạm 3: {e3}")
                    data_success = False

        if not data_success:
            st.error("🔴 KHÔNG THỂ LẤY DỮ LIỆU. Chi tiết lỗi:")
            for err in error_logs: st.warning(err)
        else:
            st.success(f"Kết nối thành công: {source_name}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Giá hiện tại", f"{current_price:,.0f}" if current_price > 1000 else f"{current_price:,.2f}")
            col2.metric("Chỉ số P/B", f"{pb_ratio}")
            col3.metric("Chỉ số P/E", f"{pe_ratio}")
            col4.metric("Ngành", industry)
            
            st.markdown("**Biểu đồ Giá**")
            st.line_chart(hist['close'])
            st.markdown("**Biểu đồ Dòng tiền (Volume)**")
            st.bar_chart(hist['volume']) 
            
            with st.spinner("Bộ não AI Gemini đang tổng hợp báo cáo..."):
                prompt = f"""
                Bạn là Giám đốc phân tích Đầu tư. Phân tích mã {ticker_input} (Ngành: {industry}):
                - Giá: {current_price}, P/B: {pb_ratio}, P/E: {pe_ratio}
                - Dữ liệu giá/khối lượng: {hist[['close', 'volume']].tail(10).to_string()}
                
                Viết báo cáo 4 phần:
                1. Dòng tiền (Gom hàng/Xả hàng?).
                2. Kỹ thuật (Xu hướng, Hỗ trợ/Kháng cự).
                3. Cơ bản (Định giá đắt hay rẻ?).
                4. Khuyến nghị (Mua/Bán/Giữ).
                """
                try:
                    response = model.generate_content(prompt)
                    st.write(response.text)
                except Exception as e:
                    st.error("Lỗi AI: Vui lòng kiểm tra lại API Key.")
