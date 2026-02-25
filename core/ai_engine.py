"""
================================================================================
  core/ai_engine.py — v2.4 FINAL FIX + Enhanced Analysis

  ROOT CAUSE FIX:
  ✅ google-genai 1.64.0: Dùng đúng cú pháp với google.generativeai (SDK cũ)
     vì google-genai 1.x đã merge với google-generativeai.
     Cú pháp ĐÚNG cho 1.64.0:
       import google.generativeai as genai
       genai.configure(api_key=key)
       model = genai.GenerativeModel("gemini-2.0-flash")
       response = model.generate_content(prompt)
       text = response.text
  
  ENHANCED FEATURES:
  ✅ Prompt phân tích kỹ thuật từ dữ liệu chart (giá, SMA, khối lượng)
  ✅ Kết hợp dữ liệu vi mô (PE, PB, ngành) + vĩ mô (thị trường)
  ✅ Yêu cầu AI cập nhật thông tin mới nhất trong knowledge
  ✅ Phân tích xu hướng cổ phiếu toàn diện
================================================================================
"""

import streamlit as st

# ── Import đúng SDK cho google-genai 1.x ──────────────────────────────────────
# google-genai 1.x = google.generativeai (đã được merge/alias)
# Thử theo thứ tự: google.generativeai → google.genai
_SDK_MODE  = None   # "new" | "old" | None
_SDK_ERROR = None

try:
    # Thử SDK cũ trước (google-generativeai) — hoạt động trong genai 1.x
    import google.generativeai as _genai_module
    _SDK_MODE = "generativeai"
except ImportError:
    pass

if _SDK_MODE is None:
    try:
        # Thử google.genai (một số version dùng path này)
        from google import genai as _genai_module
        _SDK_MODE = "genai"
    except ImportError as e:
        _SDK_ERROR = str(e)


# ══════════════════════════════════════════════════════════════════════════════
#  BUILD PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

def _build_ticker_prompt(ticker: str, lang: str, context: str, stock_data: dict) -> str:
    """
    Prompt phân tích toàn diện:
    - Dữ liệu vi mô thực tế (giá, PE, PB, ngành)
    - Yêu cầu AI phân tích kỹ thuật + vĩ mô
    - Kết hợp thông tin thị trường trong nước và thế giới
    """
    # Format dữ liệu thực tế
    price = stock_data.get('price', 'N/A')
    vol   = stock_data.get('volume', 'N/A')
    pe    = stock_data.get('pe', 'N/A')
    pb    = stock_data.get('pb', 'N/A')
    avg_pe = stock_data.get('avg_pe', 0)
    avg_pb = stock_data.get('avg_pb', 0)
    market = stock_data.get('market', 'HOSE')
    industry = stock_data.get('industry', 'N/A')

    try:
        price_fmt = f"{float(price):,.0f} VNĐ" if price != 'N/A' else 'N/A'
        vol_fmt   = f"{int(vol):,}"             if vol   != 'N/A' else 'N/A'
    except Exception:
        price_fmt, vol_fmt = str(price), str(vol)

    # Đánh giá định giá so ngành
    valuation_comment = ""
    try:
        if pe != "N/A" and avg_pe and float(avg_pe) > 0:
            ratio = float(pe) / float(avg_pe)
            if ratio > 1.3:
                valuation_comment = f"→ P/E cao hơn TB ngành {ratio:.1f}x, cổ phiếu đang được định giá CAO"
            elif ratio < 0.7:
                valuation_comment = f"→ P/E thấp hơn TB ngành {ratio:.1f}x, cổ phiếu có thể đang UNDERVALUED"
            else:
                valuation_comment = f"→ P/E ngang bằng TB ngành ({ratio:.1f}x), định giá HỢP LÝ"
    except Exception:
        pass

    extra = f"\n\n**Câu hỏi cụ thể từ nhà đầu tư:** {context}" if (
        context and "tổng quan" not in context.lower() and len(context) > 5
    ) else ""

    return f"""Bạn là Giám đốc Phân tích Đầu tư cấp cao tại một quỹ đầu tư lớn tại Việt Nam.
Hãy phân tích TOÀN DIỆN cổ phiếu **{ticker}** niêm yết trên **{market}**.

## DỮ LIỆU THỰC TẾ HIỆN TẠI:
| Chỉ số | Giá trị | Ghi chú |
|--------|---------|---------|
| Giá hiện tại | {price_fmt} | Giá khớp lệnh mới nhất |
| Khối lượng GD | {vol_fmt} | Phiên giao dịch gần nhất |
| Ngành | {industry} | |
| P/E cổ phiếu | {pe} | {valuation_comment} |
| P/E TB ngành | {avg_pe if avg_pe else "Không có dữ liệu"} | |
| P/B cổ phiếu | {pb} | |
| P/B TB ngành | {avg_pb if avg_pb else "Không có dữ liệu"} | |

## YÊU CẦU PHÂN TÍCH:

### 1. 📊 PHÂN TÍCH KỸ THUẬT
Dựa trên dữ liệu giá và khối lượng:
- Xu hướng giá hiện tại (tăng/giảm/đi ngang)
- Tín hiệu khối lượng giao dịch (tăng/giảm bất thường?)
- Các mức hỗ trợ và kháng cự quan trọng ước tính
- Điểm vào lệnh và cắt lỗ gợi ý

### 2. 💰 PHÂN TÍCH CƠ BẢN (VI MÔ)
- Đánh giá định giá hiện tại (P/E, P/B so với ngành)
- Điểm mạnh và điểm yếu của doanh nghiệp {ticker}
- Tình hình kinh doanh gần đây (dựa trên kiến thức có sẵn)

### 3. 🌍 BỐI CẢNH VĨ MÔ & THỊ TRƯỜNG
Dựa trên kiến thức mới nhất của bạn về:
- Tình hình kinh tế Việt Nam hiện tại (tăng trưởng GDP, lạm phát, lãi suất)
- Thị trường chứng khoán VN (VN-Index xu hướng gần đây)
- Yếu tố quốc tế ảnh hưởng (Fed, kinh tế Mỹ/Trung, giá dầu...)
- Rủi ro vĩ mô cần theo dõi

### 4. 🏭 TRIỂN VỌNG NGÀNH {industry.upper()}
- Xu hướng phát triển của ngành {industry} tại Việt Nam
- Cơ hội và thách thức đặc thù của ngành này

### 5. ✅ KẾT LUẬN & KHUYẾN NGHỊ
- **Quyết định: MUA / NẮM GIỮ / BÁN** (chọn 1)
- Lý do cụ thể và rõ ràng
- Mục tiêu giá ngắn hạn (1-3 tháng) và trung hạn (6-12 tháng)
- Điều kiện để đảo ngược khuyến nghị
{extra}

**Ngôn ngữ:** {lang}
**Lưu ý:** Phân tích tham khảo, không phải lời khuyên đầu tư chính thức."""


