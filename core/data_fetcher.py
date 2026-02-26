"""
core/data_fetcher.py — v7.0

KEY FIX:
  ✅ Vốn hóa = KLCP niêm yết × Giá hiện tại (tính ngay, không chờ API)
  ✅ KLCP lưu hành đã có từ yfinance (sharesOutstanding) → dùng luôn
  ✅ Giá mở cửa/cao/thấp lấy từ yfinance history (luôn có)
  ✅ Room NN: thử nhiều endpoint SSI + Fireant + VnDirect
  ✅ NN Mua/Bán: Fireant trading API
"""

import yfinance as yf
import requests
import streamlit as st
import urllib3, time
from datetime import date

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REGION_SUFFIX = {"VN": ".VN", "US": "", "INTL": ""}

_H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


def _f(v, lo=0.001, hi=1e15):
    try:
        x = float(str(v).replace(",", "").replace(" ", ""))
        return round(x, 2) if lo < abs(x) < hi else None
    except:
        return None


def _i(v, lo=1):
    try:
        x = int(float(str(v).replace(",", "").replace(" ", "")))
        return x if x >= lo else None
    except:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 1: yfinance — giá đầy đủ (open/high/low/close) + shares + fundamentals
# ══════════════════════════════════════════════════════════════════════════════
def _get_yf_full(ticker: str, region: str):
    """
    Lấy toàn bộ giá (mở cửa, cao, thấp, đóng), volume, shares từ yfinance.
    Đây là nguồn CHẮC CHẮN hoạt động.
    """
    suffix = REGION_SUFFIX.get(region, "")
    stock = None
    price = open_p = high = low = prev = volume = None
    shares = None

    for attempt in range(3):
        try:
            s = yf.Ticker(f"{ticker}{suffix}")
            df = s.history(period="5d", timeout=12)
            if df is None or df.empty:
                if suffix:
                    s2 = yf.Ticker(ticker)
                    df2 = s2.history(period="5d", timeout=12)
                    if not df2.empty:
                        s, df = s2, df2
            if df is None or df.empty:
                return None, None, None, None, None, None, None, None, None

            last = df.iloc[-1]
            price  = round(float(last["Close"]), 2)
            open_p = round(float(last["Open"]),  2) if last["Open"]  > 0 else None
            high   = round(float(last["High"]),  2) if last["High"]  > 0 else None
            low    = round(float(last["Low"]),   2) if last["Low"]   > 0 else None
            volume = int(last["Volume"])
            prev   = round(float(df.iloc[-2]["Close"]), 2) if len(df) >= 2 else price
            stock  = s

            # Lấy shares từ fast_info (nhanh hơn .info)
            try:
                fi = s.fast_info
                sh = getattr(fi, "shares", None)
                if sh and sh > 0:
                    shares = int(sh)
            except:
                pass

            break
        except Exception as e:
            err = str(e).lower()
            if ("ratelimit" in err or "429" in err) and attempt < 2:
                time.sleep((attempt + 1) * 3)
            elif "timeout" in err and attempt < 2:
                time.sleep(2)
            elif attempt == 2:
                return None, None, None, None, None, None, None, None, None

    return price, open_p, high, low, volume, prev, stock, shares, suffix


