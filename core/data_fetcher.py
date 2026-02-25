"""
core/data_fetcher.py — v3.0 DEFINITIVE
PE/PB strategy:
  1. yfinance .info (trailingPE, priceToBook) — nhanh nhất
  2. Tính PE = Price / EPS từ income_stmt
  3. Tính PB = Price / Book Value từ balance_sheet  
  4. TCBS API (có avg_pe, avg_pb) — thử dù biết hay bị block
"""
import yfinance as yf
import requests
import streamlit as st
import urllib3, time, re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REGION_SUFFIX = {"VN": ".VN", "US": "", "INTL": ""}

def _f(v, lo=0.01, hi=5000):
    try:
        x = float(v)
        return round(x, 2) if lo < x < hi else None
    except Exception:
        return None


def _from_yf_info(stock) -> dict:
    """Nguồn 1: yfinance .info"""
    info = {}
    try:
        info = stock.info or {}
    except Exception:
        pass
    pe = _f(info.get("trailingPE")) or _f(info.get("forwardPE"))
    pb = _f(info.get("priceToBook"))
    ind = info.get("industry") or info.get("sector") or "N/A"
    exch = info.get("exchange") or info.get("fullExchangeName") or "HOSE"
    exch = exch.replace("HSX","HOSE").replace("VNM","HOSE")
    if not pe and not pb:
        raise Exception("no PE/PB in .info")
    return {"pe": pe or "N/A", "pb": pb or "N/A",
            "industry": ind, "avg_pe": 0, "avg_pb": 0, "market": exch}


def _from_yf_financials(stock, price: float) -> dict:
    """
    Nguồn 2: Tính PE, PB từ báo cáo tài chính yfinance
    PE = Giá / EPS_trailing
    PB = Giá / (Book Value per Share)
    """
    pe, pb = None, None

    # ── Tính PE từ income statement ─────────────────────────────────────────
    try:
        inc = stock.income_stmt          # annual
        if inc is not None and not inc.empty:
            ni_row = None
            for key in ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operations"]:
                if key in inc.index:
                    ni_row = inc.loc[key].dropna()
                    break
            if ni_row is not None and len(ni_row) >= 1:
                net_income = float(ni_row.iloc[0])  # Năm gần nhất
                shares = None
                try:
                    fi = stock.fast_info
                    shares = getattr(fi, "shares", None)
                except Exception:
                    pass
                if not shares:
                    try:
                        shares = stock.info.get("sharesOutstanding")
                    except Exception:
                        pass
                if shares and shares > 0 and net_income > 0:
                    eps = net_income / shares
                    pe_calc = price / eps
                    pe = _f(pe_calc, 0.1, 500)
    except Exception:
        pass

    # ── Tính PB từ balance sheet ─────────────────────────────────────────────
    try:
        bs = stock.balance_sheet
        if bs is not None and not bs.empty:
            eq_row = None
            for key in ["Stockholders Equity", "Total Stockholders Equity",
                        "Common Stock Equity", "Total Equity Gross Minority Interest"]:
                if key in bs.index:
                    eq_row = bs.loc[key].dropna()
                    break
            if eq_row is not None and len(eq_row) >= 1:
                equity = float(eq_row.iloc[0])
                shares = None
                try:
                    fi = stock.fast_info
                    shares = getattr(fi, "shares", None)
                except Exception:
                    pass
                if not shares:
                    try:
                        shares = stock.info.get("sharesOutstanding")
                    except Exception:
                        pass
                if shares and shares > 0 and equity > 0:
                    bvps = equity / shares
                    pb_calc = price / bvps
                    pb = _f(pb_calc, 0.01, 100)
    except Exception:
        pass

    if pe is None and pb is None:
        raise Exception("financials: PE và PB đều None")

    return {"pe": pe or "N/A", "pb": pb or "N/A",
            "industry": "N/A", "avg_pe": 0, "avg_pb": 0, "market": "HOSE"}


def _from_tcbs(ticker: str) -> dict:
    """Nguồn 3: TCBS — có avg_pe/avg_pb, hay bị block từ US"""
    url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview"
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Origin": "https://tcinvest.tcbs.com.vn",
        "Referer": "https://tcinvest.tcbs.com.vn/",
    }
    r = requests.get(url, headers=hdrs, timeout=8, verify=False)
    if r.status_code != 200:
        raise Exception(f"TCBS {r.status_code}")
    d = r.json()
    pe = _f(d.get("pe")); pb = _f(d.get("pb"))
    if not pe and not pb:
        raise Exception("TCBS empty")
    return {
        "pe": pe or "N/A", "pb": pb or "N/A",
        "industry": d.get("industryName","N/A"),
        "avg_pe": _f(d.get("industryPe")) or 0,
        "avg_pb": _f(d.get("industryPb")) or 0,
        "market": d.get("exchange","HOSE").replace("HSX","HOSE"),
    }


