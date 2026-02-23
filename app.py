import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import requests # Thêm thư viện để tạo mặt nạ

# Cấu hình giao diện Web
st.set_page_config(page_title="La Bàn Chứng Khoán PRO", page_icon="📈", layout="wide")
st.title("📈 La Bàn Chứng Khoán PRO: AI Phân Tích Toàn Diện")
st.markdown("Hệ thống phân tích Dòng tiền, Kỹ thuật, Định giá Cơ bản và Vĩ mô thị trường.")

# Kết nối API bảo mật
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

# Giao diện nhập liệu
ticker_input = st.text_input("Nhập mã cổ phiếu (VD: FPT.VN, VCB.VN, HPG.VN hoặc AAPL):", "FPT.VN").upper()

if st.button("Kích Hoạt AI Phân Tích Chuyên Sâu 🚀"):
    with st.spinner(f"Đang thu thập dữ liệu đa chiều cho {ticker_input}..."):
        try:
            # --- TẠO MẶT NẠ NGƯỜI DÙNG ĐỂ VƯỢT RÀO YAHOO FINANCE ---
            session = requests.Session()
            session.headers['User-agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            
            # Khởi tạo dữ liệu với mặt nạ
            stock = yf.Ticker(ticker_input, session=session)
            hist = stock.history(period="3mo")
            
            if hist.empty:
                st.error("Không tìm thấy dữ liệu. Thử thêm đuôi .VN với cổ phiếu Việt Nam (VD: HPG.VN).")
            else:
                # Trích xuất các chỉ số quan trọng (có bẫy lỗi nếu Yahoo thiếu dữ liệu)
                current_price = hist['Close'].iloc[-1]
                try:
                    info = stock.info
                    book_value = info.get('bookValue', 'Chưa có dữ liệu')
                    pe_ratio = info.get('trailingPE', 'Chưa có dữ liệu')
                    industry = info.get('industry', 'Chưa xác định')
                except:
                    book_value = 'Chưa có dữ liệu'
                    pe_ratio = 'Chưa có dữ liệu'
                    industry = 'Chưa xác định'
                
                st.subheader(f"Tổng quan chỉ số {ticker_input}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Giá hiện tại", f"{current_price:,.2f}")
                col2.metric("Giá trị sổ sách (BV)", book_value)
                col3.metric("P/E", pe_ratio)
                col4.metric("Ngành", industry)
                
                st.markdown("**Biểu đồ Giá (Close)**")
                st.line_chart(hist['Close'])
                st.markdown("**Biểu đồ Dòng tiền (Volume)**")
                st.bar_chart(hist['Volume']) 
                
                with st.spinner("AI đang tổng hợp và đưa ra báo cáo..."):
                    prompt = f"""
                    Bạn là một chuyên gia chứng khoán. Hãy phân tích mã {ticker_input} thuộc ngành {industry} dựa trên:
                    - Giá hiện tại: {current_price}
                    - Giá trị sổ sách: {book_value}, P/E: {pe_ratio}
                    - Dữ liệu giá/khối lượng 3 tháng qua: {hist[['Close', 'Volume']].tail(15).to_string()}
                    
                    Báo cáo 4 phần ngắn gọn:
                    1. Phân tích Dòng tiền.
                    2. Phân tích Kỹ thuật (Xu hướng, Hỗ trợ/Kháng cự).
                    3. Định giá Cơ bản.
                    4. Khuyến nghị: Mua/Bán/Giữ.
                    """
                    try:
                        response = model.generate_content(prompt)
                        st.success("Báo cáo đã sẵn sàng!")
                        st.write(response.text)
                    except Exception as e:
                        st.error("Lỗi kết nối AI: Hãy kiểm tra lại API Key.")
        except Exception as e:
            st.warning("Yahoo Finance đang quá tải hoặc tạm thời chặn kết nối. Xin vui lòng đợi khoảng 5-10 phút rồi bấm thử lại!")
