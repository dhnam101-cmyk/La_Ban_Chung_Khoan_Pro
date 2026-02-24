import streamlit as st
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

# ==========================================
# CẤU HÌNH KẾT NỐI GEMINI
# ==========================================
def setup_gemini():
    try:
        # Lấy chìa khóa từ "két sắt" Secrets của Streamlit
        api_key = st.secrets["GOOGLE_API_KEY"]
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        st.error(f"Lỗi cấu hình API Gemini: {e}")
        return None

# ==========================================
# CƠ CHẾ 1: GỌI MODEL AI CHÍNH (GEMINI NÂNG CẤP)
# ==========================================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def ask_ai_primary(ticker, language):
    model = setup_gemini()
    if not model:
        raise Exception("Không thể kết nối Gemini")

    # Lấy thông số từ UI (Nếu có) để AI phân tích sâu hơn
    # System Prompt được tinh chỉnh để phân tích sắc bén
    prompt = f"""
    Bạn là một Giám đốc Phân tích Chiến lược tại một quỹ đầu tư lớn.
    Hãy phân tích mã cổ phiếu: {ticker}
    Ngôn ngữ trả lời: {language}
    
    YÊU CẦU PHÂN TÍCH:
    1. **Định giá:** Dựa vào chỉ số P/E và P/B thường thấy của ngành, hãy đánh giá mã này đang Đắt hay Rẻ.
    2. **Dòng tiền & Kỹ thuật:** Nhận định về biến động khối lượng (Volume) và các vùng hỗ trợ/kháng cự quan trọng.
    3. **Vĩ mô & Ngành:** Những tin tức vĩ mô nào (Lãi suất, Tỷ giá, Chính sách) đang tác động trực tiếp đến mã này?
    4. **Khuyến nghị chiến thuật:** Đưa ra hành động cụ thể (Mua tích lũy, Nắm giữ hay Hạ tỷ trọng) và Quản trị rủi ro.

    PHONG CÁCH: Chuyên nghiệp, khách quan, không dùng từ ngữ sáo rỗng. Trình bày bằng Markdown với các icon trực quan.
    """
    
    response = model.generate_content(prompt)
    return f"**[🤖 CHUYÊN GIA AI PHÂN TÍCH]**\n\n{response.text}"

# ==========================================
# CƠ CHẾ 2 & 3: DỰ PHÒNG & ĐIỀU PHỐI (GIỮ NGUYÊN)
# ==========================================
def ask_ai_fallback(ticker, language):
    if language == "Tiếng Việt":
        return f"⚠️ *Hệ thống Gemini đang bảo trì. Mã **{ticker}** hiện đang tiến gần vùng hỗ trợ. Vui lòng kiểm tra lại cấu hình Secrets.*"
    else:
        return f"⚠️ *Gemini System is busy. Ticker **{ticker}** is at support level. Check Secrets config.*"

def get_ai_analysis(ticker, language="Tiếng Việt"):
    try:
        return ask_ai_primary(ticker, language)
    except Exception as e:
        return ask_ai_fallback(ticker, language)
