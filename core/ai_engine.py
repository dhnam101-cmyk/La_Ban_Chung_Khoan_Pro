"""
core/ai_engine.py — v8.0
Đã nâng cấp lên thư viện google.genai mới nhất.
Hướng dẫn rõ cách cập nhật API key mới vào Streamlit Secrets.
Auto-retry 1 lần sau 35s khi rate limit.
"""
import streamlit as st
import time

HAS_GENAI = False
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    pass


def _build_ticker_prompt(ticker, lang, context, data):
    price    = data.get("price", "N/A")
    vol      = data.get("volume", "N/A")
    pe       = data.get("pe", "N/A")
    pb       = data.get("pb", "N/A")
    avg_pe   = data.get("avg_pe", 0) or "Chưa có"
    avg_pb   = data.get("avg_pb", 0) or "Chưa có"
    market   = data.get("market", "HOSE")
    industry = data.get("industry", "N/A")
    eps      = data.get("eps", "N/A")
    bvps     = data.get("bvps", "N/A")
    roe      = data.get("roe", "N/A")
    mc       = data.get("market_cap", "N/A")

    try: pf = f"{float(price):,.0f} VNĐ"
    except: pf = str(price)
    try: vf = f"{int(vol):,}"
    except: vf = str(vol)
    try: mc_f = f"{float(mc):,.2f} tỷ đ"
    except: mc_f = str(mc)

    val_note = ""
    try:
        if pe != "N/A" and isinstance(avg_pe, (int, float)) and float(avg_pe) > 0:
            r = float(pe) / float(avg_pe)
            val_note = (f" **(CAO {r:.1f}x ngành — Overvalued)**" if r > 1.3 else
                        f" **(THẤP {r:.1f}x ngành — Undervalued)**" if r < 0.7 else
                        f" **(Ngang ngành — Hợp lý)**")
    except: pass

    extra = (f"\n\n**❓ Câu hỏi bổ sung:** {context}"
             if context and len(context) > 5 and "tổng quan" not in context.lower() else "")

    return f"""Bạn là Giám đốc Phân tích Đầu tư tại Việt Nam, 20 năm kinh nghiệm.

## PHÂN TÍCH TOÀN DIỆN: **{ticker}** (sàn {market})

### 📊 DỮ LIỆU THỰC TẾ:
| Chỉ số | Giá trị |
|---|---|
| 💰 Giá hiện tại | **{pf}** |
| 📊 Khối lượng GD | {vf} |
| 🏭 Ngành | {industry} |
| 💵 EPS | {eps} nghìn đ |
| 📈 P/E | {pe}{val_note} |
| 📈 P/E TB ngành | {avg_pe} |
| 📉 P/B | {pb} |
| 📉 P/B TB ngành | {avg_pb} |
| 📚 BVPS | {bvps} nghìn đ |
| 💹 ROE | {roe}% |
| 🏢 Vốn hóa | {mc_f} |

---
**🔍 Dùng Google Search tìm thông tin mới nhất, sau đó phân tích:**

### 1. 📊 KỸ THUẬT
- Xu hướng ngắn/trung hạn dựa trên giá {pf}
- Vùng hỗ trợ và kháng cự quan trọng
- Điểm vào lệnh và mức cắt lỗ gợi ý

### 2. 💰 CƠ BẢN & TIN TỨC
- **[Search]** Kết quả kinh doanh mới nhất của {ticker}
- **[Search]** Tin tức quan trọng về {ticker} gần đây
- Đánh giá P/E={pe}, P/B={pb}, ROE={roe}% so ngành {industry}

### 3. 🌍 VĨ MÔ (tìm thông tin hiện tại)
- **[Search]** Lãi suất NHNN, tăng trưởng GDP VN, lạm phát
- **[Search]** Fed Mỹ, USD/VND, kinh tế Trung Quốc
- **[Search]** Giá dầu, vàng, hàng hóa liên quan ngành {industry}

### 4. 🏭 TRIỂN VỌNG NGÀNH {industry.upper() if industry != "N/A" else ""}
- **[Search]** Chính sách nhà nước, xu hướng ngành {industry} tại VN
- Vị thế cạnh tranh của {ticker}

### 5. ✅ KẾT LUẬN
- **MUA / NẮM GIỮ / BÁN** — lý do cụ thể, dẫn chứng
- Mục tiêu giá 1–3 tháng và 6–12 tháng
- Tỷ trọng danh mục gợi ý & mức stop-loss
{extra}

**Ngôn ngữ:** {lang} | **Format:** Markdown đầy đủ với emoji
*⚠️ Phân tích tham khảo, không phải lời khuyên đầu tư.*"""


def _build_general_prompt(query, lang):
    return f"""Bạn là Chuyên gia Kinh tế & Thị trường Tài chính Việt Nam.

**Câu hỏi:** {query}

**🔍 Dùng Google Search tìm thông tin mới nhất, phân tích:**

### 1. 📰 Tình hình hiện tại (thông tin thực tế mới nhất)
### 2. 🔍 Các yếu tố tác động
- Trong nước: VN-Index, NHNN, GDP, lạm phát
- Quốc tế: Fed, Trung Quốc, USD, giá dầu/vàng
- Hàng hóa: dầu thô, thép, nông sản liên quan
### 3. 📈 Xu hướng & Dự báo (ngắn + trung hạn)
### 4. 💡 Gợi ý chiến lược cho nhà đầu tư VN

**Ngôn ngữ:** {lang} | **Format:** Markdown
*⚠️ Phân tích tham khảo, không phải lời khuyên đầu tư.*"""


