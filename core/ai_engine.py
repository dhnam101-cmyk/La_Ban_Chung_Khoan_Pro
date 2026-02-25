import streamlit as st
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

def ask_ai_primary(ticker, language, model_name, context=""):
    if "GOOGLE_API_KEY" not in st.secrets:
        raise ValueError("LỖI_KEY")
    
    # Sử dụng thư viện SDK mới nhất của Google
    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
    
    # Prompt chuẩn
    base_prompt = f"""
    Bạn là Giám đốc Phân tích Chiến lược tại quỹ đầu tư.
    Phân tích mã/thị trường: {ticker}
    Ngôn ngữ: {language}
    Yêu cầu: Đánh giá định giá (P/E, P/B), dòng tiền, vĩ mô và đưa ra khuyến nghị. Trình bày bằng Markdown.
    """
    final_prompt = f"{base_prompt}\n\nNgười dùng hỏi: {context}" if context else base_prompt
    
    # Gọi model
    response = client.models.generate_content(
        model=model_name,
        contents=final_prompt
    )
    return f"**[🤖 AI - {model_name}]**\n\n{response.text}"

def get_ai_analysis(ticker, language="Tiếng Việt", model_name="gemini-2.0-flash", context=""):
    try:
        return ask_ai_primary(ticker, language, model_name, context)
    except Exception as e:
        error_msg = str(e)
        if "LỖI_KEY" in error_msg:
            return "❌ **Chưa cấu hình API Key** trong Streamlit Secrets."
        elif "429" in error_msg or "quota" in error_msg.lower():
            return "⏳ **Hệ thống AI đang quá tải.** Vui lòng đợi 30 giây rồi thử lại."
        else:
            return f"⚠️ **Lỗi AI:** {error_msg}"