def _build_general_prompt(query: str, lang: str) -> str:
    """Prompt cho câu hỏi thị trường chung."""
    return f"""Bạn là Chuyên gia Kinh tế và Phân tích Thị trường tại Việt Nam với 20 năm kinh nghiệm.

**Câu hỏi:** {query}

Hãy phân tích theo cấu trúc:

### 1. Phân tích tình hình hiện tại
Dựa trên kiến thức mới nhất của bạn về thị trường Việt Nam và thế giới.

### 2. Các yếu tố tác động chính
- Trong nước: chính sách tiền tệ, tài khóa, tăng trưởng kinh tế
- Quốc tế: Fed, Trung Quốc, giá hàng hóa, địa chính trị

### 3. Xu hướng và dự báo
Nhận định ngắn hạn và trung hạn.

### 4. Gợi ý chiến lược
Dành cho nhà đầu tư cá nhân tại Việt Nam.

**Ngôn ngữ:** {lang}
**Lưu ý:** Phân tích tham khảo, không phải lời khuyên đầu tư."""


# ══════════════════════════════════════════════════════════════════════════════
#  GỌI API
# ══════════════════════════════════════════════════════════════════════════════

def _call_generativeai(api_key: str, model_name: str, prompt: str) -> str:
    """
    Gọi API dùng google.generativeai (SDK hoạt động với google-genai 1.x).
    """
    _genai_module.configure(api_key=api_key)
    model    = _genai_module.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    
    # Đọc text
    if hasattr(response, 'text') and response.text:
        return response.text
    
    # Fallback: đọc từ parts
    if hasattr(response, 'candidates'):
        for cand in response.candidates:
            if hasattr(cand, 'content') and hasattr(cand.content, 'parts'):
                texts = [p.text for p in cand.content.parts if hasattr(p, 'text') and p.text]
                if texts:
                    return "\n".join(texts)
    
    raise Exception(f"Response rỗng: {str(response)[:300]}")


