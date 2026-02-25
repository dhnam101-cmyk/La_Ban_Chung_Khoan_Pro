"""
core/ai_engine.py — v4.1 SUBFOLDER
Google Search Grounding + GenerativeModel đúng cú pháp
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
    price=data.get("price","N/A"); vol=data.get("volume","N/A")
    pe=data.get("pe","N/A"); pb=data.get("pb","N/A")
    avg_pe=data.get("avg_pe",0) or "Chưa có"
    avg_pb=data.get("avg_pb",0) or "Chưa có"
    market=data.get("market","HOSE"); industry=data.get("industry","N/A")
    try: pf=f"{float(price):,.0f} VNĐ"; vf=f"{int(vol):,}"
    except: pf=str(price); vf=str(vol)
    val_note=""
    try:
        if pe!="N/A" and isinstance(avg_pe,(int,float)) and float(avg_pe)>0:
            r=float(pe)/float(avg_pe)
            val_note=(f" **(CAO {r:.1f}x ngành — Overvalued)**" if r>1.3 else
                      f" **(THẤP {r:.1f}x ngành — Undervalued)**" if r<0.7 else
                      f" **(Ngang ngành — Hợp lý)**")
    except: pass
    extra=(f"\n\n**Câu hỏi bổ sung:** {context}"
           if context and len(context)>5 and "tổng quan" not in context.lower() else "")

    return f"""Bạn là Giám đốc Phân tích Đầu tư tại Việt Nam với 20 năm kinh nghiệm.

## PHÂN TÍCH TOÀN DIỆN: **{ticker}** (sàn {market})

### DỮ LIỆU THỰC TẾ:
| Chỉ số | Giá trị |
|---|---|
| Giá | **{pf}** |
| Khối lượng | **{vf}** |
| Ngành | {industry} |
| P/E | {pe}{val_note} |
| P/E TB ngành | {avg_pe} |
| P/B | {pb} |
| P/B TB ngành | {avg_pb} |

---
**Hãy dùng Google Search để tìm thông tin mới nhất, sau đó phân tích:**

### 1. 📊 KỸ THUẬT (dựa trên giá {pf}, KL {vf})
- Xu hướng ngắn hạn và trung hạn
- Hỗ trợ / kháng cự ước tính
- Điểm vào lệnh và cắt lỗ

### 2. 💰 CƠ BẢN & TIN TỨC DOANH NGHIỆP
- **[Search]** Kết quả kinh doanh mới nhất của {ticker}
- **[Search]** Tin tức quan trọng {ticker} gần đây
- Đánh giá P/E={pe}, P/B={pb} so ngành {industry}

### 3. 🌍 VĨ MÔ (tìm kiếm thông tin hiện tại)
- **[Search]** Lãi suất NHNN, VN-Index hiện tại
- **[Search]** Fed Mỹ, tỷ giá USD/VND, kinh tế Trung Quốc
- **[Search]** Giá hàng hóa liên quan ngành {industry}: dầu/thép/nông sản...

### 4. 🏭 TRIỂN VỌNG NGÀNH {industry.upper() if industry!="N/A" else ""}
- **[Search]** Chính sách nhà nước với ngành {industry}
- Cơ hội và rủi ro đặc thù

### 5. ✅ KẾT LUẬN
- **MUA / NẮM GIỮ / BÁN** — lý do cụ thể
- Mục tiêu giá 1–3 tháng và 6–12 tháng
- Tỷ trọng danh mục gợi ý, điều kiện stop-loss
{extra}

Ngôn ngữ: {lang} | Định dạng: Markdown đầy đủ
*Phân tích tham khảo, không phải lời khuyên đầu tư.*"""


def _build_general_prompt(query, lang):
    return f"""Bạn là Chuyên gia Kinh tế & Thị trường Tài chính tại Việt Nam.

**Câu hỏi:** {query}

**Dùng Google Search để tìm thông tin mới nhất, sau đó trả lời:**

### 1. 📰 Tình hình hiện tại
Thông tin thực tế mới nhất tìm được từ tìm kiếm.

