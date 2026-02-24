import pandas as pd
import requests
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_fixed
import random

# ==========================================
# CƠ CHẾ 1: LẤY DỮ LIỆU CHÍNH
# ==========================================
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch_primary_data(ticker):
    # Mô phỏng API chính
    if random.random() < 0.1: # Giảm tỉ lệ lỗi để app mượt hơn
        raise Exception("Nguồn chính bận")
        
    return {
        "ticker": ticker,
        "price": random.randint(20000, 150000),
        "volume": random.randint(100000, 5000000),
        "pe": round(random.uniform(8.0, 25.0), 2),
        "pb": round(random.uniform(1.0, 5.0), 2),
        "source": "Nguồn Bản Địa (Primary)"
    }

# ==========================================
# CƠ CHẾ 2: TRUNG TÂM ĐIỀU PHỐI (Dùng cho app.py)
# ==========================================
@st.cache_data(ttl=60, show_spinner=False)
def get_stock_data(ticker):
    try:
        return fetch_primary_data(ticker)
    except Exception:
        # Fallback dữ liệu nếu lỗi
        return {
            "ticker": ticker,
            "price": 50000,
            "volume": 1000000,
            "pe": "N/A",
            "pb": "N/A",
            "source": "Dữ liệu Dự phòng"
        }
