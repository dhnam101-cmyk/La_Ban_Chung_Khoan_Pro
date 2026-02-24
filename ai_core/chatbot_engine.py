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
        # Sử dụng model gemini-1.5-flash (tốc độ cao, ổn định)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        st.error(f"Lỗi cấu hình API Gemini: {e}")
        return None

# ==========================================
# CƠ CHẾ 1: GỌI MODEL AI CHÍNH (GEMINI THẬT)
# ==========================================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def ask_ai_primary(ticker, language):
    model = setup_gemini()
    if not model:
        raise Exception("Không thể kết nối Gemini")

    # Xây dựng câu lệnh (Prompt) chuyên nghiệp
    prompt = f"""
    Bạn là một chuyên gia phân tích chứng khoán cấp cao.
    Hãy phân tích mã cổ phiếu: {ticker}
    Ngôn ngữ trả lời: {language}
    
    Yêu cầu:
    1. Đưa ra nhận định ngắn gọn về xu hướng hiện tại.
    2. Phân tích yếu tố vĩ mô ảnh hưởng đến mã này.
    3. Đưa ra khuyến nghị dựa trên phân tích kỹ thuật cơ bản.
    4. Trình bày bằng Markdown, súc tích, dễ đọc.
    """
    
    response = model.generate_content(prompt)
    return f"**[AI Gemini Pro - Real-time]**\n\n{response.text}"

# ==========================================
# CƠ CHẾ 2: KỊCH BẢN DỰ PHÒNG (FALLBACK)
# ==========================================
def ask_ai_fallback(ticker, language):
    if language == "Tiếng Việt":
        return f"⚠️ *Hệ thống Gemini đang bảo trì hoặc chưa cấu hình API Key.*\n\nMã **{ticker}** hiện đang được theo dõi chặt chẽ. Vui lòng kiểm tra lại cấu hình Secrets trên Streamlit."
    else:
        return f"⚠️ *Gemini System is busy or API Key is missing.*\n\nTicker **{ticker}** is under close observation. Please check your Streamlit Secrets configuration."

# ==========================================
# CƠ CHẾ 3: TỔNG ĐIỀU PHỐI
# ==========================================
def get_ai_analysis(ticker, language="Tiếng Việt"):
    try:
        return ask_ai_primary(ticker, language)
    except Exception as e:
        print(f"Lỗi AI: {e}")
        return ask_ai_fallback(ticker, language)
