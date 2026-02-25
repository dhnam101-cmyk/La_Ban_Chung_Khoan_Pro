"""
================================================================================
  ai_engine.py — Tích hợp Google Gemini AI
  
  Fixes:
  ✅ Luồng truyền dữ liệu stock vào prompt rõ ràng
  ✅ Xử lý lỗi 429 (quota) + lỗi API key
  ✅ Phân biệt prompt cho ticker vs general query
  ✅ Tương thích google-genai SDK mới nhất
================================================================================
"""

import streamlit as st

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def _build_ticker_prompt(ticker: str, lang: str, context: str, stock_data: dict) -> str:
    """
    Xây dựng prompt phân tích mã cổ phiếu cụ thể.
    Truyền dữ liệu thực tế (giá, P/E, P/B...) vào prompt để AI phân tích chính xác.
    """
    # Chuyển dict dữ liệu thành chuỗi có cấu trúc
    data_summary = ""
    if stock_data:
        data_summary = f"""
## Dữ liệu thực tế (Real-time):
- **Giá hiện tại:** {stock_data.get('price', 'N/A'):,}
- **Khối lượng giao dịch:** {stock_data.get('volume', 'N/A'):,}
- **Sàn niêm yết:** {stock_data.get('market', 'N/A')}
- **Ngành:** {stock_data.get('industry', 'N/A')}
- **P/E cổ phiếu:** {stock_data.get('pe', 'N/A')} | **P/E trung bình ngành:** {stock_data.get('avg_pe', 'N/A')}
- **P/B cổ phiếu:** {stock_data.get('pb', 'N/A')} | **P/B trung bình ngành:** {stock_data.get('avg_pb', 'N/A')}
"""
    
    prompt = f"""
Bạn là **Giám đốc Phân tích Đầu tư** tại một quỹ đầu tư hàng đầu. 
Hãy phân tích chuyên sâu mã cổ phiếu **{ticker}** dựa trên dữ liệu cung cấp.

{data_summary}

## Yêu cầu phân tích:
Dựa trên dữ liệu trên, hãy trình bày:

1. **Đánh giá Định giá (Valuation)**: So sánh P/E, P/B với ngành — mã này đang rẻ hay đắt?
2. **Điểm mạnh & Điểm yếu**: Phân tích cơ bản ngắn gọn
3. **Tín hiệu Kỹ thuật**: Nhận định dựa trên khối lượng giao dịch và xu hướng giá
4. **Khuyến nghị**: MUA / NẮM GIỮ / BÁN — kèm lý do rõ ràng
5. **Rủi ro cần lưu ý**

{f"**Câu hỏi bổ sung của nhà đầu tư:** {context}" if context and context != "Viết bài phân tích điểm mạnh, điểm yếu của mã này." else ""}

**Ngôn ngữ trả lời:** {lang}  
**Định dạng:** Markdown, rõ ràng, có bullets và headers.
*Lưu ý: Đây là phân tích tham khảo, không phải lời khuyên đầu tư chính thức.*
"""
    return prompt.strip()


def _build_general_prompt(query: str, lang: str) -> str:
    """
    Xây dựng prompt cho câu hỏi thị trường chung.
    KHÔNG cần dữ liệu real-time — AI trả lời từ kiến thức nền.
    """
    return f"""
Bạn là **Chuyên gia Kinh tế & Tài chính** với 20 năm kinh nghiệm.
Người dùng hỏi: **"{query}"**

Hãy trả lời bằng cách:
1. Phân tích câu hỏi theo góc nhìn tài chính/vĩ mô
2. Đưa ra các luận điểm có căn cứ
3. Kết luận thực tiễn cho nhà đầu tư cá nhân Việt Nam

**Ngôn ngữ trả lời:** {lang}  
**Định dạng:** Markdown, súc tích nhưng đầy đủ thông tin.
*Đây là phân tích tham khảo, không phải lời khuyên đầu tư.*
""".strip()


def get_ai_analysis(
    ticker: str,
    lang: str = "Tiếng Việt",
    model_name: str = "gemini-2.0-flash",
    context: str = "",
    mode: str = "ticker",          # "ticker" hoặc "general"
    stock_data: dict = None,       # Dữ liệu thực tế từ data_fetcher
    initial_query: str = ""        # Câu hỏi ban đầu (cho mode general)
) -> str:
    """
    Hàm trung tâm gọi AI analysis.
    
    Args:
        ticker:      Mã cổ phiếu hoặc "Thị trường"
        lang:        Ngôn ngữ phản hồi
        model_name:  Tên model Gemini
        context:     Câu hỏi bổ sung từ chatbox
        mode:        "ticker" | "general"
        stock_data:  Dict dữ liệu thực tế (từ data_fetcher)
        initial_query: Câu hỏi ban đầu cho mode general
    
    Returns:
        Chuỗi markdown phân tích của AI
    """
    if not GENAI_AVAILABLE:
        return "❌ **Thiếu thư viện `google-genai`**. Chạy: `pip install google-genai`"
    
    # ── Kiểm tra API Key ──────────────────────────────────────────────────────
    api_key = None
    try:
        api_key = st.secrets.get("GOOGLE_API_KEY") or st.secrets.get("google_api_key")
    except Exception:
        pass
    
    if not api_key:
        return (
            "❌ **Chưa cấu hình API Key**\n\n"
            "Thêm key vào **Settings → Secrets** của Streamlit:\n"
            "```toml\nGOOGLE_API_KEY = \"your_key_here\"\n```\n"
            "Lấy key miễn phí tại: https://aistudio.google.com/"
        )
    
    # ── Xây dựng prompt theo mode ─────────────────────────────────────────────
    if mode == "ticker":
        query = context if context else "Viết bài phân tích tổng quan."
        prompt = _build_ticker_prompt(ticker, lang, query, stock_data or {})
    else:
        query = initial_query if initial_query else context
        prompt = _build_general_prompt(query, lang)
    
    # ── Gọi Gemini API ────────────────────────────────────────────────────────
    try:
        client   = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        
        result_text = response.text if hasattr(response, 'text') else str(response)
        return f"*🤖 Phân tích bởi **{model_name}***\n\n---\n\n{result_text}"
    
    except Exception as e:
        err = str(e)
        
        if "429" in err or "quota" in err.lower() or "resource_exhausted" in err.lower():
            return (
                "⏳ **AI đang quá tải (Rate Limit)**\n\n"
                "Gemini API đã đạt giới hạn yêu cầu. "
                "Vui lòng đợi **30–60 giây** rồi thử lại.\n\n"
                "> 💡 Tip: Dùng model **Flash** thay vì **Pro** để có quota cao hơn."
            )
        elif "api_key" in err.lower() or "invalid" in err.lower() or "401" in err:
            return (
                "🔑 **API Key không hợp lệ**\n\n"
                "Kiểm tra lại `GOOGLE_API_KEY` trong Streamlit Secrets."
            )
        elif "model" in err.lower() and "not found" in err.lower():
            return (
                f"⚠️ **Model `{model_name}` không tồn tại hoặc bạn chưa có quyền truy cập.**\n\n"
                "Thử chuyển sang **Gemini 2.0 Flash** trong Settings."
            )
        else:
            return f"⚠️ **Lỗi AI:** {err}"
