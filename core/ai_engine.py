"""
core/ai_engine.py — v3.0
SDK: google.generativeai (GenerativeModel) — đây là cú pháp đúng.
Auto-retry 1 lần nếu rate limit (chờ 35s).
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


def _build_ticker_prompt(ticker, lang, context, data):
    price    = data.get("price", "N/A")
    vol      = data.get("volume", "N/A")
    pe       = data.get("pe", "N/A")
    pb       = data.get("pb", "N/A")
    avg_pe   = data.get("avg_pe", 0) or "N/A"
    avg_pb   = data.get("avg_pb", 0) or "N/A"
    market   = data.get("market", "HOSE")
    industry = data.get("industry", "N/A")
    try:
        pf = f"{float(price):,.0f} VNĐ"
        vf = f"{int(vol):,}"
    except Exception:
        pf, vf = str(price), str(vol)

    val_note = ""
    try:
        if pe != "N/A" and avg_pe != "N/A" and float(avg_pe) > 0:
            r = float(pe)/float(avg_pe)
            val_note = f"(PE cao hơn ngành {r:.1f}x → Overvalued)" if r>1.3 else \
                       f"(PE thấp hơn ngành {r:.1f}x → Undervalued)" if r<0.7 else \
                       f"(PE ngang ngành {r:.1f}x → Hợp lý)"
    except Exception:
        pass

    extra = f"\n\n**Câu hỏi bổ sung:** {context}" if context and len(context) > 5 and "tổng quan" not in context.lower() else ""

    return f"""Bạn là Giám đốc Phân tích Đầu tư tại Việt Nam. Phân tích TOÀN DIỆN cổ phiếu **{ticker}** (sàn {market}).

## DỮ LIỆU THỰC TẾ:
| Chỉ số | Giá trị |
|--------|---------|
| Giá hiện tại | {pf} |
| Khối lượng GD | {vf} |
| Ngành | {industry} |
| P/E | {pe} {val_note} |
| P/E TB ngành | {avg_pe} |
| P/B | {pb} |
| P/B TB ngành | {avg_pb} |

## PHÂN TÍCH (5 PHẦN):

### 1. 📊 KỸ THUẬT
- Xu hướng giá ngắn/trung hạn
- Tín hiệu khối lượng giao dịch  
- Mức hỗ trợ và kháng cự quan trọng
- Điểm vào lệnh và cắt lỗ gợi ý

### 2. 💰 CƠ BẢN (VI MÔ)
- Định giá P/E, P/B so ngành: đắt hay rẻ?
- Điểm mạnh & điểm yếu của {ticker}
- Kết quả kinh doanh gần đây

### 3. 🌍 VĨ MÔ & THỊ TRƯỜNG
Dựa trên kiến thức mới nhất:
- Kinh tế VN: GDP, lạm phát, lãi suất NHNN
- VN-Index xu hướng hiện tại
- Yếu tố quốc tế: Fed, Trung Quốc, USD/VND

### 4. 🏭 TRIỂN VỌNG NGÀNH {industry.upper() if industry != "N/A" else ""}
- Xu hướng ngành {industry} tại VN
- Cơ hội và thách thức

### 5. ✅ KẾT LUẬN
- **MUA / NẮM GIỮ / BÁN** — lý do cụ thể
- Mục tiêu giá 1–3 tháng và 6–12 tháng
- Điều kiện đảo ngược khuyến nghị
{extra}

Ngôn ngữ: {lang}. Định dạng Markdown đầy đủ.
*Lưu ý: phân tích tham khảo, không phải lời khuyên đầu tư.*"""


def _build_general_prompt(query, lang):
    return f"""Bạn là Chuyên gia Kinh tế & Tài chính tại Việt Nam với 20 năm kinh nghiệm.

**Câu hỏi:** {query}

Phân tích:
1. **Tình hình hiện tại** — dựa trên kiến thức mới nhất của bạn
2. **Yếu tố tác động** — trong nước (VN) và quốc tế
3. **Xu hướng & dự báo** — ngắn và trung hạn
4. **Gợi ý chiến lược** — cho nhà đầu tư cá nhân VN

Ngôn ngữ: {lang}. Định dạng Markdown.
*Phân tích tham khảo, không phải lời khuyên đầu tư.*"""


def _call(api_key, model_name, prompt):
    """Gọi google.generativeai.GenerativeModel — cú pháp đúng."""
    _SDK.configure(api_key=api_key)
    model    = _SDK.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    # Đọc text
    if hasattr(response, "text") and response.text:
        return response.text
    for cand in getattr(response, "candidates", []):
        parts = getattr(getattr(cand, "content", None), "parts", [])
        texts = [p.text for p in parts if getattr(p, "text", None)]
        if texts:
            return "\n".join(texts)
    raise Exception(f"Response rỗng: {str(response)[:200]}")


def get_ai_analysis(ticker, lang="Tiếng Việt", model_name="gemini-2.0-flash",
                    context="", mode="ticker", stock_data=None, initial_query=""):
    if _SDK is None:
        return (
            "❌ **Thiếu thư viện `google-generativeai`**\n\n"
            "Đảm bảo `requirements.txt` có:\n```\ngoogle-generativeai>=0.8.0\n```"
        )

    # Lấy API key
    api_key = None
    try:
        api_key = (st.secrets.get("GOOGLE_API_KEY")
                   or st.secrets.get("google_api_key")
                   or st.secrets.get("GEMINI_API_KEY"))
    except Exception:
        pass

    if not api_key:
        return (
            "❌ **Chưa có API Key**\n\n"
            "Vào **Manage App → Settings → Secrets**, thêm:\n"
            "```toml\nGOOGLE_API_KEY = \"AIzaSy...\"\n```\n"
            "Lấy key miễn phí: https://aistudio.google.com/"
        )

    prompt = (
        _build_ticker_prompt(ticker, lang, context or "", stock_data or {})
        if mode == "ticker" else
        _build_general_prompt(initial_query or context or "Nhận định thị trường", lang)
    )

    # Gọi API với auto-retry 1 lần nếu rate limit
    for attempt in range(2):
        try:
            text = _call(api_key, model_name, prompt)
            if text and len(text.strip()) > 10:
                return f"*🤖 **{model_name}***\n\n---\n\n{text}"
        except Exception as e:
            err = str(e)
            err_low = err.lower()

            # Rate limit → chờ 35s rồi thử lại 1 lần
            if any(x in err_low for x in ["429","quota","resource_exhausted","rate"]):
                if attempt == 0:
                    time.sleep(35)
                    continue
                return (
                    "⏳ **AI Rate Limit**\n\n"
                    "Gemini Free Tier đã hết quota tạm thời.\n"
                    "- Đợi **1–2 phút** rồi thử lại\n"
                    "- Hoặc chuyển sang **⚡ Gemini 2.0 Flash** (quota cao nhất)\n"
                    "- Flash miễn phí: 15 req/phút, 1500 req/ngày"
                )
            if any(x in err_low for x in ["api_key","invalid","401","403","unauthorized"]):
                return "🔑 **API Key không hợp lệ.** Kiểm tra lại trong Streamlit Secrets."
            if "not found" in err_low or "404" in err:
                return f"⚠️ **Model `{model_name}` không tồn tại.** Chuyển sang Gemini 2.0 Flash."
            if any(x in err_low for x in ["network","timeout","connect","ssl"]):
                return "🌐 **Lỗi kết nối.** Thử lại sau vài giây."
            return f"⚠️ **Lỗi AI:**\n```\n{err[:400]}\n```"

    return "⚠️ Không nhận được phản hồi từ AI."
