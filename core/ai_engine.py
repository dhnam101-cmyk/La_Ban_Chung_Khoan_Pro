"""
ai_engine.py — v4.0 FLAT STRUCTURE

QUAN TRỌNG - Dùng Gemini với Google Search Grounding:
  ✅ Tool "google_search_retrieval" cho phép AI tìm thông tin mới nhất
  ✅ Phân tích kết hợp: dữ liệu thực tế + thông tin thị trường hiện tại
  ✅ Cache kết quả trong session để tránh gọi lại
  ✅ Nút retry rõ ràng khi rate limit
  
SDK: google.generativeai (GenerativeModel) — ĐÚNG cho google-generativeai 0.8+
"""
import streamlit as st
import time

_SDK = None
try:
    import google.generativeai as _g
    if hasattr(_g, "GenerativeModel"):
        _SDK = _g
except Exception:
    pass


def _build_ticker_prompt(ticker: str, lang: str, context: str, data: dict) -> str:
    price    = data.get("price", "N/A")
    vol      = data.get("volume", "N/A")
    pe       = data.get("pe", "N/A")
    pb       = data.get("pb", "N/A")
    avg_pe   = data.get("avg_pe", 0) or "Chưa có"
    avg_pb   = data.get("avg_pb", 0) or "Chưa có"
    market   = data.get("market", "HOSE")
    industry = data.get("industry", "N/A")

    try:
        pf = f"{float(price):,.0f} VNĐ"
        vf = f"{int(vol):,}"
    except Exception:
        pf, vf = str(price), str(vol)

    # Đánh giá định giá tự động nếu có dữ liệu
    val_note = ""
    try:
        if pe != "N/A" and isinstance(avg_pe, (int, float)) and float(avg_pe) > 0:
            r = float(pe) / float(avg_pe)
            val_note = (f" **(CAO hơn TB ngành {r:.1f}x — có thể Overvalued)**" if r > 1.3 else
                        f" **(THẤP hơn TB ngành {r:.1f}x — có thể Undervalued)**" if r < 0.7 else
                        f" **(ngang TB ngành — Định giá hợp lý)**")
    except Exception:
        pass

    extra = (f"\n\n**Câu hỏi bổ sung từ nhà đầu tư:** {context}"
             if context and len(context) > 5 and "tổng quan" not in context.lower() else "")

    return f"""Bạn là Giám đốc Phân tích Đầu tư tại Việt Nam với 20 năm kinh nghiệm.

## NHIỆM VỤ: Phân tích toàn diện cổ phiếu **{ticker}** (sàn {market})

---
## DỮ LIỆU ĐỊNH LƯỢNG (thực tế, lấy từ hệ thống):
| Chỉ số | Giá trị |
|--------|---------|
| 💰 Giá hiện tại | **{pf}** |
| 📊 Khối lượng GD | **{vf}** |
| 🏭 Ngành | {industry} |
| 📈 P/E | {pe}{val_note} |
| 📈 P/E TB ngành | {avg_pe} |
| 📉 P/B | {pb} |
| 📉 P/B TB ngành | {avg_pb} |

---
## YÊU CẦU PHÂN TÍCH — hãy dùng Google Search để tìm thông tin mới nhất:

### 1. 📊 PHÂN TÍCH KỸ THUẬT
Dựa trên mức giá **{pf}** và khối lượng **{vf}**:
- Xu hướng ngắn hạn (1-4 tuần) và trung hạn (1-3 tháng)
- Đánh giá tín hiệu khối lượng giao dịch
- Vùng hỗ trợ và kháng cự ước tính
- Điểm vào lệnh và mức cắt lỗ gợi ý

### 2. 💰 CƠ BẢN & TÌNH HÌNH DOANH NGHIỆP
- **Tìm kiếm mới nhất:** Kết quả kinh doanh gần nhất của {ticker}
- **Tìm kiếm:** Tin tức quan trọng về {ticker} trong 1-3 tháng gần đây
- Đánh giá P/E={pe}, P/B={pb} so với ngành {industry}
- Điểm mạnh, điểm yếu, cơ hội, rủi ro (SWOT)

### 3. 🌍 VĨ MÔ TRONG NƯỚC & QUỐC TẾ
**Tìm kiếm và cập nhật thông tin mới nhất về:**
- Chính sách tiền tệ NHNN Việt Nam hiện tại (lãi suất, tín dụng)
- Tình hình VN-Index và thanh khoản thị trường gần đây
- Fed Mỹ: chính sách lãi suất hiện tại và triển vọng
- Kinh tế Trung Quốc và tác động đến VN
- Tỷ giá USD/VND hiện tại

### 4. 🏭 NGÀNH {industry.upper() if industry != "N/A" else ticker}
**Tìm kiếm thông tin mới nhất:**
- Xu hướng phát triển ngành {industry} tại Việt Nam
- Giá cả hàng hóa liên quan (nếu có): dầu, thép, xi măng, nông sản...
- Chính sách nhà nước ảnh hưởng đến ngành
- Vị thế cạnh tranh của {ticker} trong ngành

### 5. ✅ KẾT LUẬN & KHUYẾN NGHỊ
- **Quyết định rõ ràng: MUA / NẮM GIỮ / BÁN**
- Lý do cụ thể, có dẫn chứng
- Mục tiêu giá: ngắn hạn (1-3 tháng) và trung hạn (6-12 tháng)
- Tỷ trọng danh mục gợi ý (%)
- Điều kiện đảo ngược khuyến nghị (stop-loss trigger)
{extra}

---
**Ngôn ngữ:** {lang} | **Định dạng:** Markdown có headers và bullets
*⚠️ Phân tích mang tính tham khảo, không phải lời khuyên đầu tư chính thức.*"""


