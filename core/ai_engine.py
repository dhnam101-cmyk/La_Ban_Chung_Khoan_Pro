import streamlit as st
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

# ==========================================
# 1. CẤU HÌNH KẾT NỐI GEMINI
# ==========================================
def setup_gemini(model_name):
    if "GOOGLE_API_KEY" not in st.secrets:
        raise ValueError("LỖI_THIẾU_KEY")
    
    # Lấy chìa khóa từ Secrets của Streamlit
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)

# ==========================================
# 2. CƠ CHẾ GỌI AI CHÍNH (CÓ TỰ ĐỘNG THỬ LẠI KHI MẠNG LAG)
# ==========================================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def ask_ai_primary(ticker, language, model_name, context=""):
    model = setup_gemini(model_name)

    # System Prompt chuyên gia tài chính (Đã giữ nguyên bản xịn của bạn)
    base_prompt = f"""
    Bạn là một Giám đốc Phân tích Chiến lược tại một quỹ đầu tư lớn.
    Hãy phân tích mã cổ phiếu: {ticker}
    Ngôn ngữ trả lời: {language}
    Model đang sử dụng: {model_name}
    
    YÊU CẦU PHÂN TÍCH:
    1. **Định giá:** Dựa vào chỉ số P/E và P/B, hãy đánh giá mã này đang Đắt hay Rẻ so với trung bình ngành.
    2. **Dòng tiền & Kỹ thuật:** Nhận định về biến động khối lượng (Volume) và các ngưỡng hỗ trợ/kháng cự.
    3. **Vĩ mô:** Những yếu tố vĩ mô hiện tại ảnh hưởng thế nào đến doanh nghiệp này?
    4. **Khuyến nghị:** Hành động cụ thể (Mua/Bán/Theo dõi) và giá mục tiêu dự kiến.

    PHONG CÁCH: Chuyên nghiệp, súc tích, trình bày Markdown đẹp mắt với các icon.
    """
    
    # Nối thêm câu hỏi của người dùng nếu có (từ Chat/Mic)
    final_prompt = f"{base_prompt}\n\nNgười dùng hỏi thêm: {context}" if context else base_prompt
    
    response = model.generate_content(final_prompt)
    return f"**[🤖 CHUYÊN GIA AI - {model_name.upper()}]**\n\n{response.text}"

# ==========================================
# 3. TRUNG TÂM ĐIỀU PHỐI & BÁO LỖI THÔNG MINH
# ==========================================
def get_ai_analysis(ticker, language="Tiếng Việt", model_name="gemini-1.5-flash", context=""):
    try:
        return ask_ai_primary(ticker, language, model_name, context)
    except Exception as e:
        error_msg = str(e)
        
        # Phân loại lỗi để báo đúng bệnh cho người dùng
        if "LỖI_THIẾU_KEY" in error_msg:
            return "❌ **LỖI:** Chưa cài đặt GOOGLE_API_KEY trong phần Settings > Secrets của Streamlit."
        elif "429" in error_msg or "Rate limited" in error_msg or "Too Many Requests" in error_msg:
            return f"⏳ **Google báo API đang quá tải (Rate Limit).**\n\nBạn đang dùng bản miễn phí nên bị giới hạn số lần hỏi liên tục. Vui lòng đợi khoảng 1 phút rồi nhấn nút Phân tích lại nhé!"
        elif "API_KEY_INVALID" in error_msg:
            return "❌ **Lỗi API Key không hợp lệ.** Vui lòng kiểm tra lại xem copy key có bị dư dấu cách không."
        else:
            return f"⚠️ **Lỗi kết nối AI:** {error_msg}\n\n*Hệ thống đang tự động theo dõi mã {ticker}.*"
