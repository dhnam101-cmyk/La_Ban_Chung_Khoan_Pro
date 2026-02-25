"""
================================================================================
  core/ai_engine.py — Tích hợp Google Gemini AI

  FIXES v2.2:
  ✅ google-genai 1.64.0 đổi API: client.models → client.models.generate_content
     vẫn dùng được, nhưng response structure thay đổi → fix cách đọc response.text
  ✅ Thêm fallback dùng google.generativeai (SDK cũ) nếu genai mới lỗi
  ✅ Xử lý đầy đủ: 429, invalid key, model not found, network error
================================================================================
"""

import streamlit as st

# ── Thử import SDK mới (google-genai >= 0.8) ─────────────────────────────────
try:
    from google import genai as _new_genai
    NEW_SDK = True
except ImportError:
    NEW_SDK = False

# ── Thử import SDK cũ (google-generativeai) làm fallback ─────────────────────
try:
    import google.generativeai as _old_genai
    OLD_SDK = True
except ImportError:
    OLD_SDK = False


def _build_ticker_prompt(ticker: str, lang: str, context: str, stock_data: dict) -> str:
    """Prompt phân tích mã cổ phiếu — nhúng dữ liệu thực tế."""
    data_block = ""
    if stock_data:
        price = stock_data.get('price', 'N/A')
        vol   = stock_data.get('volume', 'N/A')
        try:
            price_fmt = f"{float(price):,.0f}" if price != 'N/A' else 'N/A'
            vol_fmt   = f"{int(vol):,}"         if vol   != 'N/A' else 'N/A'
        except Exception:
            price_fmt, vol_fmt = str(price), str(vol)

        data_block = f"""
## Dữ liệu thực tế:
- Giá hiện tại: {price_fmt}
- Khối lượng:   {vol_fmt}
- Sàn:          {stock_data.get('market', 'N/A')}
- Ngành:        {stock_data.get('industry', 'N/A')}
- P/E:          {stock_data.get('pe', 'N/A')} (TB ngành: {stock_data.get('avg_pe', 'N/A')})
- P/B:          {stock_data.get('pb', 'N/A')} (TB ngành: {stock_data.get('avg_pb', 'N/A')})
"""
    extra = f"\n\n**Câu hỏi bổ sung:** {context}" if (context and "tổng quan" not in context) else ""

    return f"""Bạn là Giám đốc Phân tích Đầu tư. Phân tích mã **{ticker}**:

{data_block}

Trình bày theo:
1. **Định giá**: P/E, P/B so ngành — rẻ hay đắt?
2. **Điểm mạnh & Điểm yếu**
3. **Tín hiệu kỹ thuật** (khối lượng, xu hướng)
4. **Khuyến nghị**: MUA / NẮM GIỮ / BÁN + lý do
5. **Rủi ro** cần lưu ý
{extra}

Ngôn ngữ: {lang}. Định dạng Markdown. Ghi chú: phân tích tham khảo, không phải lời khuyên đầu tư.""".strip()


def _build_general_prompt(query: str, lang: str) -> str:
    return f"""Bạn là Chuyên gia Kinh tế & Tài chính 20 năm kinh nghiệm.

Câu hỏi: **"{query}"**

Trả lời theo:
1. Phân tích góc nhìn vĩ mô / tài chính
2. Các luận điểm chính có căn cứ
3. Kết luận thực tiễn cho nhà đầu tư cá nhân VN

Ngôn ngữ: {lang}. Định dạng Markdown. Ghi chú: phân tích tham khảo.""".strip()


