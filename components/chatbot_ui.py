"""
================================================================================
  components/chatbot_ui.py — v2.5

  FIXES:
  ✅ Không tự động gọi AI khi load trang (gây rate limit)
  ✅ Chỉ gọi AI khi user bấm "Phân tích" hoặc hỏi câu hỏi
  ✅ Cache session_state tránh gọi trùng lặp
  ✅ Nút "🔄 Tạo phân tích" rõ ràng thay vì auto-trigger
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
    session_key  = f"chat_{ticker}_{mode}_{initial_query[:20]}"
    history_key  = f"history_{session_key}"
    analyzed_key = f"analyzed_{session_key}"

    # Reset khi đổi ticker/context
    if st.session_state.get("_last_chat_key") != session_key:
        st.session_state["_last_chat_key"] = session_key
        st.session_state[history_key]      = []
        st.session_state[analyzed_key]     = False

    history = st.session_state.get(history_key, [])

    # ── Nút kích hoạt phân tích lần đầu (tránh auto-call gây rate limit) ────
    if not st.session_state.get(analyzed_key):
        col_btn, col_info = st.columns([0.35, 0.65])
        with col_btn:
            do_analyze = st.button(
                "🤖 Tạo phân tích AI",
                key=f"btn_analyze_{session_key}",
                use_container_width=True,
                type="primary",
            )
        with col_info:
            st.caption(
                "💡 **Lưu ý Free Tier:** Dùng **Flash** (sidebar) để tránh Rate Limit. "
                "Pro chỉ có ~2 requests/phút."
            )

        if do_analyze:
            with st.spinner("🤖 AI đang phân tích..."):
                first_reply = get_ai_analysis(
                    ticker=ticker, lang=lang, model_name=model,
                    mode=mode, stock_data=stock_data,
                    initial_query=initial_query, context="",
                )
            history.append({"role": "assistant", "content": first_reply})
            st.session_state[history_key]  = history
            st.session_state[analyzed_key] = True
            st.rerun()
        return  # Chưa phân tích → dừng ở đây

    # ── Hiển thị lịch sử chat ────────────────────────────────────────────────
    chat_box = st.container(height=500, border=True)
    with chat_box:
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # ── Input hỏi thêm ───────────────────────────────────────────────────────
    if VOICE_ENABLED:
        col_t, col_v = st.columns([0.87, 0.13])
        with col_t:
            user_text = st.chat_input("💬 Hỏi thêm về cổ phiếu này...", key=f"ci_{session_key}")
        with col_v:
            user_audio = speech_to_text(
                language='vi-VN', start_prompt="🎙️", stop_prompt="⏹️",
                key=f'mic_{session_key}'
            )
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
        st.session_state[history_key] = history

        # TTS nhẹ
        try:
            clean = reply.replace("'", " ").replace('"', ' ').replace("\n", " ")
            clean = ''.join(c for c in clean if c.isalnum() or c in ' .,?!').strip()[:400]
            st.components.v1.html(
                f"<script>var u=new SpeechSynthesisUtterance('{clean}');"
                f"u.lang='vi-VN';window.speechSynthesis.cancel();"
                f"window.speechSynthesis.speak(u);</script>",
                height=0
            )
        except Exception:
            pass

        st.rerun()
