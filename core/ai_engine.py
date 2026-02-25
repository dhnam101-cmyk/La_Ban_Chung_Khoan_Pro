import streamlit as st
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

def setup_gemini(model_name):
    if "GOOGLE_API_KEY" not in st.secrets:
        raise ValueError("Thiếu API Key")
    
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    # Tự động gán "-latest" để chống lỗi 404 Not Found của Google
    if "-latest" not in model_name:
        model_name = f"{model_name}-latest"
        
    return genai.GenerativeModel(model_name)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def ask_ai_primary(ticker, language, model_name, context=""):
    model = setup_gemini(model_name)

    base_prompt = f"""
    Bạn là Giám đốc Phân tích Chiến lược. Hãy phân tích mã/thị trường: {ticker}
    Ngôn ngữ: {language}
    YÊU CẦU: Đánh giá định giá, dòng tiền, vĩ mô và đưa ra khuyến nghị.
    """
    
    final_prompt = f"{base_prompt}\n\nNgười dùng hỏi thêm: {context}" if context else base_prompt
    
    response = model.generate_content(final_prompt)
    return f"**[🤖 CHUYÊN GIA AI]**\n\n{response.text}"

def get_ai_analysis(ticker, language="Tiếng Việt", model_name="gemini-1.5-flash-latest", context=""):
    try:
        return ask_ai_primary(ticker, language, model_name, context)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Rate limited" in error_msg or "quota" in error_msg.lower():
            return "⏳ **Google báo AI đang quá tải.** Vui lòng đợi 1 phút rồi nhấn tìm kiếm lại."
        elif "404" in error_msg:
            return f"❌ **Lỗi Google AI:** Không tìm thấy model {model_name}. Vui lòng kiểm tra lại cấu hình."
        else:
            return f"⚠️ **Lỗi AI:** {error_msg}"
