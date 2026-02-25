import streamlit as st
import warnings

warnings.filterwarnings("ignore")

try:
    import google.generativeai as genai
except ImportError:
    pass

def get_ai_analysis(ticker, lang, model_name, context=""):
    if "GOOGLE_API_KEY" not in st.secrets:
        return "❌ LỖI: Chưa cấu hình GOOGLE_API_KEY."
        
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        model = genai.GenerativeModel(model_name)
        
        base_prompt = f"Bạn là Giám đốc Phân tích Đầu tư. Trả lời bằng {lang}. Phân tích chuyên sâu mã/thị trường: {ticker}."
        final_prompt = f"{base_prompt}\nNội dung chi tiết: {context}" if context else base_prompt
        
        response = model.generate_content(final_prompt)
        return f"**[🤖 AI - {model_name.upper()}]**\n\n{response.text}"
        
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            return "⏳ **AI đang bận (Quá tải).** Vui lòng đợi 1 phút rồi thử lại."
        else:
            return f"⚠️ **Lỗi kết nối AI:** {error_msg}"
