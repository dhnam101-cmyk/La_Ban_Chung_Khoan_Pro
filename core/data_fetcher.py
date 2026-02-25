"""
================================================================================
  core/data_fetcher.py — Lấy dữ liệu chứng khoán
  Fixes:
  ✅ YFRateLimitError: retry 3 lần + thông báo thân thiện
  ✅ "Quote not found": kiểm tra df.empty trước khi xử lý
  ✅ Cache TTL 5 phút
  ✅ Hỗ trợ đa khu vực: VN / US / INTL
================================================================================
"""

import yfinance as yf
import requests
import streamlit as st
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REGION_SUFFIX = {"VN": ".VN", "US": "", "INTL": ""}


def _get_fundamentals_tcbs(ticker: str) -> dict:
    """Lấy P/E, P/B, ngành từ TCBS (chỉ cho thị trường VN)."""
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
            "pe":       round(d["pe"], 2)         if d.get("pe")         else "N/A",
            "pb":       round(d["pb"], 2)         if d.get("pb")         else "N/A",
            "industry": d.get("industryName", "Chưa phân loại"),
            "avg_pe":   round(d["industryPe"], 2) if d.get("industryPe") else 0,
            "avg_pb":   round(d["industryPb"], 2) if d.get("industryPb") else 0,
            "market":   d.get("exchange", "HOSE").replace("HSX", "HOSE")
        }
    raise Exception(f"TCBS trả về status {resp.status_code}")


@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(ticker: str, region: str = "VN") -> dict:
    """
    Lấy giá, khối lượng và chỉ số cơ bản của mã cổ phiếu.
    Returns dict với key 'error' nếu thất bại.
    """
    suffix    = REGION_SUFFIX.get(region, "")
    yf_str    = f"{ticker}{suffix}"
    price, volume, stock = None, None, None

    # ── Lấy giá từ yfinance (retry 3 lần) ────────────────────────────────────
    for attempt in range(3):
        try:
            stock = yf.Ticker(yf_str)
            df    = stock.history(period="2d", timeout=10)

            if df is None or df.empty:
                if suffix:                          # Thử lại không có suffix
                    stock_bare = yf.Ticker(ticker)
                    df = stock_bare.history(period="2d", timeout=10)
                    if not df.empty:
                        stock = stock_bare
                if df is None or df.empty:
                    return {
                        "error": (
                            f"Không tìm thấy mã **'{ticker}'**. "
                            "Kiểm tra lại mã hoặc chọn đúng khu vực thị trường."
                        )
                    }

            price  = round(float(df['Close'].iloc[-1]), 2)
            volume = int(df['Volume'].iloc[-1])
            break

        except Exception as e:
            err = str(e).lower()
            if ("ratelimit" in err or "429" in err or "too many" in err) and attempt < 2:
                time.sleep((attempt + 1) * 3)
                continue
            elif ("timeout" in err or "timed out" in err) and attempt < 2:
                time.sleep(2)
                continue
            elif attempt == 2:
                if "ratelimit" in err or "429" in err:
                    return {"error": "⏳ Yahoo Finance đang giới hạn truy cập. Thử lại sau 30 giây."}
                return {"error": f"Lỗi khi lấy dữ liệu '{ticker}': {e}"}

    if price is None:
        return {"error": f"Không lấy được giá của '{ticker}'."}

    # ── Lấy fundamentals ─────────────────────────────────────────────────────
    fund: dict = {}
    if region == "VN":
        try:
            fund = _get_fundamentals_tcbs(ticker)
        except Exception:
            try:
                info = stock.info or {}
                fund = {
                    "pe":       round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else "N/A",
                    "pb":       round(info.get('priceToBook', 0), 2) if info.get('priceToBook') else "N/A",
                    "industry": info.get('industry', 'N/A'),
                    "avg_pe":   0, "avg_pb": 0, "market": "HOSE"
                }
            except Exception:
                fund = {"pe": "N/A", "pb": "N/A", "industry": "N/A",
                        "avg_pe": 0, "avg_pb": 0, "market": "VN"}
    else:
        try:
            info = stock.info or {}
            fund = {
                "pe":       round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else "N/A",
                "pb":       round(info.get('priceToBook', 0), 2) if info.get('priceToBook') else "N/A",
                "industry": info.get('industry', info.get('sector', 'N/A')),
                "avg_pe":   0, "avg_pb": 0, "market": info.get('exchange', region)
            }
        except Exception:
            fund = {"pe": "N/A", "pb": "N/A", "industry": "N/A",
                    "avg_pe": 0, "avg_pb": 0, "market": region}

    return {"ticker": ticker, "price": price, "volume": volume, **fund}
