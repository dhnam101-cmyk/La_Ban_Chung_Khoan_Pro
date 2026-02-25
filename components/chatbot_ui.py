"""
chatbot_ui.py — v4.0 FLAT STRUCTURE
- Import flat: from ai_engine import ...
- Nút "🤖 Phân tích ngay" để user chủ động (tránh rate limit auto-spam)
- Nút "🔄 Thử lại" khi rate limit
"""
import streamlit as st
from ai_engine import get_ai_analysis

try:
    from streamlit_mic_recorder import speech_to_text
    VOICE_ENABLED = True
except ImportError:
    VOICE_ENABLED = False


def render_chat_interface(ticker: str, lang: str, model: str,
                          mode: str = "ticker", stock_data: dict = None,
                          initial_query: str = ""):
    sk       = f"ck_{ticker}_{mode}_{initial_query[:15]}"
    hist_key = f"h_{sk}"
    done_key = f"d_{sk}"

    # Reset khi ticker/mode thay đổi
    if st.session_state.get("_sk") != sk:
        st.session_state["_sk"]    = sk
        st.session_state[hist_key] = []
        st.session_state[done_key] = False

    history = st.session_state.get(hist_key, [])

    # Hiển thị nút phân tích nếu chưa chạy lần nào
    if not st.session_state.get(done_key):
        c1, c2 = st.columns([0.55, 0.45])
        with c1:
            run_btn = st.button(
                "🤖 Phân tích ngay (AI + Google Search)",
                key=f"run_{sk}", use_container_width=True, type="primary"
            )
        with c2:
            st.caption("⚡ Flash: 15 req/phút | Pro: ~2 req/phút\n💡 Tránh bấm nhiều lần liên tiếp")

        if not run_btn:
            return

        with st.spinner("🔍 AI đang tìm kiếm thông tin và phân tích... (15–30 giây)"):
            reply = get_ai_analysis(
                ticker=ticker, lang=lang, model_name=model,
                mode=mode, stock_data=stock_data,
                initial_query=initial_query, context="",
            )
        history.append({"role": "assistant", "content": reply})
        st.session_state[hist_key] = history
        st.session_state[done_key] = True
        st.rerun()
        return

    # Hiển thị lịch sử chat
    chat_box = st.container(height=550, border=True)
    with chat_box:
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Nếu đang rate limit → hiện nút retry
    last_content = history[-1].get("content", "") if history else ""
    is_rate_limit = "Rate Limit" in last_content or "quota" in last_content.lower()

    if is_rate_limit:
        c1, c2 = st.columns([0.45, 0.55])
        with c1:
            if st.button("🔄 Thử lại", key=f"retry_{sk}", type="primary"):
                st.session_state[done_key] = False
                st.session_state[hist_key] = []
                st.rerun()
        with c2:
            st.warning("Đợi 1–2 phút rồi bấm Thử lại. Chuyển sang ⚡ Flash nếu vẫn lỗi.")
        return

    # Input chat tiếp theo
    if VOICE_ENABLED:
        col_t, col_v = st.columns([0.87, 0.13])
        with col_t:
            user_text = st.chat_input("💬 Hỏi thêm...", key=f"ci_{sk}")
        with col_v:
            user_audio = speech_to_text(
                language="vi-VN", start_prompt="🎙️", stop_prompt="⏹️",
                key=f"mic_{sk}"
            )
        prompt = user_text or user_audio
    else:
        prompt = st.chat_input("💬 Hỏi thêm về cổ phiếu này...", key=f"ci_{sk}")

    if prompt:
        history.append({"role": "user", "content": prompt})
        with chat_box:
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("🔍 Đang tìm kiếm và suy nghĩ..."):
                    reply = get_ai_analysis(
                        ticker=ticker, lang=lang, model_name=model,
                        context=prompt, mode=mode,
                        stock_data=stock_data, initial_query=initial_query,
                    )
                st.markdown(reply)
        history.append({"role": "assistant", "content": reply})
        st.session_state[hist_key] = history
        # TTS
        try:
            clean = "".join(c for c in reply if c.isalnum() or c in " .,!?").strip()[:300]
            st.components.v1.html(
                f"<script>var u=new SpeechSynthesisUtterance('{clean}');"
                "u.lang='vi-VN';window.speechSynthesis.cancel();"
                "window.speechSynthesis.speak(u);</script>",
                height=0
            )
        except Exception:
            pass
        st.rerun()
