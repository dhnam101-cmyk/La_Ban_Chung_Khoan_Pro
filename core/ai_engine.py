"""
================================================================================
  core/ai_engine.py — Tích hợp Google Gemini AI
  
  ROOT CAUSE FIX v2.3:
  ✅ google-genai 1.x: không còn dùng Client().models.generate_content()
     → Phải dùng: genai.GenerativeModel(model).generate_content(prompt)
     HOẶC: client.models.generate_content(model=..., contents=...)
     Cú pháp đúng cho 1.64.0:
       from google import genai
       client = genai.Client(api_key=key)
       response = client.models.generate_content(
           model="gemini-2.0-flash",
           contents="prompt here"       ← contents là string hoặc list, KHÔNG phải dict
       )
       text = response.text             ← .text vẫn hoạt động trong 1.x
  
  ✅ Pin version trong requirements.txt để tránh breaking change tương lai
  ✅ Debug log rõ ràng để dễ trace lỗi
================================================================================
"""

import streamlit as st

# ── Import SDK ────────────────────────────────────────────────────────────────
GENAI_CLIENT = None
GENAI_ERROR  = None

try:
    from google import genai as _genai
    # Test xem import có hoạt động không
    _test = _genai.Client
    GENAI_CLIENT = _genai
except Exception as e:
    GENAI_ERROR = str(e)


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
Dữ liệu thực tế:
- Giá hiện tại: {price_fmt}
- Khối lượng:   {vol_fmt}
- Sàn niêm yết: {stock_data.get('market', 'N/A')}
- Ngành:        {stock_data.get('industry', 'N/A')}
- P/E cổ phiếu: {stock_data.get('pe', 'N/A')} | P/E TB ngành: {stock_data.get('avg_pe', 'N/A')}
- P/B cổ phiếu: {stock_data.get('pb', 'N/A')} | P/B TB ngành: {stock_data.get('avg_pb', 'N/A')}
"""

    extra = f"\n\nCâu hỏi bổ sung: {context}" if (context and "tổng quan" not in context.lower()) else ""

    return f"""Bạn là Giám đốc Phân tích Đầu tư tại quỹ đầu tư hàng đầu.
Hãy phân tích mã cổ phiếu {ticker}.

{data_block}

Trình bày theo cấu trúc:
1. Định giá (Valuation): P/E, P/B so với ngành — đắt hay rẻ?
2. Điểm mạnh & Điểm yếu của cổ phiếu
3. Tín hiệu kỹ thuật: nhận định từ khối lượng và xu hướng giá
4. Khuyến nghị: MUA / NẮM GIỮ / BÁN + lý do rõ ràng
5. Rủi ro cần lưu ý
{extra}

Ngôn ngữ trả lời: {lang}
Định dạng: Markdown với headers và bullet points.
Lưu ý cuối: đây là phân tích tham khảo, không phải lời khuyên đầu tư chính thức."""


def _build_general_prompt(query: str, lang: str) -> str:
    """Prompt cho câu hỏi thị trường chung."""
    return f"""Bạn là Chuyên gia Kinh tế và Tài chính với 20 năm kinh nghiệm.

Câu hỏi từ nhà đầu tư: {query}

Hãy trả lời theo cấu trúc:
1. Phân tích câu hỏi theo góc nhìn vĩ mô và tài chính
2. Các luận điểm chính có căn cứ
3. Kết luận và gợi ý thực tiễn cho nhà đầu tư cá nhân tại Việt Nam

