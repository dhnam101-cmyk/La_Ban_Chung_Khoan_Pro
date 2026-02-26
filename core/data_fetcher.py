"""
core/data_fetcher.py — v6.0

FIX:
  ✅ KLCP lưu hành = Vốn hóa / Giá (tính ngay khi thiếu)
  ✅ Room NN: thêm 3 nguồn mới (SSI v1, Fireant, VnDirect extra)
  ✅ NN Mua/Bán: Fireant + SSI trading data
"""

import yfinance as yf
import requests
import streamlit as st
import urllib3, time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REGION_SUFFIX = {"VN": ".VN", "US": "", "INTL": ""}

_H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

def _f(v, lo=0.001, hi=999999999999):
    try:
        x = float(str(v).replace(",","").replace(" ",""))
        return round(x, 2) if lo < abs(x) < hi else None
    except: return None

def _i(v, lo=0):
    try:
        x = int(float(str(v).replace(",","").replace(" ","")))
        return x if x > lo else None
    except: return None


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN SSI iBoard v2 — giá realtime
# ══════════════════════════════════════════════════════════════════════════════
def _from_ssi_price(ticker: str) -> dict:
    headers = {**_H, "Origin": "https://iboard.ssi.com.vn",
               "Referer": "https://iboard.ssi.com.vn/"}
    result = {}

    # Thử endpoint v2 full
    for url, params in [
        ("https://iboard-query.ssi.com.vn/v2/stock/full",  {"symbol": ticker}),
        ("https://iboard-query.ssi.com.vn/v2/stock/price", {"symbol": ticker}),
        (f"https://iboard.ssi.com.vn/dchart/api/1.1/combinedquery?symbol={ticker}", {}),
    ]:
        try:
            r = requests.get(url, params=params, headers=headers, timeout=7, verify=False)
            if r.status_code != 200: continue
            raw = r.json()
            d = raw.get("data") or raw
            if isinstance(d, list):
                matched = [x for x in d if str(x.get("symbol","")).upper() == ticker.upper()]
                d = matched[0] if matched else {}
            if not d: continue

            def g(*keys):
                for k in keys:
                    v = d.get(k)
                    if v is not None and v != "" and v != 0: return v
                return None

            price  = _f(g("lastPrice","matchPrice","close","c"))
            ref    = _f(g("referencePrice","refPrice","r"))
            ceil   = _f(g("ceilPrice","ceiling","ce"))
            floor  = _f(g("floorPrice","floor","f"))
            open_p = _f(g("openPrice","open","o"))
            high   = _f(g("highPrice","high","h"))
            low    = _f(g("lowPrice","low","l"))
            vol    = _i(g("matchQty","totalMatchVolume","volume","mv","tv"), lo=0)
            fbuy   = _i(g("foreignBuyVolume","foreignBuyQtty","fBuyVol","fb"), lo=0)
            fsell  = _i(g("foreignSellVolume","foreignSellQtty","fSellVol","fs"), lo=0)
            room   = _f(g("currentRoom","foreignCurrentRoom","room","fr","fRoom"), lo=0, hi=100)
            ls     = _i(g("listedShare","shareIssued","listVol","listedVol"), lo=0)
            mc     = _f(g("marketCap","capitalization"), lo=0)
            exch   = str(g("exchange","floor","market") or "HOSE").upper().replace("HSX","HOSE")

            if price:
                result = {
                    "price": price, "ref_price": ref, "ceil_price": ceil,
                    "floor_price": floor, "open_price": open_p,
                    "high_price": high, "low_price": low,
                    "volume": vol or 0,
                    "foreign_buy": fbuy, "foreign_sell": fsell,
                    "foreign_room": room,
                    "listed_shares": ls,
                    "market_cap_raw": mc,  # raw số (VNĐ)
                    "market": exch,
                }
                break
        except Exception: continue

    if not result:
        raise Exception("SSI: no data from any endpoint")
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN Fireant — Room NN, NN Mua/Bán (public, không cần auth)
# ══════════════════════════════════════════════════════════════════════════════
def _from_fireant_foreign(ticker: str) -> dict:
    """
    Fireant public API cung cấp thông tin giao dịch nước ngoài.
    Không cần auth, thường không block IP nước ngoài.
    """
    # Endpoint 1: fundamental info có room NN
    url1 = f"https://restv2.fireant.vn/symbols/{ticker}/fundamental"
    headers = {**_H, "Origin": "https://fireant.vn", "Referer": "https://fireant.vn/"}

    result = {}
    try:
        r = requests.get(url1, headers=headers, timeout=7, verify=False)
        if r.status_code == 200:
            d = r.json()
            room = _f(d.get("foreignPercent") or d.get("foreignRoom") or d.get("foreignCurrentRoom"), lo=0, hi=100)
            ls   = _i(d.get("outstandingShare") or d.get("listedShare") or d.get("sharesOutstanding"), lo=0)
            mc   = _f(d.get("marketCap") or d.get("capitalisation"), lo=0)
            if room is not None: result["foreign_room"] = room
            if ls: result["listed_shares"] = ls
            if mc: result["market_cap_raw"] = mc
    except Exception: pass

    # Endpoint 2: trading data hôm nay có NN mua/bán
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    url2 = f"https://restv2.fireant.vn/symbols/{ticker}/trading-statistics?startDate={today}&endDate={today}"
    try:
        r2 = requests.get(url2, headers=headers, timeout=7, verify=False)
        if r2.status_code == 200:
            items = r2.json()
            d2 = items[0] if isinstance(items, list) and items else (items if isinstance(items, dict) else {})
            fbuy  = _i(d2.get("foreignBuyVolume") or d2.get("foreignBuy"), lo=0)
            fsell = _i(d2.get("foreignSellVolume") or d2.get("foreignSell"), lo=0)
            fval_buy  = _f(d2.get("foreignBuyValue"), lo=0)
            fval_sell = _f(d2.get("foreignSellValue"), lo=0)
            if fbuy is not None:  result["foreign_buy"] = fbuy
            if fsell is not None: result["foreign_sell"] = fsell
            if fval_buy:  result["foreign_buy_value"] = fval_buy
            if fval_sell: result["foreign_sell_value"] = fval_sell
    except Exception: pass

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN VnDirect — ratios: EPS, PE, PB, BVPS + room NN
# ══════════════════════════════════════════════════════════════════════════════
def _from_vndirect(ticker: str) -> dict:
    url = (
        "https://finfo-api.vndirect.com.vn/v4/ratios/latest"
        f"?filter=code:{ticker}"
        "&fields=code,pe,pb,eps,bvps,roe,roa,industryPe,industryPb,industryName,"
        "exchange,capitalisation,listedShare,outstandingShare,foreignPercent,foreignRoom"
    )
    r = requests.get(url, headers={**_H, "Referer": "https://www.vndirect.com.vn/"},
                     timeout=8, verify=False)
    if r.status_code != 200:
        raise Exception(f"VnDirect {r.status_code}")
    data = r.json().get("data", [])
    if not data: raise Exception("VnDirect empty")
    d = data[0]

    ls   = _i(d.get("listedShare") or d.get("outstandingShare"), lo=0)
    mc   = _f(d.get("capitalisation"), lo=0)
    room = _f(d.get("foreignPercent") or d.get("foreignRoom"), lo=0, hi=100)

    return {
        "pe":       _f(d.get("pe"))   or "N/A",
        "pb":       _f(d.get("pb"))   or "N/A",
        "eps":      _f(d.get("eps"), lo=-1e9, hi=1e9),
        "bvps":     _f(d.get("bvps")) or "N/A",
        "roe":      _f(d.get("roe"))  or "N/A",
        "roa":      _f(d.get("roa"))  or "N/A",
        "avg_pe":   _f(d.get("industryPe")) or 0,
        "avg_pb":   _f(d.get("industryPb")) or 0,
        "industry": d.get("industryName", "N/A"),
        "market":   d.get("exchange","HOSE").replace("HSX","HOSE"),
        "listed_shares": ls,
        "market_cap_raw": mc,
        "foreign_room": room,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN TCBS
# ══════════════════════════════════════════════════════════════════════════════
def _from_tcbs(ticker: str) -> dict:
    r = requests.get(
        f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview",
        headers={**_H, "Origin":"https://tcinvest.tcbs.com.vn","Referer":"https://tcinvest.tcbs.com.vn/"},
        timeout=6, verify=False
    )
    if r.status_code != 200: raise Exception(f"TCBS {r.status_code}")
    d = r.json()
    ls = _i(d.get("outstandingShare") or d.get("shareIssued"), lo=0)
    mc = _f(d.get("marketCap"), lo=0)
    return {
        "pe":       _f(d.get("pe"))   or "N/A",
        "pb":       _f(d.get("pb"))   or "N/A",
        "eps":      _f(d.get("eps"), lo=-1e9, hi=1e9),
        "bvps":     _f(d.get("bvps")) or "N/A",
        "roe":      _f(d.get("roe"))  or "N/A",
        "roa":      _f(d.get("roa"))  or "N/A",
        "avg_pe":   _f(d.get("industryPe")) or 0,
        "avg_pb":   _f(d.get("industryPb")) or 0,
        "industry": d.get("industryName","N/A"),
        "market":   d.get("exchange","HOSE").replace("HSX","HOSE"),
        "listed_shares": ls,
        "market_cap_raw": mc,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  NGUỒN yfinance — fallback
# ══════════════════════════════════════════════════════════════════════════════
def _from_yf(stock, price: float) -> dict:
    info = {}
    try: info = stock.info or {}
    except: pass

    pe   = _f(info.get("trailingPE")) or _f(info.get("forwardPE"))
    pb   = _f(info.get("priceToBook"))
    eps  = _f(info.get("trailingEps"), lo=-1e9, hi=1e9)
    bvps = _f(info.get("bookValue"))
    roe  = _f(info.get("returnOnEquity"))
    roa  = _f(info.get("returnOnAssets"))
    mc   = _f(info.get("marketCap"), lo=0)
    ls   = _i(info.get("sharesOutstanding"), lo=0)
    exch = (info.get("exchange") or "HOSE").replace("HSX","HOSE").replace("VNM","HOSE")

    # Tính PE, PB từ financials nếu thiếu
    if not pe:
        try:
            inc = stock.income_stmt
            for key in ["Net Income","Net Income Common Stockholders"]:
                if key in inc.index:
                    ni = float(inc.loc[key].dropna().iloc[0])
                    if ls and ni > 0: pe = round(price / (ni/ls), 2)
                    break
        except: pass
    if not pb:
        try:
            bs = stock.balance_sheet
            for key in ["Stockholders Equity","Total Stockholders Equity","Common Stock Equity"]:
                if key in bs.index:
                    eq = float(bs.loc[key].dropna().iloc[0])
                    if ls and eq > 0: pb = round(price / (eq/ls), 2)
                    break
        except: pass

    return {
        "pe": pe or "N/A", "pb": pb or "N/A",
        "eps": eps, "bvps": bvps or "N/A",
        "roe": round(roe*100,2) if roe else "N/A",
        "roa": round(roa*100,2) if roa else "N/A",
        "avg_pe": 0, "avg_pb": 0,
        "industry": info.get("industry") or info.get("sector") or "N/A",
        "market": exch,
        "listed_shares": ls,
        "market_cap_raw": mc,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  MERGE
# ══════════════════════════════════════════════════════════════════════════════
def _merge(base: dict, extra: dict) -> dict:
    for key in ["pe","pb","eps","bvps","roe","roa","avg_pe","avg_pb",
                "industry","market","market_cap_raw","listed_shares",
                "foreign_room","foreign_buy","foreign_sell",
                "foreign_buy_value","foreign_sell_value",
                "ref_price","ceil_price","floor_price",
                "open_price","high_price","low_price"]:
        v_base  = base.get(key)
        v_extra = extra.get(key)
        if v_base in (None, "N/A", 0, "") and v_extra not in (None, "N/A", 0, ""):
            base[key] = v_extra
    return base


# ══════════════════════════════════════════════════════════════════════════════
#  YFinance price
# ══════════════════════════════════════════════════════════════════════════════
def _get_yf_price(ticker: str, region: str):
    suffix = REGION_SUFFIX.get(region, "")
    for attempt in range(3):
        try:
            stock = yf.Ticker(f"{ticker}{suffix}")
            df = stock.history(period="5d", timeout=10)
            if df is None or df.empty:
                if suffix:
                    s2 = yf.Ticker(ticker)
                    df2 = s2.history(period="5d", timeout=10)
                    if not df2.empty:
                        stock, df = s2, df2
            if df is None or df.empty: return None, None, None, None
            price  = round(float(df["Close"].iloc[-1]), 2)
            volume = int(df["Volume"].iloc[-1])
            prev   = round(float(df["Close"].iloc[-2]), 2) if len(df)>=2 else price
            return price, volume, prev, stock
        except Exception as e:
            err = str(e).lower()
            if ("ratelimit" in err or "429" in err) and attempt < 2: time.sleep((attempt+1)*3)
            elif "timeout" in err and attempt < 2: time.sleep(2)
            elif attempt == 2: return None, None, None, None
    return None, None, None, None


# ══════════════════════════════════════════════════════════════════════════════
#  HÀM CHÍNH
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def get_stock_data(ticker: str, region: str = "VN") -> dict:
    ticker = ticker.upper().strip()

    price, volume, prev_close, stock = _get_yf_price(ticker, region)
    if price is None:
        return {"error": f"Không tìm thấy mã **'{ticker}'**."}

    result = {
        "ticker": ticker, "price": price,
        "volume": volume or 0, "prev_close": prev_close,
        "ref_price": prev_close,
        "ceil_price": round(prev_close * 1.07, 2) if prev_close else "N/A",
        "floor_price": round(prev_close * 0.93, 2) if prev_close else "N/A",
    }
    errors = {}

    if region == "VN":
        # Layer 1: SSI realtime price data
        try:
            result = _merge(result, _from_ssi_price(ticker))
        except Exception as e:
            errors["ssi"] = str(e)[:60]

        # Layer 2: VnDirect fundamentals + extra fields
        try:
            result = _merge(result, _from_vndirect(ticker))
        except Exception as e:
            errors["vndirect"] = str(e)[:60]

        # Layer 3: Fireant foreign trading
        try:
            result = _merge(result, _from_fireant_foreign(ticker))
        except Exception as e:
            errors["fireant"] = str(e)[:60]

        # Layer 4: TCBS fallback
        try:
            result = _merge(result, _from_tcbs(ticker))
        except Exception as e:
            errors["tcbs"] = str(e)[:60]

        # Layer 5: yfinance fallback
        try:
            result = _merge(result, _from_yf(stock, price))
        except Exception as e:
            errors["yf"] = str(e)[:60]

    else:
        try:
            result = _merge(result, _from_yf(stock, price))
        except: pass

    # ── Tính KLCP lưu hành = Vốn hóa / Giá ────────────────────────────────
    mc_raw = result.get("market_cap_raw")
    ls     = result.get("listed_shares")

    # Tính market_cap (tỷ đồng) từ raw nếu chưa có
    if mc_raw and mc_raw > 0:
        # mc_raw có thể là tỷ đồng hoặc đồng — heuristic
        if mc_raw > 1e12:       # > 1 nghìn tỷ đồng → đơn vị đồng
            result["market_cap"] = round(mc_raw / 1e9, 2)
        elif mc_raw > 1e6:      # > 1 triệu → đơn vị triệu đồng
            result["market_cap"] = round(mc_raw / 1e3, 2)
        else:                   # Đã là tỷ đồng
            result["market_cap"] = round(mc_raw, 2)
    else:
        result["market_cap"] = "N/A"

    # Tính KLCP lưu hành từ Vốn hóa / Giá nếu chưa có
    if not ls and mc_raw and mc_raw > 0 and price > 0:
        # Đổi mc_raw về VNĐ để chia cho giá VNĐ
        if mc_raw > 1e12:   mc_vnd = mc_raw
        elif mc_raw > 1e6:  mc_vnd = mc_raw * 1e6
        else:               mc_vnd = mc_raw * 1e9
        ls_calc = int(mc_vnd / price)
        if ls_calc > 1000:
            result["listed_shares"] = ls_calc
            result["circulating"]   = ls_calc
    else:
        result["circulating"] = ls

    # ── Giá % thay đổi ──────────────────────────────────────────────────────
    ref = result.get("ref_price") or prev_close
    if ref and ref > 0:
        result["price_change"]     = round(price - ref, 2)
        result["price_change_pct"] = round((price - ref) / ref * 100, 2)
    else:
        result["price_change"] = result["price_change_pct"] = 0

    result["_errors"] = errors
    return result
