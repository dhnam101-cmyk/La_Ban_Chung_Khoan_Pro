import time
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_exponential

# Giả lập thư viện OpenAI (Dev sẽ thay bằng thư viện thật khi tích hợp API Key)
# from openai import OpenAI
# client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ==========================================
# CƠ CHẾ 1: GỌI MODEL AI CHÍNH (Kèm tự động thử lại)
# ==========================================
# Nếu AI báo lỗi (VD: Rate limit 429), thử lại tối đa 3 lần.
# Thời gian chờ sẽ tăng dần: 2s -> 4s -> 8s (wait_exponential) để tránh spam server
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def ask_ai_primary(ticker, language):
    """
    Hàm gọi Model AI chính (Ví dụ: GPT-4-turbo hoặc Claude 3.5).
    """
    # MÔ PHỎNG: Tạo xác suất 50% AI chính bị lỗi Timeout hoặc chưa nhập API Key
    import random
    if random.random() < 0.5:
        raise Exception("Lỗi 429: AI Server đang quá tải hoặc chưa cấu hình API Key!")
    
    # Nếu thành công (Trả về câu trả lời phân tích)
    time.sleep(1) # Giả lập thời gian AI "suy nghĩ"
    if language == "Tiếng Việt":
        return f"**[AI Pro - Model Chính]** Phân tích mã **{ticker}**:\n- **Kỹ thuật:** Cổ phiếu đang trong xu hướng tích lũy, đường MACD cho tín hiệu cắt lên.\n- **Vĩ mô:** Hưởng lợi từ chính sách giảm lãi suất của Fed (DXY giảm).\n- **Khuyến nghị:** Có thể mở vị thế mua thăm dò 20% tại vùng giá hiện tại."
    else:
        return f"**[AI Pro - Primary Model]** Analysis for **{ticker}**:\n- **Technical:** The stock is consolidating, MACD shows a bullish crossover.\n- **Macro:** Benefiting from Fed's rate cuts (DXY dropping).\n- **Recommendation:** Consider initiating a 20% pilot buy position at current levels."

# ==========================================
# CƠ CHẾ 2: KỊCH BẢN DỰ PHÒNG (FALLBACK)
# ==========================================
def ask_ai_fallback(ticker, language):
    """
    Hàm gọi Model AI phụ (Ví dụ: GPT-3.5) hoặc trả về mẫu phân tích mặc định 
    khi Model chính sập hoàn toàn. Đảm bảo web không bao giờ bị "chết".
    """
    if language == "Tiếng Việt":
        return f"⚠️ *Hệ thống AI chính đang quá tải. Đang sử dụng dữ liệu dự phòng:*\n\nMã **{ticker}** hiện đang tiến gần vùng hỗ trợ mạnh. Nhà đầu tư nên quan sát thêm phản ứng giá tại đường MA50 trước khi ra quyết định giải ngân."
    else:
        return f"⚠️ *Primary AI is busy. Using fallback data:*\n\nTicker **{ticker}** is approaching a strong support zone. Investors should monitor price action around the MA50 line before making allocation decisions."

# ==========================================
# CƠ CHẾ 3: TỔNG ĐIỀU PHỐI (HÀM GỌI CHÍNH TỪ GIAO DIỆN)
# ==========================================
def get_ai_analysis(ticker, language="Tiếng Việt"):
    """
    Hàm bọc ngoài cùng, app.py sẽ gọi hàm này.
    """
    try:
        # Ưu tiên 1: Cố gắng gọi AI xịn
        return ask_ai_primary(ticker, language)
    except Exception as e:
        # Nếu AI xịn sập sau 3 lần thử, tự động đẩy sang AI dự phòng
        print(f"Lỗi AI System: {e} -> Kích hoạt Fallback.")
        return ask_ai_fallback(ticker, language)
