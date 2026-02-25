"""
================================================================================
  components/chatbot_ui.py — Giao diện Chatbot AI
  Fixes:
  ✅ Truyền stock_data → ai_engine, không còn crash do thiếu context
  ✅ Reset chat history khi đổi ticker/mode
  ✅ Voice output an toàn (bắt lỗi)
  ✅ Hỗ trợ mode "ticker" và "general"
================================================================================
"""

import streamlit as st
from core.ai_engine import get_ai_analysis

try:
    from streamlit_mic_recorder import speech_to_text
    VOICE_ENABLED = True
except ImportError:
    VOICE_ENABLED = False


def render_chat_interface(
    ticker:        str,
    lang:          str,
    model:         str,
    mode:          str  = "ticker",
    stock_data:    dict = None,
    initial_query: str  = "",
):
    """
    Giao diện chat AI — luôn được gọi SAU render_chart() nên nằm bên dưới.

    Args:
        ticker:        Mã cổ phiếu hoặc "Thị trường"
        lang:          Ngôn ngữ phản hồi
        model:         Tên model Gemini
        mode:          "ticker" | "general"
        stock_data:    Dict dữ liệu thực (từ data_fetcher) — quan trọng!
        initial_query: Câu hỏi ban đầu cho mode general
    """

    session_key = f"chat_{ticker}_{mode}_{initial_query[:30]}"

    # Reset lịch sử khi đổi context
    if st.session_state.get("_chat_key") != session_key:
        st.session_state["_chat_key"]    = session_key
        st.session_state["chat_history"] = []

        with st.spinner("🤖 AI đang soạn phân tích ban đầu..."):
            first_reply = get_ai_analysis(
                ticker=ticker, lang=lang, model_name=model,
                mode=mode, stock_data=stock_data,
                initial_query=initial_query, context=""
            )
        st.session_state["chat_history"].append(
            {"role": "assistant", "content": first_reply}
        )

    # Hiển thị lịch sử
    chat_box = st.container(height=480, border=True)
    with chat_box:
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Input box
    if VOICE_ENABLED:
        col_t, col_v = st.columns([0.85, 0.15])
        with col_t:
            user_text = st.chat_input("💬 Hỏi thêm AI...", key=f"ci_{ticker}")
        with col_v:
            st.markdown("<div style='padding-top:8px'>", unsafe_allow_html=True)
            user_audio = speech_to_text(
                language='vi-VN', start_prompt="🎙️", stop_prompt="⏹️",
                key=f'mic_{ticker}'
            )
            st.markdown("</div>", unsafe_allow_html=True)
        prompt = user_text or user_audio
    else:
        prompt = st.chat_input("💬 Hỏi thêm AI...", key=f"ci_{ticker}")

    if prompt:
        st.session_state["chat_history"].append({"role": "user", "content": prompt})

        with chat_box:
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Đang suy nghĩ..."):
                    reply = get_ai_analysis(
                        ticker=ticker, lang=lang, model_name=model,
                        context=prompt, mode=mode,
                        stock_data=stock_data, initial_query=initial_query
                    )
                st.markdown(reply)

        st.session_state["chat_history"].append({"role": "assistant", "content": reply})

        # TTS (an toàn)
        try:
            clean = (
                reply.replace("'", " ").replace('"', ' ')
                     .replace("\n", " ").replace("#", "").replace("*", "")[:500]
            )
            st.components.v1.html(
                f"<script>var u=new SpeechSynthesisUtterance('{clean}');"
                f"u.lang='vi-VN';window.speechSynthesis.cancel();"
                f"window.speechSynthesis.speak(u);</script>",
                height=0
            )
        except Exception:
            pass

        st.rerun()
