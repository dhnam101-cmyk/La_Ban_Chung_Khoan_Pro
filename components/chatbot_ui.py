"""
components/chatbot_ui.py — v6.0
Auto phân tích NGAY khi load (không có nút bấm).
Dùng session cache để không gọi lại mỗi lần re-render.
"""
import streamlit as st
from core.ai_engine import get_ai_analysis

try:
    from streamlit_mic_recorder import speech_to_text
    VOICE_ENABLED = True
except ImportError:
    VOICE_ENABLED = False


def render_chat_interface(ticker: str, lang: str, model: str,
                          mode: str = "ticker", stock_data: dict = None,
                          initial_query: str = ""):
    sk       = f"ck_{ticker}_{mode}_{model}_{initial_query[:15]}"
    hist_key = f"h_{sk}"
    done_key = f"d_{sk}"

    # Reset khi ticker/mode thay đổi
    if st.session_state.get("_sk") != sk:
        st.session_state["_sk"]      = sk
        st.session_state[hist_key]   = []
        st.session_state[done_key]   = False

    history = st.session_state.get(hist_key, [])

    # ── AUTO phân tích ngay lần đầu (không cần bấm nút) ─────────────────────
    if not st.session_state.get(done_key):
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

    # ── Hiển thị lịch sử ────────────────────────────────────────────────────
    chat_box = st.container(height=560, border=True)
    with chat_box:
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # ── Nếu rate limit → nút retry + hướng dẫn ──────────────────────────────
    last = history[-1].get("content","") if history else ""
    if "Rate Limit" in last or "quota" in last.lower():
        c1, c2 = st.columns([0.35, 0.65])
        with c1:
            if st.button("🔄 Thử lại", key=f"retry_{sk}", type="primary"):
                st.session_state[done_key] = False
                st.session_state[hist_key] = []
                st.rerun()
        with c2:
            st.warning("Đợi 1–2 phút rồi Thử lại. Chuyển sang ⚡ Flash nếu vẫn lỗi.")
        return

    # ── Chat input hỏi thêm ──────────────────────────────────────────────────
    if VOICE_ENABLED:
        c1, c2 = st.columns([0.87, 0.13])
        with c1:
            user_text = st.chat_input("💬 Hỏi thêm về cổ phiếu...", key=f"ci_{sk}")
        with c2:
            user_audio = speech_to_text(language="vi-VN", start_prompt="🎙️",
                                        stop_prompt="⏹️", key=f"mic_{sk}")
        prompt = user_text or user_audio
    else:
        prompt = st.chat_input("💬 Hỏi thêm về cổ phiếu này...", key=f"ci_{sk}")

    if prompt:
        history.append({"role": "user", "content": prompt})
        with chat_box:
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("🔍 Đang tìm kiếm và phân tích..."):
                    reply = get_ai_analysis(
                        ticker=ticker, lang=lang, model_name=model,
                        context=prompt, mode=mode,
                        stock_data=stock_data, initial_query=initial_query,
                    )
                st.markdown(reply)
        history.append({"role": "assistant", "content": reply})
        st.session_state[hist_key] = history
        try:
            clean = "".join(c for c in reply if c.isalnum() or c in " .,!?").strip()[:300]
            st.components.v1.html(
                f"<script>var u=new SpeechSynthesisUtterance('{clean}');"
                "u.lang='vi-VN';window.speechSynthesis.cancel();"
                "window.speechSynthesis.speak(u);</script>", height=0)
        except: pass
        st.rerun()
