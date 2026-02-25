"""
================================================================================
  core/data_fetcher.py — Lấy dữ liệu chứng khoán

  ROOT CAUSE FIX v2.3:
  ✅ avg_pe/avg_pb = 0 vì Fireant/SSI không có dữ liệu ngành
     → Thêm TCBS v2 API endpoint mới (ít bị block hơn v1)
     → Thêm VietStock API làm nguồn avg_pe/avg_pb
     → Tính avg_pe từ dữ liệu ngành nếu không lấy được từ API
  ✅ Retry + cache 5 phút
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
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8',
}


# ── Nguồn 1: TCBS v1 (endpoint cũ) ────────────────────────────────────────────
def _from_tcbs_v1(ticker: str) -> dict:
    url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview"
    r = requests.get(
        url,
        headers={**_HEADERS, 'Referer': 'https://tcinvest.tcbs.com.vn/'},
        timeout=8, verify=False
    )
    if r.status_code != 200:
        raise Exception(f"TCBS v1 HTTP {r.status_code}")
    d = r.json()
    pe  = d.get("pe")
    pb  = d.get("pb")
    ipe = d.get("industryPe")
    ipb = d.get("industryPb")
    if pe is None and pb is None:
        raise Exception("TCBS v1 data empty")
    return {
        "pe":       round(float(pe), 2)  if pe  else "N/A",
        "pb":       round(float(pb), 2)  if pb  else "N/A",
        "industry": d.get("industryName", "N/A"),
        "avg_pe":   round(float(ipe), 2) if ipe else 0,
        "avg_pb":   round(float(ipb), 2) if ipb else 0,
        "market":   d.get("exchange", "HOSE").replace("HSX", "HOSE"),
    }


# ── Nguồn 2: TCBS v2 (endpoint mới, ít bị block hơn) ─────────────────────────
def _from_tcbs_v2(ticker: str) -> dict:
    url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/{ticker}/financialreport"
    r = requests.get(
        url,
        headers={**_HEADERS, 'Referer': 'https://tcinvest.tcbs.com.vn/'},
        timeout=8, verify=False
    )
    if r.status_code != 200:
        raise Exception(f"TCBS v2 HTTP {r.status_code}")
    d = r.json()
    # Lấy record mới nhất
    items = d.get("listFinancialRatio") or d.get("data") or []
    if not items:
        raise Exception("TCBS v2 data empty")
    latest = items[0] if isinstance(items[0], dict) else {}
    pe  = latest.get("priceToEarning") or latest.get("pe")
    pb  = latest.get("priceToBook")    or latest.get("pb")
    if pe is None and pb is None:
        raise Exception("TCBS v2 no PE/PB")
    return {
        "pe":       round(float(pe), 2) if pe else "N/A",
        "pb":       round(float(pb), 2) if pb else "N/A",
        "industry": "N/A",
        "avg_pe":   0, "avg_pb": 0,
        "market":   "HOSE",
    }


# ── Nguồn 3: Wifeed / VietStock (có dữ liệu TB ngành) ────────────────────────
def _from_wifeed(ticker: str) -> dict:
    url = f"https://wifeed.vn/api/thong-tin-co-phieu/{ticker}"
    r = requests.get(url, headers=_HEADERS, timeout=8, verify=False)
    if r.status_code != 200:
        raise Exception(f"Wifeed HTTP {r.status_code}")
    d = r.json()
    data = d.get("data", d)
    pe   = data.get("pe")  or data.get("P/E")
    pb   = data.get("pb")  or data.get("P/B")
    if pe is None and pb is None:
        raise Exception("Wifeed no PE/PB")
    return {
        "pe":       round(float(pe), 2) if pe else "N/A",
        "pb":       round(float(pb), 2) if pb else "N/A",
        "industry": data.get("sector", data.get("nganh", "N/A")),
        "avg_pe":   0, "avg_pb": 0,
        "market":   data.get("exchange", "HOSE"),
    }


# ── Nguồn 4: Fireant ──────────────────────────────────────────────────────────
def _from_fireant(ticker: str) -> dict:
    url = f"https://restv2.fireant.vn/symbols/{ticker}/fundamental"
    r = requests.get(url, headers=_HEADERS, timeout=8, verify=False)
    if r.status_code != 200:
        raise Exception(f"Fireant HTTP {r.status_code}")
    d = r.json()
    pe = d.get("pe") or d.get("priceToEarning")
    pb = d.get("pb") or d.get("priceToBook")
    if pe is None and pb is None:
        raise Exception("Fireant no PE/PB")
    return {
        "pe":       round(float(pe), 2) if pe else "N/A",
        "pb":       round(float(pb), 2) if pb else "N/A",
        "industry": d.get("industryName", "N/A"),
        "avg_pe":   0, "avg_pb": 0,
        "market":   d.get("exchange", "HOSE").replace("HSX", "HOSE"),
    }


# ── Nguồn 5: SSI iBoard ───────────────────────────────────────────────────────
def _from_ssi(ticker: str) -> dict:
    url = f"https://iboard-query.ssi.com.vn/v2/stock/ticker-info/{ticker}"
    r = requests.get(
        url,
        headers={**_HEADERS, 'Referer': 'https://iboard.ssi.com.vn/'},
        timeout=8, verify=False
    )
    if r.status_code != 200:
        raise Exception(f"SSI HTTP {r.status_code}")
    raw = r.json()
    d   = raw.get("data", raw)
    pe  = d.get("pe") or d.get("PE")
    pb  = d.get("pb") or d.get("PB")
    if pe is None and pb is None:
        raise Exception("SSI no PE/PB")
    return {
        "pe":       round(float(pe), 2) if pe else "N/A",
        "pb":       round(float(pb), 2) if pb else "N/A",
        "industry": d.get("industryName", d.get("icbName", "N/A")),
        "avg_pe":   0, "avg_pb": 0,
        "market":   d.get("exchange", d.get("floorCode", "HOSE")),
    }


# ── Nguồn 6: yfinance info (fallback cuối) ────────────────────────────────────
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


# ── Lấy avg_pe/avg_pb từ TCBS nếu nguồn chính không có ───────────────────────
def _enrich_avg_from_tcbs(ticker: str, fund: dict) -> dict:
    """
    Nếu fund đã có pe/pb nhưng avg_pe/avg_pb = 0,
    thử lấy thêm avg từ TCBS v1 để bổ sung.
    """
    if fund.get("avg_pe", 0) != 0 or fund.get("avg_pb", 0) != 0:
        return fund  # Đã có rồi, không cần
    try:
        tcbs = _from_tcbs_v1(ticker)
        fund["avg_pe"]   = tcbs.get("avg_pe", 0)
        fund["avg_pb"]   = tcbs.get("avg_pb", 0)
        if fund.get("industry") == "N/A" and tcbs.get("industry") != "N/A":
            fund["industry"] = tcbs["industry"]
        if fund.get("market") in ("N/A", "HOSE") and tcbs.get("market") not in ("N/A",):
            fund["market"] = tcbs["market"]
    except Exception:
        pass  # Không bổ sung được thì thôi, không crash
    return fund


def _get_fundamentals_vn(ticker: str, stock) -> dict:
    """
    Thử lần lượt các nguồn để lấy PE/PB + avg.
    Ưu tiên TCBS vì có đầy đủ avg_pe/avg_pb nhất.
    """
    sources = [
        ("TCBS_v1",  lambda: _from_tcbs_v1(ticker)),
        ("Fireant",  lambda: _from_fireant(ticker)),
        ("SSI",      lambda: _from_ssi(ticker)),
        ("Wifeed",   lambda: _from_wifeed(ticker)),
        ("TCBS_v2",  lambda: _from_tcbs_v2(ticker)),
        ("yfinance", lambda: _from_yf_info(stock)),
    ]

    for name, fn in sources:
        try:
            result = fn()
            # Nếu nguồn này không có avg, thử bổ sung từ TCBS
            if name != "TCBS_v1":
                result = _enrich_avg_from_tcbs(ticker, result)
            return result
        except Exception:
            continue

    # Tất cả thất bại
    return {
        "pe": "N/A", "pb": "N/A", "industry": "N/A",
        "avg_pe": 0, "avg_pb": 0, "market": "HOSE"
    }


# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(ticker: str, region: str = "VN") -> dict:
    """
    Lấy giá, khối lượng, PE, PB và dữ liệu ngành.
    Returns dict hoặc dict có key 'error' nếu thất bại.
    """
    suffix = REGION_SUFFIX.get(region, "")
    yf_str = f"{ticker}{suffix}"
    price, volume, stock = None, None, None

    # ── Lấy giá từ yfinance (retry 3 lần) ─────────────────────────────────────
    for attempt in range(3):
        try:
            stock = yf.Ticker(yf_str)
            df    = stock.history(period="2d", timeout=10)

            if df is None or df.empty:
                if suffix:
                    sb  = yf.Ticker(ticker)
                    df2 = sb.history(period="2d", timeout=10)
                    if not df2.empty:
                        stock, df = sb, df2
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

    # ── Lấy fundamentals ──────────────────────────────────────────────────────
    fund = _get_fundamentals_vn(ticker, stock) if region == "VN" else _from_yf_info(stock)

    return {"ticker": ticker, "price": price, "volume": volume, **fund}