def _get_yf_fundamentals(stock, price: float, shares: int) -> dict:
    """Lấy PE, PB, EPS, BVPS, ROE, ROA từ yfinance."""
    info = {}
    try:
        info = stock.info or {}
    except:
        pass

    pe   = _f(info.get("trailingPE")) or _f(info.get("forwardPE"))
    pb   = _f(info.get("priceToBook"))
    eps  = _f(info.get("trailingEps"), lo=-1e9, hi=1e9)
    bvps = _f(info.get("bookValue"))
    roe  = _f(info.get("returnOnEquity"))
    roa  = _f(info.get("returnOnAssets"))
    mc   = _f(info.get("marketCap"), lo=0)
    sh   = shares or _i(info.get("sharesOutstanding"), lo=1000)
    exch = (info.get("exchange") or "HOSE").replace("HSX", "HOSE").replace("VNM", "HOSE")

    # Fallback PE từ income_stmt
    if not pe and sh:
        try:
            inc = stock.income_stmt
            for key in ["Net Income", "Net Income Common Stockholders"]:
                if key in inc.index:
                    ni = float(inc.loc[key].dropna().iloc[0])
                    if ni > 0:
                        pe = round(price / (ni / sh), 2)
                    break
        except:
            pass

    # Fallback PB từ balance_sheet
    if not pb and sh:
        try:
            bs = stock.balance_sheet
            for key in ["Stockholders Equity", "Total Stockholders Equity", "Common Stock Equity"]:
                if key in bs.index:
                    eq = float(bs.loc[key].dropna().iloc[0])
                    if eq > 0:
                        pb = round(price / (eq / sh), 2)
                    break
        except:
            pass

    return {
        "pe": pe or "N/A", "pb": pb or "N/A",
        "eps": eps, "bvps": bvps or "N/A",
        "roe": round(roe * 100, 2) if roe else "N/A",
        "roa": round(roa * 100, 2) if roa else "N/A",
        "avg_pe": 0, "avg_pb": 0,
        "industry": info.get("industry") or info.get("sector") or "N/A",
        "market": exch,
        "shares_yf": sh,
        "mc_yf": mc,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 2: VnDirect — ratios đầy đủ + shares + room NN
# ══════════════════════════════════════════════════════════════════════════════
def _from_vndirect(ticker: str) -> dict:
    url = (
        "https://finfo-api.vndirect.com.vn/v4/ratios/latest"
        f"?filter=code:{ticker}"
        "&fields=code,pe,pb,eps,bvps,roe,roa,industryPe,industryPb,industryName,"
        "exchange,capitalisation,listedShare,outstandingShare,foreignPercent"
    )
    r = requests.get(url, headers={**_H, "Referer": "https://www.vndirect.com.vn/"},
                     timeout=8, verify=False)
    if r.status_code != 200:
        raise Exception(f"VnDirect HTTP {r.status_code}")
    data = r.json().get("data", [])
    if not data:
        raise Exception("VnDirect empty")
    d = data[0]

    ls   = _i(d.get("listedShare") or d.get("outstandingShare"), lo=1000)
    mc   = _f(d.get("capitalisation"), lo=0)
    room = _f(d.get("foreignPercent"), lo=0, hi=100)

    return {
        "pe":       _f(d.get("pe"))  or "N/A",
        "pb":       _f(d.get("pb"))  or "N/A",
        "eps":      _f(d.get("eps"), lo=-1e9, hi=1e9),
        "bvps":     _f(d.get("bvps")) or "N/A",
        "roe":      _f(d.get("roe")) or "N/A",
        "roa":      _f(d.get("roa")) or "N/A",
        "avg_pe":   _f(d.get("industryPe")) or 0,
        "avg_pb":   _f(d.get("industryPb")) or 0,
        "industry": d.get("industryName", "N/A"),
        "market":   d.get("exchange", "HOSE").replace("HSX", "HOSE"),
        "listed_shares_vnd": ls,
        "mc_vnd":   mc,
        "foreign_room": room,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 3: TCBS
# ══════════════════════════════════════════════════════════════════════════════
def _from_tcbs(ticker: str) -> dict:
    r = requests.get(
        f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview",
        headers={**_H, "Origin": "https://tcinvest.tcbs.com.vn",
                 "Referer": "https://tcinvest.tcbs.com.vn/"},
        timeout=6, verify=False
    )
    if r.status_code != 200:
        raise Exception(f"TCBS {r.status_code}")
    d = r.json()
    ls = _i(d.get("outstandingShare") or d.get("shareIssued"), lo=1000)
    mc = _f(d.get("marketCap"), lo=0)
    return {
        "pe":    _f(d.get("pe"))  or "N/A",
        "pb":    _f(d.get("pb"))  or "N/A",
        "eps":   _f(d.get("eps"), lo=-1e9, hi=1e9),
        "bvps":  _f(d.get("bvps")) or "N/A",
        "roe":   _f(d.get("roe")) or "N/A",
        "roa":   _f(d.get("roa")) or "N/A",
        "avg_pe": _f(d.get("industryPe")) or 0,
        "avg_pb": _f(d.get("industryPb")) or 0,
        "industry": d.get("industryName", "N/A"),
        "market":   d.get("exchange", "HOSE").replace("HSX", "HOSE"),
        "listed_shares_tcbs": ls,
        "mc_tcbs": mc,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 4: Fireant — foreign trading data
# ══════════════════════════════════════════════════════════════════════════════
def _from_fireant(ticker: str) -> dict:
    result = {}
    headers = {**_H, "Origin": "https://fireant.vn", "Referer": "https://fireant.vn/"}

    # Fundamental: room NN, shares
    try:
        r = requests.get(f"https://restv2.fireant.vn/symbols/{ticker}/fundamental",
                         headers=headers, timeout=7, verify=False)
        if r.status_code == 200:
            d = r.json()
            room = _f(d.get("foreignPercent") or d.get("foreignRoom"), lo=0, hi=100)
            ls   = _i(d.get("outstandingShare") or d.get("listedShare"), lo=1000)
            mc   = _f(d.get("marketCap") or d.get("capitalisation"), lo=0)
            if room is not None: result["foreign_room"] = room
            if ls:   result["fa_shares"] = ls
            if mc:   result["fa_mc"] = mc
    except:
        pass

    # Trading stats: NN mua/bán hôm nay
    try:
        today = date.today().strftime("%Y-%m-%d")
        r2 = requests.get(
            f"https://restv2.fireant.vn/symbols/{ticker}/trading-statistics"
            f"?startDate={today}&endDate={today}",
            headers=headers, timeout=7, verify=False
        )
        if r2.status_code == 200:
            items = r2.json()
            d2 = items[0] if isinstance(items, list) and items else {}
            fbuy  = _i(d2.get("foreignBuyVolume")  or d2.get("foreignBuy"),  lo=0)
            fsell = _i(d2.get("foreignSellVolume") or d2.get("foreignSell"), lo=0)
            fbuyv  = _f(d2.get("foreignBuyValue"),  lo=0)
            fsellv = _f(d2.get("foreignSellValue"), lo=0)
            if fbuy  is not None: result["foreign_buy"]        = fbuy
            if fsell is not None: result["foreign_sell"]       = fsell
            if fbuyv:             result["foreign_buy_value"]  = fbuyv
            if fsellv:            result["foreign_sell_value"] = fsellv
    except:
        pass

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN 5: SSI — realtime (giá mở/cao/thấp, room NN)
# ══════════════════════════════════════════════════════════════════════════════
def _from_ssi(ticker: str) -> dict:
    headers = {**_H, "Origin": "https://iboard.ssi.com.vn",
               "Referer": "https://iboard.ssi.com.vn/"}
    endpoints = [
        ("https://iboard-query.ssi.com.vn/v2/stock/full",  {"symbol": ticker}),
        ("https://iboard-query.ssi.com.vn/v2/stock/price", {"symbol": ticker}),
    ]
    for url, params in endpoints:
        try:
            r = requests.get(url, params=params, headers=headers, timeout=6, verify=False)
            if r.status_code != 200: continue
            raw = r.json()
            d   = raw.get("data") or raw
            if isinstance(d, list):
                matched = [x for x in d if str(x.get("symbol","")).upper() == ticker.upper()]
                d = matched[0] if matched else {}
            if not d: continue

            def g(*keys):
                for k in keys:
                    v = d.get(k)
                    if v not in (None, "", 0): return v
                return None

            open_p = _f(g("openPrice", "open", "o"))
            high   = _f(g("highPrice", "high", "h"))
            low    = _f(g("lowPrice",  "low",  "l"))
            ref    = _f(g("referencePrice", "refPrice", "r"))
            ceil   = _f(g("ceilPrice", "ceiling", "ce"))
            floor  = _f(g("floorPrice", "floor", "f"))
            room   = _f(g("currentRoom", "foreignCurrentRoom", "room", "fRoom"), lo=0, hi=100)
            fbuy   = _i(g("foreignBuyVolume",  "foreignBuyQtty",  "fb"), lo=0)
            fsell  = _i(g("foreignSellVolume", "foreignSellQtty", "fs"), lo=0)
            ls     = _i(g("listedShare", "shareIssued", "listVol"), lo=1000)
            exch   = str(g("exchange", "floor", "market") or "HOSE").upper().replace("HSX","HOSE")

            result = {}
            if open_p: result["open_price"]  = open_p
            if high:   result["high_price"]  = high
            if low:    result["low_price"]   = low
            if ref:    result["ref_price"]   = ref
            if ceil:   result["ceil_price"]  = ceil
            if floor:  result["floor_price"] = floor
            if room is not None: result["foreign_room"] = room
            if fbuy  is not None: result["foreign_buy"]  = fbuy
            if fsell is not None: result["foreign_sell"] = fsell
            if ls:     result["ssi_shares"] = ls
            if exch:   result["ssi_market"] = exch
            if result: return result
        except:
            continue
    return {}


# ══════════════════════════════════════════════════════════════════════════════
#  TỔNG HỢP
# ══════════════════════════════════════════════════════════════════════════════
def _pick(*vals, default="N/A"):
    """Trả về giá trị đầu tiên không phải None/"N/A"."""
    for v in vals:
        if v not in (None, "N/A", 0, ""):
            return v
    return default


@st.cache_data(ttl=60, show_spinner=False)
def get_stock_data(ticker: str, region: str = "VN") -> dict:
    ticker = ticker.upper().strip()

    # ── Bước 1: yfinance — giá + open/high/low + shares (LUÔN CÓ) ──────────
    price, open_p, high, low, volume, prev_close, stock, shares_yf, suffix = \
        _get_yf_full(ticker, region)

    if price is None:
        return {"error": f"Không tìm thấy mã **'{ticker}'**."}

    # Trần/sàn tạm tính (HOSE ±7%), sẽ ghi đè nếu SSI có
    ref_tmp = prev_close or price
    result = {
        "ticker":      ticker,
        "price":       price,
        "open_price":  open_p,
        "high_price":  high,
        "low_price":   low,
        "volume":      volume or 0,
        "prev_close":  prev_close,
        "ref_price":   prev_close,
        "ceil_price":  round(ref_tmp * 1.07, 2),
        "floor_price": round(ref_tmp * 0.93, 2),
        "shares_yf":   shares_yf,
    }
    errors = {}

    if region == "VN":
        # ── Bước 2: Fundamentals từ yfinance ──────────────────────────────
        yf_fund = _get_yf_fundamentals(stock, price, shares_yf)
        for k, v in yf_fund.items():
            if v not in (None, "N/A", 0, ""):
                result[k] = v

        # ── Bước 3: VnDirect — PE/PB chính xác hơn + shares + room NN ────
        vnd = {}
        try:
            vnd = _from_vndirect(ticker)
        except Exception as e:
            errors["vndirect"] = str(e)[:60]
        for k, v in vnd.items():
            if v not in (None, "N/A", 0, ""):
                result[k] = v

        # ── Bước 4: TCBS ──────────────────────────────────────────────────
        try:
            tcbs = _from_tcbs(ticker)
            for k, v in tcbs.items():
                if result.get(k) in (None, "N/A", 0, "") and v not in (None, "N/A", 0, ""):
                    result[k] = v
        except Exception as e:
            errors["tcbs"] = str(e)[:60]

        # ── Bước 5: SSI realtime (open/high/low, trần/sàn chính xác, room NN)
        try:
            ssi = _from_ssi(ticker)
            for k, v in ssi.items():
                if v not in (None, "N/A", 0, ""):
                    result[k] = v
        except Exception as e:
            errors["ssi"] = str(e)[:60]

        # ── Bước 6: Fireant — foreign trading ────────────────────────────
        try:
            fa = _from_fireant(ticker)
            for k, v in fa.items():
                if result.get(k) in (None, "N/A", 0, "") and v not in (None, "N/A", 0, ""):
                    result[k] = v
        except Exception as e:
            errors["fireant"] = str(e)[:60]

    else:
        yf_fund = _get_yf_fundamentals(stock, price, shares_yf)
        for k, v in yf_fund.items():
            if v not in (None, "N/A", 0, ""):
                result[k] = v

    # ── TỔNG HỢP KLCP & VỐN HÓA ───────────────────────────────────────────
    # Lấy số CP tốt nhất từ nhiều nguồn
    best_shares = _pick(
        result.get("listed_shares_vnd"),
        result.get("listed_shares_tcbs"),
        result.get("ssi_shares"),
        result.get("fa_shares"),
        result.get("shares_yf"),
    )
    if best_shares != "N/A":
        result["listed_shares"] = int(best_shares)
        result["circulating"]   = int(best_shares)

    # Tính Vốn hóa = KLCP × Giá (đơn vị tỷ đồng)
    ls = result.get("listed_shares")
    if ls and ls != "N/A" and price:
        mc_tdy = round(ls * price / 1e9, 2)
        result["market_cap"] = mc_tdy
    else:
        # Fallback từ API
        mc_raw = _pick(result.get("mc_vnd"), result.get("mc_tcbs"),
                       result.get("fa_mc"), result.get("mc_yf"))
        if mc_raw != "N/A":
            mc_raw = float(mc_raw)
            if mc_raw > 1e12:   result["market_cap"] = round(mc_raw / 1e9, 2)
            elif mc_raw > 1e9:  result["market_cap"] = round(mc_raw / 1e6, 2)
            elif mc_raw > 1e3:  result["market_cap"] = round(mc_raw / 1e3, 2)
            else:               result["market_cap"] = round(mc_raw, 2)

            # Tính ngược KLCP từ Vốn hóa nếu chưa có
            if not result.get("listed_shares"):
                mc_vnd = mc_raw
                if mc_raw > 1e12:   mc_vnd = mc_raw
                elif mc_raw > 1e9:  mc_vnd = mc_raw * 1e3
                elif mc_raw > 1e6:  mc_vnd = mc_raw * 1e6
                else:               mc_vnd = mc_raw * 1e9
                ls_calc = int(mc_vnd / price)
                if ls_calc > 100000:
                    result["listed_shares"] = ls_calc
                    result["circulating"]   = ls_calc
        else:
            result["market_cap"] = "N/A"

    # ── Thị trường tốt nhất ────────────────────────────────────────────────
    result["market"] = _pick(
        result.get("ssi_market"),
        result.get("market"),
        region
    )

    # ── Giá % thay đổi so tham chiếu ──────────────────────────────────────
    ref = result.get("ref_price") or prev_close or price
    result["price_change"]     = round(price - ref, 2)
    result["price_change_pct"] = round((price - ref) / ref * 100, 2) if ref else 0

    result["_errors"] = errors
    return result