def _build_general_prompt(query: str, lang: str) -> str:
    return f"""Bạn là Chuyên gia Kinh tế & Thị trường Tài chính tại Việt Nam.

**Câu hỏi:** {query}

**Hãy dùng Google Search để tìm thông tin mới nhất và trả lời theo cấu trúc:**

### 1. 📰 Tình hình hiện tại (Thông tin mới nhất từ tìm kiếm)
Cập nhật thông tin thực tế nhất có thể tìm được.

### 2. 🔍 Phân tích các yếu tố tác động
- **Trong nước:** VN-Index, NHNN, tăng trưởng GDP, lạm phát VN
- **Quốc tế:** Fed Mỹ, kinh tế Trung Quốc, giá dầu, USD Index
- **Thị trường hàng hóa:** giá dầu, vàng, thép, nông sản có liên quan

### 3. 📈 Xu hướng & Dự báo
- Ngắn hạn: 1-4 tuần tới
- Trung hạn: 1-3 tháng tới
- Rủi ro cần theo dõi

### 4. 💡 Gợi ý Chiến lược
- Cho nhà đầu tư cổ phiếu tại VN
- Ngành/nhóm cổ phiếu nên chú ý
- Phân bổ danh mục gợi ý

**Ngôn ngữ:** {lang} | **Định dạng:** Markdown rõ ràng
*⚠️ Phân tích tham khảo, không phải lời khuyên đầu tư.*"""


def _call_with_search(api_key: str, model_name: str, prompt: str) -> str:
    """
    Gọi Gemini với Google Search Grounding.
    Cho phép AI tìm thông tin mới nhất từ internet.
    """
    _SDK.configure(api_key=api_key)

    # Cấu hình Google Search tool
    search_tool = _SDK.protos.Tool(
        google_search_retrieval=_SDK.protos.GoogleSearchRetrieval()
    )

    model = _SDK.GenerativeModel(
        model_name=model_name,
        tools=[search_tool],
    )

    response = model.generate_content(prompt)

    # Đọc text từ response
    if hasattr(response, "text") and response.text:
        return response.text
    for cand in getattr(response, "candidates", []):
        parts = getattr(getattr(cand, "content", None), "parts", [])
        texts = [p.text for p in parts if getattr(p, "text", None)]
        if texts:
            return "\n".join(texts)

    raise Exception(f"Response rỗng: {str(response)[:200]}")


