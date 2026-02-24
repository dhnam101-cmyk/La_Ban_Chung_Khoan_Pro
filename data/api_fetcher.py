import pandas as pd
import requests
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_fixed
import random

# ==========================================
# CƠ CHẾ 1: TỰ ĐỘNG RETRY NẾU LỖI MẠNG (Tenacity)
# Nếu gọi API thất bại, tự động thử lại 3 lần, mỗi lần cách nhau 2 giây
# ==========================================
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch_primary_data(ticker):
    """
    Hàm gọi API từ nguồn chính (Ví dụ: API của sàn bản địa).
    Dev sẽ thay thế requests.get(url) thật vào đây.
    """
    # MÔ PHỎNG: Tạo xác suất 30% API chính bị sập để test tính năng dự phòng
    if random.random() < 0.3:
        raise Exception("Lỗi 500: Server nguồn chính không phản hồi!")
        
    # Nếu thành công, trả về dữ liệu (hiện đang dùng số liệu ngẫu nhiên để demo)
    return {
        "ticker": ticker,
        "price": random.randint(20000, 150000),
        "volume": random.randint(100000, 5000000),
        "pe": round(random.uniform(8.0, 25.0), 2),
        "pb": round(random.uniform(1.0, 5.0), 2),
        "source": "Nguồn Bản Địa (Primary API)"
    }

# ==========================================
# CƠ CHẾ 2: LẤY DỮ LIỆU DỰ PHÒNG (Fallback)
# ==========================================
def fetch_fallback_data(ticker):
    """
    Hàm gọi API từ nguồn phụ (Ví dụ: Yahoo Finance Quốc tế).
    Chỉ kích hoạt khi nguồn chính sập hoàn toàn.
    """
    return {
        "ticker": ticker,
        "price": random.randint(20000, 150000),
        "volume": random.randint(100000, 5000000),
        "pe": "Đang tính toán (AI)", # Xử lý lỗi N/A bằng text thân thiện
        "pb": "Đang tính toán (AI)",
        "source": "Nguồn Quốc Tế (Fallback API)"
    }

# ==========================================
# CƠ CHẾ 3: BỘ NHỚ ĐỆM (CACHE) BẢO VỆ SERVER
# ==========================================
# Cache dữ liệu trong 60 giây. Nếu user bấm "Tra cứu" liên tục trong 1 phút, 
# hệ thống lấy từ RAM ra thay vì gọi lại API.
@st.cache_data(ttl=60, show_spinner=False)
def get_stock_data(ticker):
    """
    Hàm tổng điều phối: app.py chỉ cần gọi hàm này.
    Nó sẽ lo toàn bộ logic Ưu tiên 1 -> Lỗi -> Ưu tiên 2.
    """
    try:
        data = fetch_primary_data(ticker)
        return data
    except Exception as e:
        # Ghi log lỗi ngầm cho Dev biết, không hiện lên màn hình user
        print(f"Lỗi truy xuất {ticker}: {e}. Đang chuyển nguồn...")
        return fetch_fallback_data(ticker)
