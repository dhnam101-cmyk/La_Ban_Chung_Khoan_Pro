"""
components/chatbot_ui.py — v3.0
Auto phân tích khi load ticker (có spinner rõ ràng).
Không cần bấm nút thêm — UX tốt hơn.
"""
import streamlit as st
from core.ai_engine import get_ai_analysis

try:
    from streamlit_mic_recorder import speech_to_text
    VOICE_ENABLED = True
except ImportError:
    VOICE_ENABLED = False


def render_chat_interface(ticker, lang, model, mode="ticker",
                          stock_data=None, initial_query=""):
    session_key = f"chat_{ticker}_{mode}_{initial_query[:20]}"
    hist_key    = f"h_{session_key}"
    done_key    = f"d_{session_key}"

    # Reset khi đổi context
    if st.session_state.get("_ck") != session_key:
        st.session_state["_ck"]  = session_key
        st.session_state[hist_key] = []
        st.session_state[done_key] = False

    history = st.session_state.get(hist_key, [])

    # Auto-phân tích lần đầu (chỉ 1 lần, có cache session)
    if not st.session_state.get(done_key):
        with st.spinner("🤖 AI đang phân tích... (có thể mất 10–20 giây)"):
            reply = get_ai_analysis(
                ticker=ticker, lang=lang, model_name=model,
                mode=mode, stock_data=stock_data,
                initial_query=initial_query, context="",
            )
        history.append({"role": "assistant", "content": reply})
        st.session_state[hist_key] = history
        st.session_state[done_key] = True
        st.rerun()

    # Hiển thị lịch sử
    chat_box = st.container(height=520, border=True)
    with chat_box:
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Rate limit hint
    if history and ("Rate Limit" in history[-1].get("content","") or "quota" in history[-1].get("content","").lower()):
        col1, col2 = st.columns([0.5, 0.5])
        with col1:
            if st.button("🔄 Thử lại sau 1 phút", key=f"retry_{session_key}"):
                st.session_state[done_key] = False
                st.session_state[hist_key] = []
                st.rerun()
        with col2:
            st.caption("💡 Tip: Chuyển sang **⚡ Flash** trong sidebar")
        return

    # Input hỏi thêm
    if VOICE_ENABLED:
        c1, c2 = st.columns([0.87, 0.13])
        with c1:
            user_text = st.chat_input("💬 Hỏi thêm...", key=f"ci_{session_key}")
        with c2:
            user_audio = speech_to_text(language='vi-VN', start_prompt="🎙️",
                                        stop_prompt="⏹️", key=f"mic_{session_key}")
        prompt = user_text or user_audio
    else:
        prompt = st.chat_input("💬 Hỏi thêm về cổ phiếu này...", key=f"ci_{session_key}")

    if prompt:
        history.append({"role": "user", "content": prompt})
        with chat_box:
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Đang suy nghĩ..."):
                    reply = get_ai_analysis(
                        ticker=ticker, lang=lang, model_name=model,
                        context=prompt, mode=mode,
                        stock_data=stock_data, initial_query=initial_query,
                    )
                st.markdown(reply)
        history.append({"role": "assistant", "content": reply})
        st.session_state[hist_key] = history

        try:
            clean = "".join(c for c in reply if c.isalnum() or c in " .,!?").strip()[:350]
            st.components.v1.html(
                f"<script>var u=new SpeechSynthesisUtterance('{clean}');"
                "u.lang='vi-VN';window.speechSynthesis.cancel();"
                "window.speechSynthesis.speak(u);</script>",
                height=0
            )
        except Exception:
            pass
        st.rerun()
