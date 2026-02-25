import streamlit as st
from core.ai_engine import get_ai_analysis
from streamlit_mic_recorder import speech_to_text

def render_chat_interface(ticker, lang, model, is_general_query=False, initial_query=None):
    if "current_ticker" not in st.session_state or st.session_state.current_ticker != ticker:
        st.session_state.current_ticker = ticker
        st.session_state.chat_history = []
        
        with st.spinner("AI đang soạn báo cáo..."):
            if is_general_query and initial_query:
                custom_prompt = f"Người dùng hỏi: '{initial_query}'. Hãy phân tích chuyên sâu."
                initial_analysis = get_ai_analysis(ticker, lang, model, context=custom_prompt)
            else:
                initial_analysis = get_ai_analysis(ticker, lang, model, context="Viết bài phân tích điểm mạnh, điểm yếu của mã này.")
            st.session_state.chat_history.append({"role": "assistant", "content": initial_analysis})

    chat_container = st.container(height=500, border=True)
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    col_chat, col_mic = st.columns([0.85, 0.15])
    with col_chat:
        user_text = st.chat_input("💬 Hỏi thêm AI điều gì đó...")
    with col_mic:
        user_audio_text = speech_to_text(language='vi-VN', start_prompt="🎙️ Bấm nói", stop_prompt="⏹️ Dừng", key=f'mic_{ticker}')

    prompt = user_text or user_audio_text
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"): st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Đang suy nghĩ..."):
                    reply = get_ai_analysis(ticker, lang, model, context=prompt)
                    st.markdown(reply)
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                    
                    clean_text = reply.replace("'", " ").replace('"', ' ').replace("\n", " ")
                    js = f"<script>var msg=new SpeechSynthesisUtterance('{clean_text}');msg.lang='vi-VN';window.speechSynthesis.speak(msg);</script>"
                    st.components.v1.html(js, height=0)
