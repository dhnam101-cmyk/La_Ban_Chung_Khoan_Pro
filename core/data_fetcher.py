"""
================================================================================
  core/data_fetcher.py — v2.4 FINAL FIX
  
  ROOT CAUSE: Tất cả API VN (TCBS, SSI, Fireant) đều block IP nước ngoài.
  
  SOLUTION:
  ✅ Scrape CafeF.vn (HTML) — không chặn IP nước ngoài
  ✅ Scrape VnDirect (JSON public) — backup
  ✅ yfinance info — fallback cuối
  ✅ Retry 3 lần chống YFRateLimitError
  ✅ Cache 5 phút
================================================================================
"""

import yfinance as yf
import requests
from bs4 import BeautifulSoup
import streamlit as st
import urllib3
import time
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REGION_SUFFIX = {"VN": ".VN", "US": "", "INTL": ""}

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Cache-Control': 'no-cache',
}


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 1: CafeF.vn — scrape HTML, không bị block từ nước ngoài
# ══════════════════════════════════════════════════════════════════════════════
def _from_cafef(ticker: str) -> dict:
    """
    Scrape trang cổ phiếu trên CafeF để lấy P/E, P/B và ngành.
    URL: https://cafef.vn/thi-truong-chung-khoan/[ticker]-ctcp.chn
    """
    url = f"https://cafef.vn/du-lieu/Ajax/PageNew/DataAnalyticsHandler.ashx?Type=FQ&Symbol={ticker}"
    headers = {**_HEADERS, 'Referer': f'https://cafef.vn/co-phieu/{ticker.lower()}-ctcp.chn'}
    
    r = requests.get(url, headers=headers, timeout=8, verify=False)
    if r.status_code != 200:
        raise Exception(f"CafeF API HTTP {r.status_code}")
    
    try:
        data = r.json()
    except Exception:
        raise Exception("CafeF API không trả về JSON")
    
    # CafeF trả về list, lấy record mới nhất
    items = data if isinstance(data, list) else data.get("Data", data.get("data", []))
    if not items:
        raise Exception("CafeF data empty")
    
    latest = items[0] if isinstance(items[0], dict) else {}
    pe = latest.get("PE") or latest.get("pe") or latest.get("priceToEarning")
    pb = latest.get("PB") or latest.get("pb") or latest.get("priceToBook")
    
    if pe is None and pb is None:
        raise Exception("CafeF no PE/PB in response")
    
    return {
        "pe":       round(float(pe), 2) if pe and float(pe) > 0 else "N/A",
        "pb":       round(float(pb), 2) if pb and float(pb) > 0 else "N/A",
        "industry": latest.get("IndustryName", latest.get("industry", "N/A")),
        "avg_pe":   0,
        "avg_pb":   0,
        "market":   latest.get("Exchange", "HOSE").replace("HSX", "HOSE"),
    }