def _call(api_key, model_name, prompt, use_search=True):
    client = genai.Client(api_key=api_key)
    
    config = None
    if use_search:
        try:
            # Khởi tạo công cụ Google Search cho genai SDK mới
            google_search_tool = types.Tool(
                google_search=types.GoogleSearch()
            )
            config = types.GenerateContentConfig(
                tools=[google_search_tool]
            )
        except:
            use_search = False

    if config:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
    else:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )

    text = ""
    if hasattr(response, "text") and response.text:
        text = response.text

    if not text or len(text.strip()) < 10:
        raise Exception(f"Response rỗng: {str(response)[:100]}")
        
    return text, use_search


def get_ai_analysis(ticker, lang="Tiếng Việt", model_name="gemini-2.0-flash",
                    context="", mode="ticker", stock_data=None, initial_query=""):
    if not HAS_GENAI:
        return "❌ **Thiếu `google-genai`** trong `requirements.txt`. Vui lòng cập nhật thư viện."

    # Lấy API key từ Secrets
    api_key = None
    try:
        api_key = (st.secrets.get("GOOGLE_API_KEY")
                   or st.secrets.get("google_api_key")
                   or st.secrets.get("GEMINI_API_KEY"))
    except:
        pass

    if not api_key:
        return """❌ **Chưa có API Key trong Streamlit Secrets**

**Cách thêm / cập nhật key mới:**
1. Vào trang app Streamlit → **⋮ (3 chấm)** → **Settings**
2. Chọn tab **Secrets**
3. Thêm / sửa:
GOOGLE_API_KEY = "AIzaSy...key_mới_của_bạn..."

4. Nhấn **Save** → App tự **Reboot**
5. Sau khi reboot xong → thử lại

Lấy key miễn phí: [https://aistudio.google.com/](https://aistudio.google.com/)"""

    prompt = (_build_ticker_prompt(ticker, lang, context or "", stock_data or {})
              if mode == "ticker" else
              _build_general_prompt(initial_query or context or "Nhận định thị trường", lang))

    last_err = ""
    for attempt in range(2):
        for use_search in [True, False]:
            try:
                text, searched = _call(api_key, model_name, prompt, use_search)
                badge = "🔍 *Google Search + AI*" if searched else "🤖 *AI*"
                return f"{badge} | ***{model_name}***\n\n---\n\n{text}"
            except Exception as e:
                err = str(e); el = err.lower(); last_err = err

                if any(x in el for x in ["429", "quota", "resource_exhausted", "rate"]):
                    if attempt == 0:
                        time.sleep(35)
                        break  # Thử lại vòng attempt=1
                    return (
                        "⏳ **AI Rate Limit — Hết quota tạm thời**\n\n"
                        "**Nguyên nhân thường gặp:**\n"
                        "- Gọi API quá nhiều lần liên tiếp\n"
                        "- Key mới tạo nhưng **chưa cập nhật vào Streamlit Secrets**\n\n"
                        "**Cách fix:**\n"
                        "1. Vào app → **⋮** → **Settings** → **Secrets**\n"
                        "2. Cập nhật GOOGLE_API_KEY = \"key_mới\"\n"
                        "3. **Save** → đợi app reboot\n"
                        "4. Đợi thêm **1–2 phút** rồi nhấn 🔄 Thử lại\n\n"
                        "Flash miễn phí: 15 req/phút, 1,500 req/ngày\n"
                        "Tạo key mới: [https://aistudio.google.com/](https://aistudio.google.com/)"
                    )

                if any(x in el for x in ["api_key", "invalid", "401", "403", "unauthorized"]):
                    return (
                        "🔑 **API Key không hợp lệ hoặc bị thu hồi**\n\n"
                        "**Cách fix:**\n"
                        "1. Vào [https://aistudio.google.com/](https://aistudio.google.com/) → tạo key mới\n"
                        "2. Vào Streamlit → **⋮** → **Settings** → **Secrets**\n"
                        "3. Cập nhật GOOGLE_API_KEY = \"key_mới\"\n"
                        "4. **Save** → đợi app reboot"
                    )

                if "not found" in el or "404" in err:
                    model_name = "gemini-1.5-flash"
                    continue

                if any(x in el for x in ["network", "timeout", "connect", "ssl"]):
                    return "🌐 **Lỗi kết nối mạng.** Thử lại sau 10 giây."

                if any(x in el for x in ["tool", "grounding", "search", "function"]):
                    continue  # Thử lại không có search

                last_err = err
                continue

    return (f"⚠️ **Lỗi không xác định:**\n{last_err[:300]}\n\n"
            "Đợi 1–2 phút rồi nhấn 🔄 Thử lại.")
