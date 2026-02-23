import streamlit as st
import yfinance as yf
import google.generativeai as genai

st.set_page_config(page_title="La Bàn Chứng Khoán PRO", page_icon="📈", layout="wide")
st.title("📈 La Bàn Chứng Khoán PRO: AI Phân Tích Toàn Diện")
st.markdown("Hệ thống kết hợp Phân tích Kỹ thuật, Dòng tiền và Định giá Cơ bản.")

API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

ticker_input = st.text_input("Nhập mã cổ phiếu (VD: AAPL, VCB.VN, FPT.VN):", "FPT.VN").upper()

if st.button("Kích Hoạt AI Phân Tích Chuyên Sâu 🚀"):
    with st.spinner(f"Đang thu thập dữ liệu vĩ mô và vi mô cho {ticker_input}..."):
        stock = yf.Ticker(ticker_input)
        
        # Lấy dữ liệu lịch sử và cơ bản
        hist = stock.history(period="3mo")
        info = stock.info
        
        if hist.empty:
            st.error("Không tìm thấy dữ liệu. Thử thêm đuôi .VN với cổ phiếu Việt Nam (VD: HPG.VN).")
        else:
            # Trích xuất các chỉ số quan trọng
            current_price = hist['Close'].iloc[-1]
            book_value = info.get('bookValue', 'Không có dữ liệu')
            pe_ratio = info.get('trailingPE', 'Không có dữ liệu')
            industry = info.get('industry', 'Không xác định')
            
            st.subheader(f"Tổng quan chỉ số {ticker_input}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Giá hiện tại", f"{current_price:,.2f}")
            col2.metric("Giá trị sổ sách (BV)", book_value)
            col3.metric("P/E", pe_ratio)
            col4.metric("Ngành", industry)
            
            st.line_chart(hist['Close'])
            st.bar_chart(hist['Volume']) # Biểu đồ dòng tiền
            
            with st.spinner("AI đang tổng hợp và đưa ra định giá..."):
                prompt = f"""
                Bạn là một chuyên gia chứng khoán cấp cao. Hãy phân tích mã {ticker_input} thuộc ngành {industry} dựa trên các dữ liệu sau:
                - Giá hiện tại: {current_price}
                - Giá trị sổ sách (Book Value): {book_value}
                - Chỉ số P/E: {pe_ratio}
                - Dữ liệu giá và khối lượng (dòng tiền) 3 tháng qua: {hist[['Close', 'Volume']].tail(15).to_string()}
                
                Yêu cầu báo cáo gồm 4 phần rõ ràng:
                1. Phân tích Dòng tiền: Nhận xét sự ra/vào của dòng tiền lớn dựa trên khối lượng (Volume) gần đây.
                2. Phân tích Kỹ thuật: Xu hướng chính, điểm hỗ trợ/kháng cự.
                3. Định giá Cơ bản: Đánh giá giá hiện tại so với Giá trị sổ sách và P/E ngành. Cổ phiếu đang đắt hay rẻ?
                4. Khuyến nghị hành động: Mua/Bán/Giữ kèm lý do cốt lõi.
                """
                response = model.generate_content(prompt)
                
                st.success("Báo cáo đã sẵn sàng!")
                st.write(response.text)
