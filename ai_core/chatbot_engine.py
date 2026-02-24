import streamlit as st
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

# ==========================================
# CẤU HÌNH KẾT NỐI GEMINI
# ==========================================
def setup_gemini(model_name):
    try:
        # Lấy chìa khóa từ "két sắt" Secrets của Streamlit
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)
        # Khởi tạo model dựa trên lựa chọn của người dùng
        model = genai.GenerativeModel(model_name)
        return model
    except Exception as e:
        st.error(f"Lỗi cấu hình API Gemini: {e}")
        return None

# ==========================================
# CƠ CHẾ 1: GỌI MODEL AI CHÍNH (LINH HOẠT MODEL)
# ==========================================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def ask_ai_primary(ticker, language, model_name):
    model = setup_gemini(model_name)
    if not model:
        raise Exception("Không thể kết nối Gemini")

    # System Prompt chuyên gia tài chính
    prompt = f"""
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
    
    response = model.generate_content(prompt)
    return f"**[🤖 CHUYÊN GIA AI - {model_name.upper()}]**\n\n{response.text}"

# ==========================================
# CƠ CHẾ 2 & 3: DỰ PHÒNG & ĐIỀU PHỐI
# ==========================================
def ask_ai_fallback(ticker, language):
    if language == "Tiếng Việt":
        return f"⚠️ *Hệ thống AI đang bận hoặc lỗi cấu hình. Mã **{ticker}** hiện đang ở vùng theo dõi. Vui lòng kiểm tra API Key.*"
    else:
        return f"⚠️ *AI System busy. Ticker **{ticker}** is under observation. Check API Key.*"

def get_ai_analysis(ticker, language="Tiếng Việt", model_name="gemini-1.5-flash"):
    """
    Hàm nhận thêm tham số model_name để linh hoạt theo người dùng.
    """
    try:
        return ask_ai_primary(ticker, language, model_name)
    except Exception as e:
        print(f"Lỗi AI ({model_name}): {e}")
        return ask_ai_fallback(ticker, language)
