"""
core/data_fetcher.py — v5.0

Lấy ĐẦY ĐỦ dữ liệu như trang HOSE/CafeF:
  - Giá tham chiếu, trần, sàn, mở cửa, cao/thấp nhất
  - EPS cơ bản, P/E, Giá trị sổ sách/CP, P/B
  - Vốn hóa thị trường
  - KLGD khớp lệnh TB 10 phiên  
  - KLCP niêm yết / lưu hành
  - Room NN còn lại
  - NN Mua / NN Bán

Nguồn ưu tiên (hoạt động từ US server):
  1. SSI iBoard API    — giá realtime + room NN
  2. VnDirect API     — ratios: EPS, PE, PB, book value
  3. yfinance         — giá + fundamental fallback
  4. Tính từ financials — PE, PB tự tính
"""

import yfinance as yf
import requests
import streamlit as st
import urllib3, time, re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REGION_SUFFIX = {"VN": ".VN", "US": "", "INTL": ""}

_H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}


def _f(v, lo=0.001, hi=999999):
    """Safe float conversion."""
    try:
        x = float(str(v).replace(",", ""))
        return round(x, 2) if lo < abs(x) < hi else None
    except Exception:
        return None


def _safe(d, *keys, default="N/A"):
    """Nested dict safe get."""
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k)
        else:
            return default
    return d if d is not None else default


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 1: SSI iBoard — realtime price, room NN, foreign buy/sell
# ══════════════════════════════════════════════════════════════════════════════
def _from_ssi(ticker: str) -> dict:
    """
    SSI public API — không cần auth, hoạt động từ nước ngoài.
    Trả về: giá, KL, trần/sàn/tham chiếu, room NN, NN mua/bán.
    """
    # SSI iBoard realtime
    url = "https://iboard-query.ssi.com.vn/v2/stock/full"
    headers = {
        **_H,
        "Origin":  "https://iboard.ssi.com.vn",
        "Referer": "https://iboard.ssi.com.vn/",
    }
    r = requests.get(url, params={"symbol": ticker}, headers=headers, timeout=8, verify=False)
    if r.status_code != 200:
        raise Exception(f"SSI iBoard {r.status_code}")

    raw = r.json()
    d   = raw.get("data") or raw  # Tuỳ version API

    # Nếu trả về list
    if isinstance(d, list):
        matched = [x for x in d if str(x.get("symbol","")).upper() == ticker.upper()]
        d = matched[0] if matched else {}
    if not d:
        raise Exception("SSI: empty data")

    def g(*keys):
        for k in keys:
            v = d.get(k)
            if v is not None and v != "":
                return v
        return None

    price      = _f(g("lastPrice", "matchPrice", "close"))
    ref        = _f(g("referencePrice", "refPrice", "avePrice"))
    ceil       = _f(g("ceilPrice", "ceiling"))
    floor      = _f(g("floorPrice", "floor"))
    open_p     = _f(g("openPrice", "open"))
    high       = _f(g("highPrice", "high"))
    low        = _f(g("lowPrice", "low"))
    volume     = _f(g("matchQty", "totalMatchVolume", "volume"), lo=0, hi=1e15)
    total_vol  = _f(g("totalVolume", "totalVol"), lo=0, hi=1e15)

    # Room NN
    foreign_room    = _f(g("currentRoom", "foreignCurrentRoom", "room"))
    foreign_buy     = _f(g("foreignBuyVolume", "foreignBuyQtty", "fBuyVol"), lo=0, hi=1e15)
    foreign_sell    = _f(g("foreignSellVolume", "foreignSellQtty", "fSellVol"), lo=0, hi=1e15)

    # Listed/circulating shares
    listed_shares   = _f(g("listedShare", "shareIssued", "listVol"), lo=0, hi=1e15)
    circulating     = _f(g("circulatingShare", "shareFloat"), lo=0, hi=1e15)

    # Market cap
    market_cap      = _f(g("marketCap", "capitalization"), lo=0, hi=1e18)
    if not market_cap and price and listed_shares:
        market_cap = round(price * listed_shares, 0)

    # Sàn giao dịch
    exchange = str(g("exchange", "floor", "market") or "HOSE").upper()
    exchange = exchange.replace("HSX", "HOSE").replace("HNX-Index", "HNX")

    result = {
        "price":      price or ref,
        "ref_price":  ref,
        "ceil_price": ceil,
        "floor_price": floor,
        "open_price": open_p,
        "high_price": high,
        "low_price":  low,
        "volume":     int(volume) if volume else 0,
        "total_volume": int(total_vol) if total_vol else int(volume) if volume else 0,
        "foreign_room":  foreign_room,
        "foreign_buy":   int(foreign_buy)  if foreign_buy  else "N/A",
        "foreign_sell":  int(foreign_sell) if foreign_sell else "N/A",
        "listed_shares": int(listed_shares) if listed_shares else "N/A",
        "circulating":   int(circulating)   if circulating  else "N/A",
        "market_cap":    round(market_cap / 1e9, 2) if market_cap else "N/A",  # Tỷ đồng
        "market":        exchange,
    }

    if price is None:
        raise Exception("SSI: no price")

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 2: VnDirect — EPS, PE, PB, book value, avg industry
# ══════════════════════════════════════════════════════════════════════════════
def _from_vndirect_ratios(ticker: str) -> dict:
    url = (
        "https://finfo-api.vndirect.com.vn/v4/ratios/latest"
        f"?filter=code:{ticker}"
        "&fields=code,pe,pb,eps,bvps,roe,roa,industryPe,industryPb,industryName,exchange,capitalisation,listedShare"
    )
    r = requests.get(url, headers={**_H, "Referer": "https://www.vndirect.com.vn/"},
                     timeout=8, verify=False)
    if r.status_code != 200:
        raise Exception(f"VnDirect {r.status_code}")
    data = r.json().get("data", [])
    if not data:
        raise Exception("VnDirect empty")
    d = data[0]
    return {
        "pe":           _f(d.get("pe"))       or "N/A",
        "pb":           _f(d.get("pb"))       or "N/A",
        "eps":          _f(d.get("eps"), lo=-1e9, hi=1e9),   # VNĐ nghìn đồng
        "bvps":         _f(d.get("bvps"))     or "N/A",      # Book value/share (nghìn đồng)
        "roe":          _f(d.get("roe"))      or "N/A",
        "roa":          _f(d.get("roa"))      or "N/A",
        "avg_pe":       _f(d.get("industryPe")) or 0,
        "avg_pb":       _f(d.get("industryPb")) or 0,
        "industry":     d.get("industryName", "N/A"),
        "market":       d.get("exchange", "HOSE").replace("HSX", "HOSE"),
        "market_cap":   _f(d.get("capitalisation"), lo=0, hi=1e15),
        "listed_shares": _f(d.get("listedShare"), lo=0, hi=1e15),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 3: TCBS — overview + trading info
# ══════════════════════════════════════════════════════════════════════════════
def _from_tcbs(ticker: str) -> dict:
    url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview"
    r = requests.get(url, headers={**_H, "Origin": "https://tcinvest.tcbs.com.vn",
                                   "Referer": "https://tcinvest.tcbs.com.vn/"},
                     timeout=6, verify=False)
    if r.status_code != 200:
        raise Exception(f"TCBS {r.status_code}")
    d = r.json()
    return {
        "pe":           _f(d.get("pe"))        or "N/A",
        "pb":           _f(d.get("pb"))        or "N/A",
        "eps":          _f(d.get("eps"), lo=-1e9, hi=1e9),
        "bvps":         _f(d.get("bvps"))      or "N/A",
        "roe":          _f(d.get("roe"))        or "N/A",
        "roa":          _f(d.get("roa"))        or "N/A",
        "avg_pe":       _f(d.get("industryPe")) or 0,
        "avg_pb":       _f(d.get("industryPb")) or 0,
        "industry":     d.get("industryName", "N/A"),
        "market":       d.get("exchange", "HOSE").replace("HSX", "HOSE"),
        "outstanding_share": _f(d.get("outstandingShare"), lo=0, hi=1e15),
        "market_cap":   _f(d.get("marketCap"), lo=0, hi=1e15),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 4: yfinance — fallback lấy giá + fundamental
# ══════════════════════════════════════════════════════════════════════════════
def _from_yf(stock, price: float) -> dict:
    info = {}
    try:
        info = stock.info or {}
    except Exception:
        pass

    pe   = _f(info.get("trailingPE")) or _f(info.get("forwardPE"))
    pb   = _f(info.get("priceToBook"))
    eps  = _f(info.get("trailingEps"), lo=-1e9, hi=1e9)
    bvps = _f(info.get("bookValue"))
    roe  = _f(info.get("returnOnEquity"))
    roa  = _f(info.get("returnOnAssets"))
    mc   = _f(info.get("marketCap"), lo=0, hi=1e18)
    ls   = _f(info.get("sharesOutstanding"), lo=0, hi=1e15)
    exch = (info.get("exchange") or "HOSE").replace("HSX","HOSE").replace("VNM","HOSE")

    # Tính PE, PB từ financials nếu .info không có
    if not pe:
        try:
            inc = stock.income_stmt
            for key in ["Net Income", "Net Income Common Stockholders"]:
                if key in inc.index:
                    ni = float(inc.loc[key].dropna().iloc[0])
                    sh = _f(info.get("sharesOutstanding"), lo=1, hi=1e15)
                    if sh and ni > 0:
                        pe = round(price / (ni / sh), 2)
                    break
        except Exception:
            pass

    if not pb:
        try:
            bs = stock.balance_sheet
            for key in ["Stockholders Equity", "Total Stockholders Equity", "Common Stock Equity"]:
                if key in bs.index:
                    eq = float(bs.loc[key].dropna().iloc[0])
                    sh = _f(info.get("sharesOutstanding"), lo=1, hi=1e15)
                    if sh and eq > 0:
                        pb = round(price / (eq / sh), 2)
                    break
        except Exception:
            pass

    return {
        "pe":           pe   or "N/A",
        "pb":           pb   or "N/A",
        "eps":          eps,
        "bvps":         bvps or "N/A",
        "roe":          round(roe * 100, 2) if roe else "N/A",
        "roa":          round(roa * 100, 2) if roa else "N/A",
        "avg_pe":       0,
        "avg_pb":       0,
        "industry":     info.get("industry") or info.get("sector") or "N/A",
        "market":       exch,
        "market_cap":   round(mc / 1e9, 2) if mc else "N/A",
        "listed_shares": int(ls) if ls else "N/A",
    }


def _get_yf_price(ticker: str, region: str):
    """Lấy giá và cơ bản từ yfinance với retry."""
    suffix = REGION_SUFFIX.get(region, "")
    yf_str = f"{ticker}{suffix}"

    for attempt in range(3):
        try:
            stock = yf.Ticker(yf_str)
            df    = stock.history(period="5d", timeout=10)
            if df is None or df.empty:
                if suffix:
                    sb = yf.Ticker(ticker)
                    df2 = sb.history(period="5d", timeout=10)
                    if not df2.empty:
                        stock, df = sb, df2
            if df is None or df.empty:
                return None, None, None, None
            last   = df.iloc[-1]
            price  = round(float(last["Close"]), 2)
            volume = int(last["Volume"])
            prev   = round(float(df.iloc[-2]["Close"]), 2) if len(df) >= 2 else price
            return price, volume, prev, stock
        except Exception as e:
            err = str(e).lower()
            if ("ratelimit" in err or "429" in err) and attempt < 2:
                time.sleep((attempt + 1) * 3)
            elif "timeout" in err and attempt < 2:
                time.sleep(2)
            elif attempt == 2:
                return None, None, None, None
    return None, None, None, None


# ══════════════════════════════════════════════════════════════════════════════
#  MERGE & ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════
def _merge_fund(base: dict, extra: dict) -> dict:
    """Bổ sung fields còn thiếu từ extra vào base."""
    for key in ["pe","pb","eps","bvps","roe","roa","avg_pe","avg_pb",
                "industry","market","market_cap","listed_shares","circulating",
                "foreign_room","foreign_buy","foreign_sell",
                "ref_price","ceil_price","floor_price","open_price","high_price","low_price"]:
        if base.get(key) in (None, "N/A", 0, "") and extra.get(key) not in (None, "N/A", 0, ""):
            base[key] = extra[key]
    return base


def _get_fundamentals_vn(ticker: str, stock, price: float) -> dict:
    result   = {}
    errors   = {}
    fund_sources = [
        ("vndirect",  lambda: _from_vndirect_ratios(ticker)),
        ("tcbs",      lambda: _from_tcbs(ticker)),
        ("yf",        lambda: _from_yf(stock, price)),
    ]
    for name, fn in fund_sources:
        try:
            r = fn()
            if not result:
                result = r
            else:
                result = _merge_fund(result, r)
            # Nếu đã đủ PE, PB, EPS thì dừng
            if all(result.get(k) not in (None, "N/A") for k in ["pe","pb","eps"]):
                break
        except Exception as e:
            errors[name] = str(e)[:60]

    if not result:
        result = {}
    result["_errors"] = errors
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  HÀM CHÍNH
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)   # Cache 1 phút (dữ liệu realtime)
def get_stock_data(ticker: str, region: str = "VN") -> dict:
    ticker = ticker.upper().strip()

    # ── Bước 1: Lấy giá từ yfinance ─────────────────────────────────────────
    price, volume, prev_close, stock = _get_yf_price(ticker, region)
    if price is None:
        return {"error": f"Không tìm thấy mã **'{ticker}'**. Kiểm tra mã hoặc khu vực."}

    result = {
        "ticker":    ticker,
        "price":     price,
        "volume":    volume or 0,
        "prev_close": prev_close,
        # Tính trần/sàn theo quy tắc HOSE ±7%, HNX ±10%, UPCOM ±15%
        # (sẽ được ghi đè bởi SSI nếu có)
        "ref_price":  prev_close,
        "ceil_price": round(prev_close * 1.07, 2) if prev_close else "N/A",
        "floor_price": round(prev_close * 0.93, 2) if prev_close else "N/A",
    }

    if region == "VN":
        # ── Bước 2: Lấy dữ liệu realtime từ SSI (trần/sàn/room NN chính xác) ─
        try:
            ssi = _from_ssi(ticker)
            result.update(ssi)
        except Exception as e:
            result["_ssi_error"] = str(e)[:60]

        # ── Bước 3: Lấy fundamentals (PE, PB, EPS...) ───────────────────────
        fund = _get_fundamentals_vn(ticker, stock, price)
        result = _merge_fund(result, fund)
        if "_errors" in fund:
            result["_fund_errors"] = fund["_errors"]

    else:
        fund = _from_yf(stock, price)
        result.update(fund)

    # ── Tính % thay đổi so tham chiếu ─────────────────────────────────────────
    ref = result.get("ref_price") or prev_close
    if ref and ref > 0:
        result["price_change"]    = round(price - ref, 2)
        result["price_change_pct"] = round((price - ref) / ref * 100, 2)
    else:
        result["price_change"]    = 0
        result["price_change_pct"] = 0

    return result