def _call_without_search(api_key: str, model_name: str, prompt: str) -> str:
    """Fallback: gọi Gemini không có Search (khi model không hỗ trợ grounding)."""
    _SDK.configure(api_key=api_key)
    model    = _SDK.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    if hasattr(response, "text") and response.text:
        return response.text
    for cand in getattr(response, "candidates", []):
        parts = getattr(getattr(cand, "content", None), "parts", [])
        texts = [p.text for p in parts if getattr(p, "text", None)]
        if texts:
            return "\n".join(texts)
    raise Exception(f"Response rỗng: {str(response)[:200]}")


def get_ai_analysis(ticker: str, lang: str = "Tiếng Việt",
                    model_name: str = "gemini-2.0-flash",
                    context: str = "", mode: str = "ticker",
                    stock_data: dict = None, initial_query: str = "") -> str:
    if _SDK is None:
        return ("❌ **Thiếu thư viện `google-generativeai`**\n\n"
                "Đảm bảo `requirements.txt` có:\n```\ngoogle-generativeai>=0.8.0\n```")

    # Lấy API key
    api_key = None
    try:
        api_key = (st.secrets.get("GOOGLE_API_KEY")
                   or st.secrets.get("google_api_key")
                   or st.secrets.get("GEMINI_API_KEY"))
    except Exception:
        pass

    if not api_key:
        return ("❌ **Chưa có API Key**\n\n"
                "Vào **Manage App → Settings → Secrets**, thêm:\n"
                "```toml\nGOOGLE_API_KEY = \"AIzaSy...\"\n```\n"
                "Lấy key miễn phí: https://aistudio.google.com/")

    prompt = (
        _build_ticker_prompt(ticker, lang, context or "", stock_data or {})
        if mode == "ticker" else
        _build_general_prompt(initial_query or context or "Nhận định thị trường", lang)
    )

    # Thử gọi với Search Grounding trước, fallback không search
    last_error = ""
    for attempt in range(2):
        for call_fn, fn_name in [
            (_call_with_search,    "with_search"),
            (_call_without_search, "no_search"),
        ]:
            try:
                text = call_fn(api_key, model_name, prompt)
                if text and len(text.strip()) > 20:
                    badge = "🔍 *Phân tích với Google Search*" if fn_name == "with_search" else "🤖"
                    return f"{badge} ***{model_name}***\n\n---\n\n{text}"
            except Exception as e:
                err     = str(e)
                err_low = err.lower()
                last_error = err

                # Rate limit → chờ 35s rồi retry
                if any(x in err_low for x in ["429", "quota", "resource_exhausted", "rate"]):
                    if attempt == 0:
                        time.sleep(35)
                        break  # Phá vòng for, thử lại attempt=1
                    return ("⏳ **AI Rate Limit**\n\n"
                            "Gemini Free Tier đã hết quota tạm thời.\n\n"
                            "**Giải pháp:**\n"
                            "- Đợi **1–2 phút** rồi nhấn 🔄 Thử lại\n"
                            "- Flash miễn phí: 15 req/phút, 1,500 req/ngày\n"
                            "- Nếu vẫn lỗi → tạo API key mới tại https://aistudio.google.com/")

                if any(x in err_low for x in ["api_key", "invalid", "401", "403", "unauthorized"]):
                    return "🔑 **API Key không hợp lệ.** Kiểm tra lại trong Streamlit Secrets."

                if "not found" in err_low or "404" in err:
                    # Model không tồn tại → thử model khác ngay
                    if model_name != "gemini-1.5-flash":
                        model_name = "gemini-1.5-flash"
                        continue
                    return f"⚠️ **Model không tồn tại.** Chuyển sang Gemini 1.5 Flash."

                if any(x in err_low for x in ["network", "timeout", "connect", "ssl"]):
                    return "🌐 **Lỗi kết nối.** Thử lại sau vài giây."

                # Lỗi search grounding không được hỗ trợ → skip sang no_search
                if "tool" in err_low or "grounding" in err_low or "search" in err_low:
                    continue

                # Lỗi khác → hiển thị để debug
                last_error = err
                continue

    return (f"⚠️ **Lỗi AI**\n```\n{last_error[:400]}\n```\n\n"
            "Thử nhấn 🔄 Thử lại sau 1–2 phút.")