### 2. 🔍 Phân tích yếu tố tác động
- Trong nước: VN-Index, NHNN, GDP, lạm phát VN
- Quốc tế: Fed, Trung Quốc, USD Index, giá dầu/vàng
- Thị trường hàng hóa liên quan

### 3. 📈 Xu hướng & Dự báo
- Ngắn hạn (1–4 tuần) và trung hạn (1–3 tháng)

### 4. 💡 Gợi ý Chiến lược
- Nhóm cổ phiếu/ngành nên chú ý
- Phân bổ danh mục gợi ý

Ngôn ngữ: {lang} | Định dạng: Markdown
*Phân tích tham khảo, không phải lời khuyên đầu tư.*"""


def _call(api_key, model_name, prompt, use_search=True):
    _SDK.configure(api_key=api_key)
    if use_search:
        try:
            tool = _SDK.protos.Tool(
                google_search_retrieval=_SDK.protos.GoogleSearchRetrieval()
            )
            model = _SDK.GenerativeModel(model_name, tools=[tool])
        except Exception:
            use_search = False
    if not use_search:
        model = _SDK.GenerativeModel(model_name)

    response = model.generate_content(prompt)
    if hasattr(response, "text") and response.text:
        return response.text, use_search
    for cand in getattr(response, "candidates", []):
        parts = getattr(getattr(cand, "content", None), "parts", [])
        texts = [p.text for p in parts if getattr(p, "text", None)]
        if texts:
            return "\n".join(texts), use_search
    raise Exception(f"Response rỗng: {str(response)[:150]}")


def get_ai_analysis(ticker, lang="Tiếng Việt", model_name="gemini-2.0-flash",
                    context="", mode="ticker", stock_data=None, initial_query=""):
    if _SDK is None:
        return "❌ **Thiếu `google-generativeai`** trong requirements.txt"

    api_key = None
    try:
        api_key = (st.secrets.get("GOOGLE_API_KEY")
                   or st.secrets.get("google_api_key")
                   or st.secrets.get("GEMINI_API_KEY"))
    except Exception:
        pass
    if not api_key:
        return ("❌ **Chưa có API Key**\n\n"
                "Vào **Manage App → Settings → Secrets**:\n"
                "```toml\nGOOGLE_API_KEY = \"AIzaSy...\"\n```\n"
                "Lấy key miễn phí: https://aistudio.google.com/")

    prompt = (_build_ticker_prompt(ticker, lang, context or "", stock_data or {})
              if mode == "ticker" else
              _build_general_prompt(initial_query or context or "Nhận định thị trường", lang))

    last_err = ""
    for attempt in range(2):
        for use_search in [True, False]:
            try:
                text, searched = _call(api_key, model_name, prompt, use_search)
                if text and len(text.strip()) > 20:
                    badge = "🔍 *Google Search + AI*" if searched else "🤖 *AI*"
                    return f"{badge} | ***{model_name}***\n\n---\n\n{text}"
            except Exception as e:
                err = str(e); el = err.lower(); last_err = err
                if any(x in el for x in ["429","quota","resource_exhausted","rate"]):
                    if attempt == 0:
                        time.sleep(35); break
                    return ("⏳ **AI Rate Limit**\n\n"
                            "Gemini Free Tier hết quota tạm thời.\n"
                            "- Đợi **1–2 phút** rồi nhấn 🔄 Thử lại\n"
                            "- Flash: 15 req/phút, 1,500 req/ngày\n"
                            "- Nếu vẫn lỗi → tạo API key mới: https://aistudio.google.com/")
                if any(x in el for x in ["api_key","invalid","401","403","unauthorized"]):
                    return "🔑 **API Key không hợp lệ.** Kiểm tra Streamlit Secrets."
                if "not found" in el or "404" in err:
                    model_name = "gemini-1.5-flash"; continue
                if any(x in el for x in ["tool","grounding","search","function"]):
                    continue  # Thử lại không có search
                last_err = err; continue

    return f"⚠️ **Lỗi AI:**\n```\n{last_err[:400]}\n```\nĐợi 1–2 phút rồi nhấn 🔄 Thử lại."