Ngôn ngữ trả lời: {lang}
Định dạng: Markdown súc tích nhưng đầy đủ thông tin.
Lưu ý: đây là phân tích tham khảo, không phải lời khuyên đầu tư."""


def get_ai_analysis(
    ticker:        str,
    lang:          str  = "Tiếng Việt",
    model_name:    str  = "gemini-2.0-flash",
    context:       str  = "",
    mode:          str  = "ticker",
    stock_data:    dict = None,
    initial_query: str  = "",
) -> str:
    """
    Gọi Gemini API và trả về phân tích dạng markdown.
    Tương thích google-genai 1.x (bao gồm 1.64.0).
    """

    # Kiểm tra SDK
    if GENAI_CLIENT is None:
        return (
            f"❌ **Không load được thư viện google-genai**\n\n"
            f"Lỗi: `{GENAI_ERROR}`\n\n"
            "Kiểm tra `requirements.txt` có dòng: `google-genai>=1.0.0`"
        )

    # Lấy API key
    api_key = None
    try:
        secrets = st.secrets
        api_key = (
            secrets.get("GOOGLE_API_KEY")
            or secrets.get("google_api_key")
            or secrets.get("GEMINI_API_KEY")
        )
    except Exception:
        pass

    if not api_key:
        return (
            "❌ **Chưa cấu hình API Key**\n\n"
            "Vào **Manage App → Settings → Secrets** trên Streamlit Cloud, thêm:\n"
            "```toml\n"
            "GOOGLE_API_KEY = \"AIzaSy...\"\n"
            "```\n"
            "Lấy key miễn phí tại: https://aistudio.google.com/"
        )

    # Build prompt
    if mode == "ticker":
        prompt = _build_ticker_prompt(
            ticker, lang,
            context or "Viết phân tích tổng quan.",
            stock_data or {}
        )
    else:
        prompt = _build_general_prompt(initial_query or context or ticker, lang)

    # ── Gọi API với cú pháp chính xác của google-genai 1.x ───────────────────
    try:
        client = GENAI_CLIENT.Client(api_key=api_key)

        # Cú pháp đúng cho google-genai >= 1.0.0:
        # - contents: str (prompt đơn giản) hoặc list[str]
        # - model: string tên model
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,          # ← string, không phải dict
        )

        # Đọc text từ response (1.x vẫn có .text)
        result = None
        if hasattr(response, 'text') and response.text:
            result = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            # Fallback: đọc từ candidates nếu .text không có
            parts = []
            for cand in response.candidates:
                if hasattr(cand, 'content') and hasattr(cand.content, 'parts'):
                    for part in cand.content.parts:
                        if hasattr(part, 'text') and part.text:
                            parts.append(part.text)
            result = "\n".join(parts) if parts else None

        if result:
            return f"*🤖 Phân tích bởi **{model_name}***\n\n---\n\n{result}"
        else:
            return f"⚠️ **AI trả về kết quả rỗng.** Response: `{str(response)[:200]}`"

    except Exception as e:
        err_str = str(e)
        err_low = err_str.lower()

        # Rate limit / Quota
        if any(x in err_low for x in ["429", "quota", "resource_exhausted", "rate"]):
            return (
                "⏳ **AI đang quá tải (Rate Limit)**\n\n"
                "Vui lòng đợi 30–60 giây rồi thử lại.\n"
                "> 💡 Model **Flash** có quota cao hơn **Pro**, hãy chuyển sang Flash."
            )

        # API Key lỗi
        if any(x in err_low for x in ["api_key", "invalid", "unauthorized", "401", "403", "api key"]):
            return (
                "🔑 **API Key không hợp lệ hoặc hết hạn**\n\n"
                "Kiểm tra lại `GOOGLE_API_KEY` trong Streamlit Secrets.\n"
                "Đảm bảo key còn hiệu lực tại: https://aistudio.google.com/"
            )

        # Model không tìm thấy
        if "not found" in err_low or "404" in err_str:
            return (
                f"⚠️ **Model `{model_name}` không khả dụng**\n\n"
                "Hãy chuyển sang **Gemini 2.0 Flash** trong phần Cấu hình AI."
            )

        # Lỗi mạng
        if any(x in err_low for x in ["network", "connection", "timeout", "connect"]):
            return "🌐 **Lỗi kết nối mạng.** Kiểm tra kết nối internet và thử lại."

        # Lỗi khác — hiển thị chi tiết để dễ debug
        return (
            f"⚠️ **Lỗi AI không xác định**\n\n"
            f"```\n{err_str[:500]}\n```\n\n"
            "Hãy chụp màn hình lỗi này và báo cáo."
        )
