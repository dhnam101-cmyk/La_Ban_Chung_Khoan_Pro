import streamlit as st
from google import genai

def ask_ai_primary(ticker, language, model_name, context=""):
    if "GOOGLE_API_KEY" not in st.secrets:
        raise ValueError("LỖI_KEY")
    
    # Dùng chuẩn API mới của Google
    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
    
    base_prompt = f"""
    Bạn là Giám đốc Phân tích Đầu tư. Phân tích mã/thị trường: {ticker}
    Ngôn ngữ: {language}
    Đánh giá định giá (P/E, P/B), dòng tiền, vĩ mô và khuyến nghị. (Trình bày Markdown).
    """
    final_prompt = f"{base_prompt}\n\nNgười dùng hỏi thêm: {context}" if context else base_prompt
    
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
            return "⏳ **Hệ thống AI đang bận.** Vui lòng đợi 30 giây rồi thử lại."
        else:
            return f"⚠️ **Lỗi AI:** {error_msg}"