def _from_vndirect(ticker: str) -> dict:
    """Nguồn 4: VnDirect public API"""
    url = (f"https://finfo-api.vndirect.com.vn/v4/ratios/latest"
           f"?filter=code:{ticker}&fields=code,pe,pb,industryPe,industryPb,industryName,exchange")
    r = requests.get(url, headers={"User-Agent":"Mozilla/5.0","Accept":"application/json",
                                   "Referer":"https://www.vndirect.com.vn/"},
                     timeout=8, verify=False)
    if r.status_code != 200:
        raise Exception(f"VnDirect {r.status_code}")
    data = r.json().get("data", [])
    if not data:
        raise Exception("VnDirect empty")
    d = data[0]
    pe = _f(d.get("pe")); pb = _f(d.get("pb"))
    if not pe and not pb:
        raise Exception("VnDirect no pe/pb")
    return {
        "pe": pe or "N/A", "pb": pb or "N/A",
        "industry": d.get("industryName","N/A"),
        "avg_pe": _f(d.get("industryPe")) or 0,
        "avg_pb": _f(d.get("industryPb")) or 0,
        "market": d.get("exchange","HOSE").replace("HSX","HOSE"),
    }


def _merge(base: dict, extra: dict) -> dict:
    """Bổ sung avg_pe/avg_pb từ nguồn extra nếu base chưa có."""
    if base.get("avg_pe", 0) == 0 and extra.get("avg_pe", 0) != 0:
        base["avg_pe"] = extra["avg_pe"]
    if base.get("avg_pb", 0) == 0 and extra.get("avg_pb", 0) != 0:
        base["avg_pb"] = extra["avg_pb"]
    if base.get("industry") in ("N/A", None) and extra.get("industry") not in ("N/A", None):
        base["industry"] = extra["industry"]
    if base.get("market") in ("N/A", "HOSE") and extra.get("market") not in ("N/A",):
        base["market"] = extra["market"]
    return base


def _get_fundamentals_vn(ticker: str, stock, price: float) -> dict:
    result = None
    errors = {}

    # Bước 1: Lấy PE/PB từ 4 nguồn
    for name, fn in [
        ("yf_info",       lambda: _from_yf_info(stock)),
        ("tcbs",          lambda: _from_tcbs(ticker)),
        ("vndirect",      lambda: _from_vndirect(ticker)),
        ("yf_financials", lambda: _from_yf_financials(stock, price)),
    ]:
        try:
            r = fn()
            if r.get("pe") != "N/A" or r.get("pb") != "N/A":
                result = r
                # Bước 2: Bổ sung avg_pe/avg_pb nếu chưa có
                if result.get("avg_pe", 0) == 0:
                    for aname, afn in [("tcbs", lambda: _from_tcbs(ticker)),
                                       ("vndirect", lambda: _from_vndirect(ticker))]:
                        if aname == name:
                            continue
                        try:
                            result = _merge(result, afn())
                            break
                        except Exception:
                            pass
                break
        except Exception as e:
            errors[name] = str(e)[:60]

    if result:
        return result

    return {"pe":"N/A","pb":"N/A","industry":"N/A","avg_pe":0,"avg_pb":0,"market":"HOSE",
            "_errors": errors}


@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(ticker: str, region: str = "VN") -> dict:
    suffix = REGION_SUFFIX.get(region, "")
    yf_str = f"{ticker}{suffix}"
    price = volume = stock = None

    for attempt in range(3):
        try:
            stock = yf.Ticker(yf_str)
            df = stock.history(period="2d", timeout=10)
            if df is None or df.empty:
                if suffix:
                    sb = yf.Ticker(ticker)
                    df2 = sb.history(period="2d", timeout=10)
                    if not df2.empty:
                        stock, df = sb, df2
                if df is None or df.empty:
                    return {"error": f"Không tìm thấy mã **'{ticker}'**."}
            price = round(float(df["Close"].iloc[-1]), 2)
            volume = int(df["Volume"].iloc[-1])
            break
        except Exception as e:
            err = str(e).lower()
            if ("ratelimit" in err or "429" in err) and attempt < 2:
                time.sleep((attempt+1)*3); continue
            elif "timeout" in err and attempt < 2:
                time.sleep(2); continue
            elif attempt == 2:
                return {"error": f"Lỗi Yahoo Finance: {e}"}

    if price is None:
        return {"error": "Không lấy được giá."}

    fund = _get_fundamentals_vn(ticker, stock, price) if region == "VN" else _from_yf_info(stock)
    return {"ticker": ticker, "price": price, "volume": volume, **fund}
