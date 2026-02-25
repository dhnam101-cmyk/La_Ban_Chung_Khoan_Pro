"""
================================================================================
  chatbot_ui.py — Giao diện Chatbot AI
  
  Fixes:
  ✅ Truyền stock_data vào AI engine để tránh crash
  ✅ Chatbot nằm dưới biểu đồ (được gọi sau render_chart trong app.py)
  ✅ Reset chat history khi đổi ticker
  ✅ Voice output có thể tắt nếu bị lỗi trình duyệt
  ✅ Tương thích mode "ticker" và "general"
================================================================================
"""

import streamlit as st
from ai_engine import get_ai_analysis

try:
    from streamlit_mic_recorder import speech_to_text
    VOICE_ENABLED = True
except ImportError:
    VOICE_ENABLED = False


def render_chat_interface(
    ticker: str,
    lang: str,
    model: str,
    mode: str = "ticker",         # "ticker" | "general"
    stock_data: dict = None,      # Dữ liệu thực từ data_fetcher (quan trọng!)
    initial_query: str = ""       # Query ban đầu cho mode general
):
    """
    Render giao diện chat AI.
    Vị trí: Luôn được gọi SAU khi render_chart() — nằm dưới biểu đồ.
    
    Args:
        ticker:       Mã cổ phiếu hoặc "Thị trường"
        lang:         Ngôn ngữ phản hồi AI
        model:        Tên model Gemini
        mode:         "ticker" để phân tích mã cụ thể, "general" cho câu hỏi chung
        stock_data:   Dict dữ liệu cổ phiếu — PHẢI TRUYỀN để AI có context thực tế
        initial_query: Câu hỏi ban đầu (dành cho mode general)
    """
    
    # ── Khởi tạo / Reset session khi đổi ticker ───────────────────────────────
    session_key = f"chat_{ticker}_{mode}"
    
    if st.session_state.get("_chat_key") != session_key:
        st.session_state["_chat_key"]   = session_key
        st.session_state["chat_history"] = []  # Reset lịch sử chat
        
        # ── Tự động tạo phân tích khởi đầu khi load ───────────────────────────
        with st.spinner("🤖 AI đang soạn phân tích ban đầu..."):
            initial_reply = get_ai_analysis(
                ticker=ticker,
                lang=lang,
                model_name=model,
                mode=mode,
                stock_data=stock_data,
                initial_query=initial_query,
                context=""
            )
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": initial_reply
        })
    
    # ── Hiển thị lịch sử chat ─────────────────────────────────────────────────
    chat_container = st.container(height=480, border=True)
    
    with chat_container:
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # ── Input: Text + Voice ───────────────────────────────────────────────────
    if VOICE_ENABLED:
        col_text, col_voice = st.columns([0.85, 0.15])
        with col_text:
            user_text = st.chat_input("💬 Hỏi thêm AI điều gì đó...", key=f"chat_input_{ticker}")
        with col_voice:
            st.markdown("<div style='padding-top:8px'>", unsafe_allow_html=True)
            user_audio = speech_to_text(
                language='vi-VN',
                start_prompt="🎙️",
                stop_prompt="⏹️",
                key=f'mic_chat_{ticker}'
            )
            st.markdown("</div>", unsafe_allow_html=True)
        prompt = user_text or user_audio
    else:
        prompt = st.chat_input("💬 Hỏi thêm AI điều gì đó...", key=f"chat_input_{ticker}")
    
    # ── Xử lý câu hỏi mới ────────────────────────────────────────────────────
    if prompt:
        # Thêm message của user vào history
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        
        # Hiện ngay trong container
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("Đang suy nghĩ..."):
                    reply = get_ai_analysis(
                        ticker=ticker,
                        lang=lang,
                        model_name=model,
                        context=prompt,
                        mode=mode,
                        stock_data=stock_data,
                        initial_query=initial_query
                    )
                st.markdown(reply)
        
        # Lưu reply vào history
        st.session_state["chat_history"].append({"role": "assistant", "content": reply})
        
        # ── Text-to-Speech (tuỳ chọn, bắt lỗi an toàn) ──────────────────────
        try:
            clean = (
                reply
                .replace("'", " ").replace('"', ' ')
                .replace("\n", " ").replace("#", "")
                .replace("*", "")[:500]  # Giới hạn 500 ký tự để tránh nói quá dài
            )
            tts_js = (
                f"<script>"
                f"var u=new SpeechSynthesisUtterance('{clean}');"
                f"u.lang='vi-VN'; u.rate=1.0;"
                f"window.speechSynthesis.cancel();"  # Dừng cái đang nói nếu có
                f"window.speechSynthesis.speak(u);"
                f"</script>"
            )
            st.components.v1.html(tts_js, height=0)
        except Exception:
            pass  # TTS không quan trọng, bỏ qua nếu lỗi
        
        # Rerun để cập nhật container
        st.rerun()
