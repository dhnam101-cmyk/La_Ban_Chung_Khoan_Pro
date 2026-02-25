"""
================================================================================
  core/ai_engine.py — v2.5 DEFINITIVE FIX

  LỖI: module 'google.generativeai' has no attribute 'Client'
  
  NGUYÊN NHÂN: Code cũ cố dùng .Client() cho cả 2 module nhưng:
    - google.generativeai  → KHÔNG có Client → dùng GenerativeModel()
    - google.genai         → CÓ Client       → dùng Client()
  
  FIX: Tách hẳn 2 path, mỗi module dùng đúng cú pháp của nó.
  Thứ tự ưu tiên:
    1. google.generativeai.GenerativeModel (SDK cũ, tương thích rộng nhất)
    2. google.genai.Client (SDK mới 1.x)
================================================================================
"""

import streamlit as st

# ── Detect SDK khả dụng ───────────────────────────────────────────────────────
_GENAI_OLD   = None   # google.generativeai
_GENAI_NEW   = None   # google.genai (Client-based)

try:
    import google.generativeai as _tmp
    # Kiểm tra có GenerativeModel không (cú pháp cũ đúng)
    if hasattr(_tmp, 'GenerativeModel'):
        _GENAI_OLD = _tmp
except Exception:
    pass

try:
    from google import genai as _tmp2
    # Kiểm tra có Client không (cú pháp mới)
    if hasattr(_tmp2, 'Client'):
        _GENAI_NEW = _tmp2
except Exception:
    pass


# ══════════════════════════════════════════════════════════════════════════════
#  BUILD PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

def _build_ticker_prompt(ticker: str, lang: str, context: str, stock_data: dict) -> str:
    price    = stock_data.get('price', 'N/A')
    vol      = stock_data.get('volume', 'N/A')
    pe       = stock_data.get('pe', 'N/A')
    pb       = stock_data.get('pb', 'N/A')
    avg_pe   = stock_data.get('avg_pe', 0)
    avg_pb   = stock_data.get('avg_pb', 0)
    market   = stock_data.get('market', 'HOSE')
    industry = stock_data.get('industry', 'N/A')

    try:
        price_fmt = f"{float(price):,.0f} VNĐ" if price != 'N/A' else 'N/A'
        vol_fmt   = f"{int(vol):,}"             if vol   != 'N/A' else 'N/A'
    except Exception:
        price_fmt, vol_fmt = str(price), str(vol)

    # Nhận xét định giá tự động
    valuation = ""
    try:
        if pe != "N/A" and avg_pe and float(avg_pe) > 0:
            r = float(pe) / float(avg_pe)
            if r > 1.3:
                valuation = f"(CAO hơn TB ngành {r:.1f}x — có thể đang Overvalued)"
            elif r < 0.7:
                valuation = f"(THẤP hơn TB ngành {r:.1f}x — có thể Undervalued)"
            else:
                valuation = f"(Ngang TB ngành {r:.1f}x — định giá hợp lý)"
    except Exception:
        pass

    extra = f"\n\n**Câu hỏi bổ sung:** {context}" if context and len(context) > 5 and "tổng quan" not in context.lower() else ""

    return f"""Bạn là Giám đốc Phân tích Đầu tư cấp cao tại Việt Nam.
Phân tích TOÀN DIỆN cổ phiếu **{ticker}** (sàn {market}).

## DỮ LIỆU THỰC TẾ:
- Giá hiện tại:  {price_fmt}
- Khối lượng GD: {vol_fmt}
- Ngành:         {industry}
- P/E: {pe} {valuation} | P/E TB ngành: {avg_pe if avg_pe else "N/A"}
- P/B: {pb} | P/B TB ngành: {avg_pb if avg_pb else "N/A"}

## YÊU CẦU PHÂN TÍCH 5 PHẦN:

### 1. 📊 PHÂN TÍCH KỸ THUẬT
- Xu hướng giá ngắn hạn và trung hạn
- Tín hiệu từ khối lượng giao dịch
- Mức hỗ trợ và kháng cự quan trọng
- Điểm vào/thoát lệnh gợi ý

### 2. 💰 PHÂN TÍCH CƠ BẢN (VI MÔ)
- Đánh giá định giá P/E, P/B so với ngành
- Điểm mạnh và rủi ro của {ticker}
- Kết quả kinh doanh gần đây

### 3. 🌍 BỐI CẢNH VĨ MÔ
Dựa trên kiến thức mới nhất về:
- Kinh tế Việt Nam (GDP, lạm phát, lãi suất)
- VN-Index xu hướng hiện tại
- Yếu tố quốc tế (Fed, Trung Quốc, giá hàng hóa)

### 4. 🏭 TRIỂN VỌNG NGÀNH {industry.upper()}
- Xu hướng và cơ hội của ngành {industry} tại VN

### 5. ✅ KẾT LUẬN
- **Quyết định: MUA / NẮM GIỮ / BÁN**
- Mục tiêu giá ngắn hạn (1-3 tháng)
- Điều kiện đảo ngược khuyến nghị
{extra}

Ngôn ngữ: {lang} | Định dạng: Markdown.
*Phân tích tham khảo, không phải lời khuyên đầu tư.*"""


