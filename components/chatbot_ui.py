import streamlit as st
from core.ai_engine import get_ai_analysis
from streamlit_mic_recorder import speech_to_text

def render_chat_interface(ticker, lang, model):
    st.subheader(f"💬 Trò chuyện AI - Mã {ticker}")
    
    # Khởi tạo hoặc Reset lịch sử chat khi đổi mã cổ phiếu
    if "current_ticker" not in st.session_state or st.session_state.current_ticker != ticker:
        st.session_state.current_ticker = ticker
        st.session_state.chat_history = []
        
        # Lấy bài phân tích mẫu đầu tiên
        with st.spinner("AI đang soạn báo cáo tổng quan..."):
            initial_analysis = get_ai_analysis(ticker, lang, model, context="Viết bài phân tích ngắn gọn điểm mạnh, điểm yếu của mã này.")
            st.session_state.chat_history.append({"role": "assistant", "content": initial_analysis})

    # Cấu trúc vùng chứa Chat
    chat_container = st.container(height=400, border=True)
    
    # Hiển thị lịch sử tin nhắn
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # ==========================================
    # INPUT: TEXT HOẶC MIC GIỌNG NÓI
    # ==========================================
    col_chat, col_mic = st.columns([0.8, 0.2])
    
    with col_chat:
        user_text = st.chat_input("Hỏi thêm (VD: Điểm mua hợp lý?)...")
        
    with col_mic:
        st.caption("🎙️ Mic")
        # Chuyển đổi giọng nói thành văn bản
        user_audio_text = speech_to_text(language='vi-VN', start_prompt="Bấm nói", stop_prompt="Dừng", key=f'mic_{ticker}')

    # Gộp 2 nguồn input (nếu user gõ phím hoặc nói)
    prompt = user_text or user_audio_text
    
    if prompt:
        # 1. Thêm câu hỏi vào UI
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # 2. Lấy câu trả lời từ AI
            with st.chat_message("assistant"):
                with st.spinner("Đang suy nghĩ..."):
                    reply = get_ai_analysis(ticker, lang, model, context=prompt)
                    st.markdown(reply)
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                    
                    # Nút phát âm thanh cho câu trả lời mới
                    clean_text = reply.replace("'", " ").replace('"', ' ').replace("\n", " ")
                    js = f"<script>var msg=new SpeechSynthesisUtterance('{clean_text}');msg.lang='vi-VN';window.speechSynthesis.speak(msg);</script>"
                    st.components.v1.html(js, height=0)