def _call_new_sdk(api_key: str, model_name: str, prompt: str) -> str:
    """Gọi API với google-genai >= 0.8 (SDK mới)."""
    client = _new_genai.Client(api_key=api_key)
    
    # SDK 1.x đổi cách trả về response — dùng try/except để tương thích cả 0.x và 1.x
    response = client.models.generate_content(
        model=model_name,
        contents=prompt
    )
    
    # Tương thích cả SDK 0.x và 1.x
    if hasattr(response, 'text') and response.text:
        return response.text
    # SDK 1.x có thể lồng trong candidates
    if hasattr(response, 'candidates') and response.candidates:
        for cand in response.candidates:
            if hasattr(cand, 'content') and hasattr(cand.content, 'parts'):
                parts = cand.content.parts
                if parts:
                    return "".join(p.text for p in parts if hasattr(p, 'text'))
    return str(response)


def _call_old_sdk(api_key: str, model_name: str, prompt: str) -> str:
    """Gọi API với google-generativeai (SDK cũ — fallback)."""
    _old_genai.configure(api_key=api_key)
    model    = _old_genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    return response.text


def get_ai_analysis(
    ticker:        str,
    lang:          str  = "Tiếng Việt",
    model_name:    str  = "gemini-2.0-flash",
    context:       str  = "",
    mode:          str  = "ticker",
    stock_data:    dict = None,
    initial_query: str  = "",
) -> str:
    """Gọi Gemini và trả về phân tích dạng markdown."""

    if not NEW_SDK and not OLD_SDK:
        return "❌ **Thiếu thư viện AI.** Chạy: `pip install google-genai`"

    # Lấy API key từ Streamlit Secrets
    api_key = None
    try:
        api_key = (st.secrets.get("GOOGLE_API_KEY")
                   or st.secrets.get("google_api_key")
                   or st.secrets.get("GEMINI_API_KEY"))
    except Exception:
        pass

    if not api_key:
        return (
            "❌ **Chưa cấu hình API Key**\n\n"
            "Thêm vào **Settings → Secrets** của Streamlit:\n"
            "```toml\nGOOGLE_API_KEY = \"AIza...\"\n```\n"
            "Lấy key miễn phí: https://aistudio.google.com/"
        )

    # Build prompt
    if mode == "ticker":
        prompt = _build_ticker_prompt(
            ticker, lang,
            context or "Viết phân tích tổng quan.",
            stock_data or {}
        )
    else:
        prompt = _build_general_prompt(initial_query or context, lang)

    # Gọi API — thử SDK mới trước, fallback SDK cũ
    raw_text = None
    last_err = ""

    if NEW_SDK:
        try:
            raw_text = _call_new_sdk(api_key, model_name, prompt)
        except Exception as e:
            last_err = str(e)
            # Nếu lỗi không phải 429/auth → thử SDK cũ
            if OLD_SDK and "429" not in last_err and "quota" not in last_err.lower():
                try:
                    raw_text = _call_old_sdk(api_key, model_name, prompt)
                    last_err = ""
                except Exception as e2:
                    last_err = str(e2)

    elif OLD_SDK:
        try:
            raw_text = _call_old_sdk(api_key, model_name, prompt)
        except Exception as e:
            last_err = str(e)

    # Xử lý kết quả
    if raw_text:
        return f"*🤖 **{model_name}***\n\n---\n\n{raw_text}"

    # Phân loại lỗi
    err = last_err.lower()
    if "429" in last_err or "quota" in err or "resource_exhausted" in err:
        return (
            "⏳ **AI đang quá tải (Rate Limit)**\n\n"
            "Đợi 30–60 giây rồi thử lại, hoặc chuyển sang model **Flash** "
            "để có quota cao hơn."
        )
    elif "api_key" in err or "invalid" in err or "401" in last_err or "403" in last_err:
        return "🔑 **API Key không hợp lệ.** Kiểm tra lại trong Streamlit Secrets."
    elif "not found" in err and "model" in err:
        return (
            f"⚠️ Model `{model_name}` không khả dụng. "
            "Chuyển sang **Gemini 2.0 Flash** trong Settings."
        )
    elif "network" in err or "connection" in err or "timeout" in err:
        return "🌐 **Lỗi kết nối mạng.** Kiểm tra kết nối và thử lại."
    return f"⚠️ **Lỗi AI:** {last_err}"