def _from_cafef_html(ticker: str) -> dict:
    """
    Fallback: Scrape trang HTML profile cổ phiếu CafeF.
    Tìm các số liệu P/E, P/B trong table.
    """
    url = f"https://cafef.vn/co-phieu/{ticker.lower()}-ctcp.chn"
    r   = requests.get(url, headers=_HEADERS, timeout=10, verify=False)
    if r.status_code != 200:
        raise Exception(f"CafeF HTML HTTP {r.status_code}")
    
    soup = BeautifulSoup(r.text, 'html.parser')
    
    pe, pb, industry, market = None, None, "N/A", "HOSE"
    
    # Tìm trong tất cả text của trang
    text = soup.get_text()
    
    # Pattern tìm P/E
    pe_match = re.search(r'P/E[:\s]+([0-9]+\.?[0-9]*)', text)
    if pe_match:
        pe = float(pe_match.group(1))
    
    # Pattern tìm P/B
    pb_match = re.search(r'P/B[:\s]+([0-9]+\.?[0-9]*)', text)
    if pb_match:
        pb = float(pb_match.group(1))
    
    # Tìm tên ngành
    industry_tag = soup.find('span', string=re.compile('Ngành', re.I))
    if industry_tag and industry_tag.find_next_sibling():
        industry = industry_tag.find_next_sibling().get_text(strip=True)
    
    # Tìm sàn giao dịch
    for tag in soup.find_all(['span', 'td', 'div']):
        t = tag.get_text(strip=True).upper()
        if t in ('HOSE', 'HNX', 'UPCOM', 'HSX'):
            market = t.replace('HSX', 'HOSE')
            break
    
    if pe is None and pb is None:
        raise Exception("CafeF HTML: không parse được P/E, P/B")
    
    return {
        "pe":       round(pe, 2) if pe and pe > 0 else "N/A",
        "pb":       round(pb, 2) if pb and pb > 0 else "N/A",
        "industry": industry,
        "avg_pe":   0,
        "avg_pb":   0,
        "market":   market,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 2: VnDirect public JSON API
# ══════════════════════════════════════════════════════════════════════════════
def _from_vndirect(ticker: str) -> dict:
    """
    VnDirect có public API không cần auth, ít bị block hơn TCBS.
    """
    url = (
        f"https://finfo-api.vndirect.com.vn/v4/ratios/latest?"
        f"filter=code:{ticker}&fields=code,pe,pb,roe,roa,industryPe,industryPb,industryName,exchange"
    )
    headers = {
        **_HEADERS,
        'Referer': 'https://www.vndirect.com.vn/',
        'Accept': 'application/json',
    }
    r = requests.get(url, headers=headers, timeout=8, verify=False)
    if r.status_code != 200:
        raise Exception(f"VnDirect HTTP {r.status_code}")
    
    raw  = r.json()
    data = raw.get("data", [])
    if not data:
        raise Exception("VnDirect data empty")
    
    d  = data[0]
    pe = d.get("pe")
    pb = d.get("pb")
    
    if pe is None and pb is None:
        raise Exception("VnDirect no PE/PB")
    
    return {
        "pe":       round(float(pe), 2)               if pe                   else "N/A",
        "pb":       round(float(pb), 2)               if pb                   else "N/A",
        "industry": d.get("industryName", "N/A"),
        "avg_pe":   round(float(d["industryPe"]), 2)  if d.get("industryPe")  else 0,
        "avg_pb":   round(float(d["industryPb"]), 2)  if d.get("industryPb")  else 0,
        "market":   d.get("exchange", "HOSE").replace("HSX", "HOSE"),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 3: TCBS (thử lại với headers khác)
# ══════════════════════════════════════════════════════════════════════════════
def _from_tcbs(ticker: str) -> dict:
    url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview"
    headers = {
        **_HEADERS,
        'Accept': 'application/json',
        'Origin': 'https://tcinvest.tcbs.com.vn',
        'Referer': 'https://tcinvest.tcbs.com.vn/',
    }
    r = requests.get(url, headers=headers, timeout=8, verify=False)
    if r.status_code != 200:
        raise Exception(f"TCBS HTTP {r.status_code}")
    d  = r.json()
    pe = d.get("pe")
    pb = d.get("pb")
    if not pe and not pb:
        raise Exception("TCBS data empty")
    return {
        "pe":       round(float(pe), 2)              if pe              else "N/A",
        "pb":       round(float(pb), 2)              if pb              else "N/A",
        "industry": d.get("industryName", "N/A"),
        "avg_pe":   round(float(d["industryPe"]), 2) if d.get("industryPe") else 0,
        "avg_pb":   round(float(d["industryPb"]), 2) if d.get("industryPb") else 0,
        "market":   d.get("exchange", "HOSE").replace("HSX", "HOSE"),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 4: yfinance info (fallback cuối cùng)
# ══════════════════════════════════════════════════════════════════════════════
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
        "avg_pe":   0,
        "avg_pb":   0,
        "market":   info.get("exchange", "HOSE"),
    }


def _get_fundamentals_vn(ticker: str, stock) -> dict:
    """
    Thử lần lượt các nguồn. VnDirect ưu tiên vì có avg_pe/avg_pb.
    Nếu nguồn thành công không có avg, thử bổ sung từ VnDirect.
    """
    sources = [
        ("VnDirect",    lambda: _from_vndirect(ticker)),
        ("TCBS",        lambda: _from_tcbs(ticker)),
        ("CafeF_API",   lambda: _from_cafef(ticker)),
        ("CafeF_HTML",  lambda: _from_cafef_html(ticker)),
        ("yfinance",    lambda: _from_yf_info(stock)),
    ]
    
    best_result = None
    
    for name, fn in sources:
        try:
            result = fn()
            # Nếu có đủ pe/pb + avg → dùng luôn
            if result.get("pe") != "N/A" and result.get("avg_pe", 0) != 0:
                return result
            # Nếu chưa đủ avg, lưu lại và thử tiếp
            if result.get("pe") != "N/A" and best_result is None:
                best_result = result
        except Exception:
            continue
    
    # Nếu có pe/pb nhưng không có avg → trả về kết quả tốt nhất
    if best_result:
        return best_result
    
    # Tất cả thất bại
    return {
        "pe": "N/A", "pb": "N/A", "industry": "N/A",
        "avg_pe": 0, "avg_pb": 0, "market": "HOSE"
    }


# ══════════════════════════════════════════════════════════════════════════════
#  HÀM CHÍNH
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(ticker: str, region: str = "VN") -> dict:
    """
    Lấy giá, khối lượng, PE, PB và dữ liệu ngành.
    Returns dict, hoặc dict{'error': ...} nếu thất bại.
    """
    suffix = REGION_SUFFIX.get(region, "")
    yf_str = f"{ticker}{suffix}"
    price, volume, stock = None, None, None

    # ── Lấy giá từ yfinance (retry 3 lần) ──────────────────────────────────
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

    fund = _get_fundamentals_vn(ticker, stock) if region == "VN" else _from_yf_info(stock)
    return {"ticker": ticker, "price": price, "volume": volume, **fund}
