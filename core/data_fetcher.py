"""
================================================================================
  data_fetcher.py — Lấy dữ liệu chứng khoán
  
  Fixes:
  ✅ YFRateLimitError: Bắt lỗi cụ thể + retry + fallback
  ✅ "Quote not found": Kiểm tra df.empty trước khi xử lý
  ✅ Cache TTL 5 phút để giảm số lần gọi API
  ✅ Hỗ trợ đa khu vực: VN (.VN suffix), US (không suffix), INTL
================================================================================
"""

import yfinance as yf
import requests
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ──────────────────────────────────────────────────────────────────────────────
#  CẤU HÌNH SUFFIX THEO REGION
# ──────────────────────────────────────────────────────────────────────────────
REGION_SUFFIX = {
    "VN":   ".VN",
    "US":   "",
    "INTL": "",   # Người dùng tự nhập suffix nếu cần (VD: "9984.T")
}

# ──────────────────────────────────────────────────────────────────────────────
#  LẤY DỮ LIỆU CƠ BẢN TỪ TCBS (CHỈ CHO THỊ TRƯỜNG VIỆT NAM)
# ──────────────────────────────────────────────────────────────────────────────
def _get_fundamentals_tcbs(ticker: str) -> dict:
    """
    Lấy P/E, P/B và thông tin ngành từ API TCBS.
    Raise Exception nếu thất bại để caller chuyển sang fallback.
    """
    url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview"
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/122.0.0.0 Safari/537.36'
        ),
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://tcinvest.tcbs.com.vn/'
    }
    
    resp = requests.get(url, headers=headers, timeout=6, verify=False)
    
    if resp.status_code == 200:
        d = resp.json()
        return {
            "pe":       round(d["pe"], 2)           if d.get("pe")          else "N/A",
            "pb":       round(d["pb"], 2)           if d.get("pb")          else "N/A",
            "industry": d.get("industryName", "Chưa phân loại"),
            "avg_pe":   round(d["industryPe"], 2)   if d.get("industryPe")  else 0,
            "avg_pb":   round(d["industryPb"], 2)   if d.get("industryPb")  else 0,
            "market":   d.get("exchange", "HOSE").replace("HSX", "HOSE")
        }
    
    raise Exception(f"TCBS trả về status {resp.status_code}")


# ──────────────────────────────────────────────────────────────────────────────
#  HÀM CHÍNH: LẤY DỮ LIỆU CỔ PHIẾU (CÓ CACHE & RETRY)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)  # Cache 5 phút
def get_stock_data(ticker: str, region: str = "VN") -> dict:
    """
    Lấy giá, khối lượng và chỉ số cơ bản của mã cổ phiếu.
    
    Args:
        ticker: Mã cổ phiếu (VD: "FPT", "AAPL")
        region: "VN" | "US" | "INTL"
    
    Returns:
        dict với các key: ticker, price, volume, pe, pb, industry,
                          avg_pe, avg_pb, market
        hoặc dict với key "error" nếu thất bại.
    """
    suffix   = REGION_SUFFIX.get(region, "")
    yf_ticker_str = f"{ticker}{suffix}"
    
    # ── Bước 1: Lấy giá & khối lượng từ yfinance ─────────────────────────────
    price, volume = None, None
    
    for attempt in range(3):  # Retry tối đa 3 lần
        try:
            stock = yf.Ticker(yf_ticker_str)
            df    = stock.history(period="2d", timeout=10)  # 2d để chắc có dữ liệu
            
            if df is None or df.empty:
                # Thử lại không có suffix (cho trường hợp INTL tự gõ suffix)
                if suffix:
                    stock_bare = yf.Ticker(ticker)
                    df = stock_bare.history(period="2d", timeout=10)
                    if not df.empty:
                        stock = stock_bare
                
                if df is None or df.empty:
                    return {"error": f"Không tìm thấy mã '{ticker}'. Kiểm tra lại mã hoặc chọn đúng khu vực thị trường."}
            
            price  = round(float(df['Close'].iloc[-1]), 2)
            volume = int(df['Volume'].iloc[-1])
            break  # Thành công → thoát vòng retry
        
        except Exception as e:
            err_str = str(e).lower()
            
            # Bắt lỗi rate limit cụ thể
            if "ratelimit" in err_str or "429" in err_str or "too many" in err_str:
                if attempt < 2:
                    wait = (attempt + 1) * 3  # 3s, 6s
                    time.sleep(wait)
                    continue
                else:
                    return {"error": "⏳ Yahoo Finance đang giới hạn truy cập (Rate Limit). Vui lòng thử lại sau 30 giây."}
            
            # Lỗi timeout
            elif "timeout" in err_str or "timed out" in err_str:
                if attempt < 2:
                    time.sleep(2)
                    continue
                else:
                    return {"error": "⌛ Kết nối đến Yahoo Finance bị timeout. Kiểm tra mạng và thử lại."}
            
            # Các lỗi khác
            else:
                return {"error": f"Lỗi khi lấy dữ liệu '{ticker}': {str(e)}"}
    
    if price is None:
        return {"error": f"Không lấy được giá của '{ticker}'."}
    
    # ── Bước 2: Lấy chỉ số cơ bản (Fundamentals) ─────────────────────────────
    fund_data = {}
    
    if region == "VN":
        # Ưu tiên TCBS cho thị trường Việt Nam
        try:
            fund_data = _get_fundamentals_tcbs(ticker)
        except Exception:
            # Fallback: dùng yfinance info (ít dữ liệu hơn)
            try:
                info = stock.info or {}
                fund_data = {
                    "pe":       round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else "N/A",
                    "pb":       round(info.get('priceToBook', 0), 2) if info.get('priceToBook') else "N/A",
                    "industry": info.get('industry', 'N/A'),
                    "avg_pe":   0,
                    "avg_pb":   0,
                    "market":   "HOSE"
                }
            except Exception:
                fund_data = {"pe": "N/A", "pb": "N/A", "industry": "N/A", "avg_pe": 0, "avg_pb": 0, "market": "VN"}
    
    else:
        # Thị trường US/INTL: Dùng yfinance info
        try:
            info = stock.info or {}
            fund_data = {
                "pe":       round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else "N/A",
                "pb":       round(info.get('priceToBook', 0), 2) if info.get('priceToBook') else "N/A",
                "industry": info.get('industry', info.get('sector', 'N/A')),
                "avg_pe":   0,
                "avg_pb":   0,
                "market":   info.get('exchange', region)
            }
        except Exception:
            fund_data = {"pe": "N/A", "pb": "N/A", "industry": "N/A", "avg_pe": 0, "avg_pb": 0, "market": region}
    
    return {
        "ticker": ticker,
        "price":  price,
        "volume": volume,
        **fund_data
    }
