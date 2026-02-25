"""
================================================================================
  core/data_fetcher.py — Lấy dữ liệu chứng khoán
  
  FIXES v2.2:
  ✅ TCBS bị block từ cloud nước ngoài → fallback: Fireant → SSI → yfinance
  ✅ Retry chống YFRateLimitError
  ✅ Cache 5 phút
================================================================================
"""

import yfinance as yf
import requests
import streamlit as st
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REGION_SUFFIX = {"VN": ".VN", "US": "", "INTL": ""}

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
}


# ── Nguồn 1: TCBS ─────────────────────────────────────────────────────────────
def _from_tcbs(ticker: str) -> dict:
    url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview"
    r = requests.get(url, headers={**_HEADERS, 'Referer': 'https://tcinvest.tcbs.com.vn/'},
                     timeout=6, verify=False)
    if r.status_code != 200:
        raise Exception(f"TCBS HTTP {r.status_code}")
    d = r.json()
    if not d.get("pe") and not d.get("pb"):
        raise Exception("TCBS data empty")
    return {
        "pe":       round(float(d["pe"]), 2)         if d.get("pe")         else "N/A",
        "pb":       round(float(d["pb"]), 2)         if d.get("pb")         else "N/A",
        "industry": d.get("industryName", "N/A"),
        "avg_pe":   round(float(d["industryPe"]), 2) if d.get("industryPe") else 0,
        "avg_pb":   round(float(d["industryPb"]), 2) if d.get("industryPb") else 0,
        "market":   d.get("exchange", "HOSE").replace("HSX", "HOSE"),
    }


# ── Nguồn 2: Fireant ──────────────────────────────────────────────────────────
def _from_fireant(ticker: str) -> dict:
    url = f"https://restv2.fireant.vn/symbols/{ticker}/fundamental"
    r = requests.get(url, headers=_HEADERS, timeout=6, verify=False)
    if r.status_code != 200:
        raise Exception(f"Fireant HTTP {r.status_code}")
    d = r.json()
    pe = d.get("pe") or d.get("priceToEarning")
    pb = d.get("pb") or d.get("priceToBook")
    if pe is None and pb is None:
        raise Exception("Fireant data empty")
    return {
        "pe":       round(float(pe), 2) if pe else "N/A",
        "pb":       round(float(pb), 2) if pb else "N/A",
        "industry": d.get("industryName", "N/A"),
        "avg_pe":   0, "avg_pb": 0,
        "market":   d.get("exchange", "HOSE").replace("HSX", "HOSE"),
    }


# ── Nguồn 3: SSI iBoard ───────────────────────────────────────────────────────
def _from_ssi(ticker: str) -> dict:
    url = f"https://iboard-query.ssi.com.vn/v2/stock/ticker-info/{ticker}"
    r = requests.get(url, headers={**_HEADERS, 'Referer': 'https://iboard.ssi.com.vn/'},
                     timeout=6, verify=False)
    if r.status_code != 200:
        raise Exception(f"SSI HTTP {r.status_code}")
    raw = r.json()
    d   = raw.get("data", raw)
    pe  = d.get("pe") or d.get("PE")
    pb  = d.get("pb") or d.get("PB")
    if pe is None and pb is None:
        raise Exception("SSI data empty")
    return {
        "pe":       round(float(pe), 2) if pe else "N/A",
        "pb":       round(float(pb), 2) if pb else "N/A",
        "industry": d.get("industryName", d.get("icbName", "N/A")),
        "avg_pe":   0, "avg_pb": 0,
        "market":   d.get("exchange", d.get("floorCode", "HOSE")),
    }


# ── Nguồn 4: yfinance info (fallback cuối) ────────────────────────────────────
def _from_yf_info(stock) -> dict:
    try:
        info = stock.info or {}
    except Exception:
        info = {}
    pe = info.get("trailingPE") or info.get("forwardPE")
    pb = info.get("priceToBook")
    return {
        "pe":       round(float(pe), 2) if pe else "N/A",
        "pb":       round(float(pb), 2) if pb else "N/A",
        "industry": info.get("industry") or info.get("sector", "N/A"),
        "avg_pe":   0, "avg_pb": 0,
        "market":   info.get("exchange", "HOSE"),
    }


def _get_fundamentals_vn(ticker: str, stock) -> dict:
    """Thử lần lượt 4 nguồn, trả về kết quả đầu tiên thành công."""
    for name, fn in [
        ("TCBS",    lambda: _from_tcbs(ticker)),
        ("Fireant", lambda: _from_fireant(ticker)),
        ("SSI",     lambda: _from_ssi(ticker)),
        ("YF",      lambda: _from_yf_info(stock)),
    ]:
        try:
            return fn()
        except Exception:
            continue
    # Tất cả thất bại → N/A, không crash app
    return {"pe": "N/A", "pb": "N/A", "industry": "N/A",
            "avg_pe": 0, "avg_pb": 0, "market": "HOSE"}


# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(ticker: str, region: str = "VN") -> dict:
    """
    Lấy giá, khối lượng và chỉ số cơ bản.
    Returns dict hoặc dict với key 'error'.
    """
    suffix = REGION_SUFFIX.get(region, "")
    yf_str = f"{ticker}{suffix}"
    price, volume, stock = None, None, None

    for attempt in range(3):
        try:
            stock = yf.Ticker(yf_str)
            df    = stock.history(period="2d", timeout=10)

            if df is None or df.empty:
                if suffix:
                    sb = yf.Ticker(ticker)
                    df2 = sb.history(period="2d", timeout=10)
                    if not df2.empty:
                        stock, df = sb, df2
                if df is None or df.empty:
                    return {"error": f"Không tìm thấy mã **'{ticker}'**. Kiểm tra mã hoặc khu vực thị trường."}

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

    fund = _get_fundamentals_vn(ticker, stock) if region == "VN" else _from_yf_info(stock)
    return {"ticker": ticker, "price": price, "volume": volume, **fund}