def _call_genai_client(api_key: str, model_name: str, prompt: str) -> str:
    """
    Gọi API dùng google.genai.Client (google-genai >= 1.0).
    """
    client   = _genai_module.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    if hasattr(response, 'text') and response.text:
        return response.text
    if hasattr(response, 'candidates'):
        for cand in response.candidates:
            if hasattr(cand, 'content') and hasattr(cand.content, 'parts'):
                texts = [p.text for p in cand.content.parts if hasattr(p, 'text') and p.text]
                if texts:
                    return "\n".join(texts)
    raise Exception(f"Response rỗng: {str(response)[:300]}")


# ══════════════════════════════════════════════════════════════════════════════
#  HÀM CHÍNH
# ══════════════════════════════════════════════════════════════════════════════

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
    Gọi Gemini API và trả về phân tích markdown toàn diện.
    Tự động thử cả 2 cú pháp SDK để tương thích mọi version.
    """

    if _SDK_MODE is None:
        return (
            "❌ **Không tìm thấy thư viện Google AI**\n\n"
            f"Lỗi: `{_SDK_ERROR}`\n\n"
            "Đảm bảo `requirements.txt` có: `google-genai>=1.0.0`"
        )

    # Lấy API key
    api_key = None
    try:
        api_key = (
            st.secrets.get("GOOGLE_API_KEY")
            or st.secrets.get("google_api_key")
            or st.secrets.get("GEMINI_API_KEY")
        )
    except Exception:
        pass

    if not api_key:
        return (
            "❌ **Chưa cấu hình Gemini API Key**\n\n"
            "**Cách thêm key trên Streamlit Cloud:**\n"
            "1. Mở app → click **⋮ (3 chấm)** góc phải → **Settings**\n"
            "2. Chọn tab **Secrets**\n"
            "3. Thêm dòng sau rồi Save:\n"
            "```toml\n"
            "GOOGLE_API_KEY = \"AIzaSy_your_key_here\"\n"
            "```\n"
            "4. **Reboot app** để áp dụng\n\n"
            "🔑 Lấy key miễn phí: https://aistudio.google.com/"
        )

    # Build prompt
    if mode == "ticker":
        prompt = _build_ticker_prompt(
            ticker, lang,
            context or "",
            stock_data or {}
        )
    else:
        prompt = _build_general_prompt(initial_query or context or "Nhận định thị trường", lang)

    # ── Gọi API với 2 phương thức, thử cái nào hoạt động ────────────────────
    call_methods = []
    
    if _SDK_MODE == "generativeai":
        call_methods = [
            ("generativeai.GenerativeModel", _call_generativeai),
            ("genai.Client",                 _call_genai_client),
        ]
    else:
        call_methods = [
            ("genai.Client",                 _call_genai_client),
            ("generativeai.GenerativeModel", _call_generativeai),
        ]

    last_error = ""
    for method_name, call_fn in call_methods:
        try:
            raw = call_fn(api_key, model_name, prompt)
            if raw and len(raw.strip()) > 10:
                return f"*🤖 Phân tích bởi **{model_name}***\n\n---\n\n{raw}"
        except Exception as e:
            last_error = str(e)
            continue

    # ── Phân loại lỗi để hiển thị thông báo hữu ích ─────────────────────────
    err = last_error.lower()
    
    if any(x in err for x in ["429", "quota", "resource_exhausted", "rate limit", "too many"]):
        return (
            "⏳ **AI đang quá tải (Quota/Rate Limit)**\n\n"
            "- Đợi **30–60 giây** rồi thử lại\n"
            "- Chuyển sang model **Gemini 2.0 Flash** (quota cao hơn Pro)\n"
            "- Gemini Free Tier giới hạn 15 requests/phút"
        )
    
    if any(x in err for x in ["api_key", "invalid", "api key", "401", "403", "unauthorized", "permission"]):
        return (
            "🔑 **API Key không hợp lệ**\n\n"
            "Kiểm tra lại `GOOGLE_API_KEY` trong Streamlit Secrets.\n"
            "Đảm bảo key chưa bị revoke tại: https://aistudio.google.com/"
        )
    
    if "not found" in err or "404" in last_error:
        return (
            f"⚠️ **Model `{model_name}` không tồn tại**\n\n"
            "Hãy chuyển sang **Gemini 2.0 Flash** trong Settings."
        )
    
    if any(x in err for x in ["network", "connection", "timeout", "connect", "ssl"]):
        return "🌐 **Lỗi kết nối mạng.** Thử lại sau vài giây."
    
    # Hiển thị lỗi raw để debug
    return (
        f"⚠️ **Lỗi khi gọi AI** (method: {_SDK_MODE})\n\n"
        f"```\n{last_error[:600]}\n```\n\n"
        "📸 Chụp màn hình lỗi này để debug."
    )