def _build_general_prompt(query: str, lang: str) -> str:
    return f"""Bạn là Chuyên gia Kinh tế và Phân tích Thị trường tài chính Việt Nam.

**Câu hỏi:** {query}

Hãy phân tích theo cấu trúc:
1. **Tình hình hiện tại** — dựa trên kiến thức mới nhất
2. **Yếu tố tác động** — trong nước và quốc tế
3. **Xu hướng & dự báo** — ngắn và trung hạn
4. **Gợi ý chiến lược** — cho nhà đầu tư cá nhân VN

Ngôn ngữ: {lang} | Định dạng: Markdown.
*Phân tích tham khảo, không phải lời khuyên đầu tư.*"""


# ══════════════════════════════════════════════════════════════════════════════
#  GỌI API — TÁCH RIÊNG 2 CÚ PHÁP
# ══════════════════════════════════════════════════════════════════════════════

def _call_old_sdk(api_key: str, model_name: str, prompt: str) -> str:
    """
    google.generativeai — cú pháp: GenerativeModel().generate_content()
    KHÔNG có Client trong module này.
    """
    _GENAI_OLD.configure(api_key=api_key)
    model    = _GENAI_OLD.GenerativeModel(model_name)
    response = model.generate_content(prompt)

    if hasattr(response, 'text') and response.text:
        return response.text

    # Fallback: đọc từ candidates
    if hasattr(response, 'candidates'):
        parts = []
        for cand in response.candidates:
            if hasattr(cand, 'content') and hasattr(cand.content, 'parts'):
                parts += [p.text for p in cand.content.parts if hasattr(p, 'text') and p.text]
        if parts:
            return "\n".join(parts)

    raise Exception(f"Response rỗng. Raw: {str(response)[:200]}")


def _call_new_sdk(api_key: str, model_name: str, prompt: str) -> str:
    """
    google.genai — cú pháp: Client().models.generate_content()
    Module này CÓ Client.
    """
    client   = _GENAI_NEW.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )

    if hasattr(response, 'text') and response.text:
        return response.text

    if hasattr(response, 'candidates'):
        parts = []
        for cand in response.candidates:
            if hasattr(cand, 'content') and hasattr(cand.content, 'parts'):
                parts += [p.text for p in cand.content.parts if hasattr(p, 'text') and p.text]
        if parts:
            return "\n".join(parts)

    raise Exception(f"Response rỗng. Raw: {str(response)[:200]}")


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

    if _GENAI_OLD is None and _GENAI_NEW is None:
        return (
            "❌ **Không tìm thấy thư viện Google AI**\n\n"
            "Đảm bảo `requirements.txt` có:\n"
            "```\ngoogle-generativeai>=0.8.0\n```"
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
            "**Cách thêm key:**\n"
            "1. Click **⋮** góc phải app → **Settings** → **Secrets**\n"
            "2. Thêm dòng:\n"
            "```toml\nGOOGLE_API_KEY = \"AIzaSy...\"\n```\n"
            "3. Save → **Reboot app**\n\n"
            "Lấy key miễn phí: https://aistudio.google.com/"
        )

    # Build prompt
    if mode == "ticker":
        prompt = _build_ticker_prompt(ticker, lang, context or "", stock_data or {})
    else:
        prompt = _build_general_prompt(initial_query or context or "Nhận định thị trường", lang)

    # ── Thử SDK cũ trước (GenerativeModel) → SDK mới (Client) ────────────────
    last_error = ""

    # Ưu tiên SDK cũ vì tương thích rộng hơn
    if _GENAI_OLD is not None:
        try:
            text = _call_old_sdk(api_key, model_name, prompt)
            if text and len(text.strip()) > 10:
                return f"*🤖 Phân tích bởi **{model_name}***\n\n---\n\n{text}"
        except Exception as e:
            last_error = str(e)

    # Fallback: SDK mới (Client-based)
    if _GENAI_NEW is not None:
        try:
            text = _call_new_sdk(api_key, model_name, prompt)
            if text and len(text.strip()) > 10:
                return f"*🤖 Phân tích bởi **{model_name}***\n\n---\n\n{text}"
        except Exception as e:
            last_error = str(e)

    # ── Phân loại lỗi ─────────────────────────────────────────────────────────
    err = last_error.lower()

    if any(x in err for x in ["429", "quota", "resource_exhausted", "rate"]):
        return (
            "⏳ **AI đang quá tải (Rate Limit)**\n\n"
            "Đợi 30–60 giây rồi thử lại.\n"
            "> Flash có quota cao hơn Pro."
        )
    if any(x in err for x in ["api_key", "invalid", "401", "403", "unauthorized", "api key"]):
        return "🔑 **API Key không hợp lệ.** Kiểm tra lại trong Streamlit Secrets."
    if "not found" in err or "404" in last_error:
        return f"⚠️ **Model `{model_name}` không tồn tại.** Chuyển sang Gemini 2.0 Flash."
    if any(x in err for x in ["network", "timeout", "connect", "ssl"]):
        return "🌐 **Lỗi kết nối mạng.** Thử lại sau vài giây."

    return (
        f"⚠️ **Lỗi AI**\n\n"
        f"```\n{last_error[:500]}\n```"
    )
