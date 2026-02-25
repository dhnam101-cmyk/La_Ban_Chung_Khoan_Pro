"""
================================================================================
  core/ai_engine.py — Tích hợp Google Gemini AI
  Fixes:
  ✅ Luồng truyền stock_data vào prompt rõ ràng, không crash
  ✅ Xử lý 429 (quota), API key không hợp lệ, model not found
  ✅ Phân biệt prompt: ticker analysis vs general market query
================================================================================
"""

import streamlit as st

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def _build_ticker_prompt(ticker: str, lang: str, context: str, stock_data: dict) -> str:
    """Prompt phân tích mã cổ phiếu cụ thể — nhúng dữ liệu thực tế vào."""
    data_block = ""
    if stock_data:
        data_block = f"""
## Dữ liệu thực tế (Real-time):
| Chỉ số | Giá trị |
|--------|---------|
| Giá hiện tại | {stock_data.get('price', 'N/A'):,} |
| Khối lượng giao dịch | {stock_data.get('volume', 'N/A'):,} |
| Sàn niêm yết | {stock_data.get('market', 'N/A')} |
| Ngành | {stock_data.get('industry', 'N/A')} |
| P/E cổ phiếu | {stock_data.get('pe', 'N/A')} |
| P/E trung bình ngành | {stock_data.get('avg_pe', 'N/A')} |
| P/B cổ phiếu | {stock_data.get('pb', 'N/A')} |
| P/B trung bình ngành | {stock_data.get('avg_pb', 'N/A')} |
"""
    follow_up = f"\n\n**Câu hỏi bổ sung:** {context}" if (
        context and context != "Viết bài phân tích tổng quan."
    ) else ""

    return f"""
Bạn là **Giám đốc Phân tích Đầu tư** tại quỹ đầu tư hàng đầu.
Phân tích chuyên sâu mã cổ phiếu **{ticker}** dựa trên dữ liệu sau:

{data_block}

## Yêu cầu:
1. **Định giá (Valuation)**: P/E, P/B so với ngành — rẻ hay đắt?
2. **Điểm mạnh & Điểm yếu** của cổ phiếu này
3. **Tín hiệu kỹ thuật**: nhận định từ khối lượng và xu hướng giá
4. **Khuyến nghị**: MUA / NẮM GIỮ / BÁN + lý do
5. **Rủi ro** cần lưu ý
{follow_up}

**Ngôn ngữ:** {lang} | **Định dạng:** Markdown có headers và bullets.
*Lưu ý: Đây là phân tích tham khảo, không phải lời khuyên đầu tư.*
""".strip()


def _build_general_prompt(query: str, lang: str) -> str:
    """Prompt cho câu hỏi thị trường chung — không cần dữ liệu real-time."""
    return f"""
Bạn là **Chuyên gia Kinh tế & Tài chính** với 20 năm kinh nghiệm.

Người dùng hỏi: **"{query}"**

Hãy trả lời theo cấu trúc:
1. Phân tích câu hỏi theo góc nhìn vĩ mô / tài chính
2. Các luận điểm chính có căn cứ
3. Kết luận thực tiễn cho nhà đầu tư cá nhân Việt Nam

**Ngôn ngữ:** {lang} | **Định dạng:** Markdown súc tích.
*Đây là phân tích tham khảo, không phải lời khuyên đầu tư.*
""".strip()


def get_ai_analysis(
    ticker:        str,
    lang:          str  = "Tiếng Việt",
    model_name:    str  = "gemini-2.0-flash",
    context:       str  = "",
    mode:          str  = "ticker",   # "ticker" | "general"
    stock_data:    dict = None,
    initial_query: str  = "",
) -> str:
    """Gọi Gemini API và trả về phân tích dạng markdown."""

    if not GENAI_AVAILABLE:
        return "❌ **Thiếu thư viện `google-genai`**. Chạy: `pip install google-genai`"

    # Lấy API key
    api_key = None
    try:
        api_key = st.secrets.get("GOOGLE_API_KEY") or st.secrets.get("google_api_key")
    except Exception:
        pass
    if not api_key:
        return (
            "❌ **Chưa cấu hình API Key**\n\n"
            "Thêm vào **Settings → Secrets** của Streamlit:\n"
            "```toml\nGOOGLE_API_KEY = \"your_key_here\"\n```\n"
            "Lấy key miễn phí: https://aistudio.google.com/"
        )

    # Build prompt
    if mode == "ticker":
        prompt = _build_ticker_prompt(
            ticker, lang,
            context if context else "Viết bài phân tích tổng quan.",
            stock_data or {}
        )
    else:
        prompt = _build_general_prompt(initial_query if initial_query else context, lang)

    # Gọi API
    try:
        client   = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model_name, contents=prompt)
        text     = response.text if hasattr(response, 'text') else str(response)
        return f"*🤖 **{model_name}***\n\n---\n\n{text}"

    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower() or "resource_exhausted" in err.lower():
            return (
                "⏳ **AI đang quá tải (Rate Limit)**\n\n"
                "Đợi 30–60 giây rồi thử lại. "
                "Hoặc chuyển sang model **Flash** để có quota cao hơn."
            )
        elif "api_key" in err.lower() or "invalid" in err.lower() or "401" in err:
            return "🔑 **API Key không hợp lệ.** Kiểm tra lại trong Streamlit Secrets."
        elif "not found" in err.lower() and "model" in err.lower():
            return (
                f"⚠️ Model `{model_name}` không khả dụng. "
                "Chuyển sang **Gemini 2.0 Flash** trong Settings."
            )
        return f"⚠️ **Lỗi AI:** {err}"
