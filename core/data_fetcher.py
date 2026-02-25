"""
data_fetcher.py — v4.0 FLAT STRUCTURE
Lấy giá + fundamental từ yfinance (income_stmt, balance_sheet).
Không phụ thuộc API VN vì đều bị block từ US server.
"""
import yfinance as yf
import requests
import streamlit as st
import urllib3, time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REGION_SUFFIX = {"VN": ".VN", "US": "", "INTL": ""}


def _f(v, lo=0.01, hi=5000):
    try:
        x = float(v)
        return round(x, 2) if lo < x < hi else None
    except Exception:
        return None


def _get_shares(stock):
    """Lấy số lượng cổ phiếu lưu hành từ nhiều nguồn."""
    try:
        s = getattr(stock.fast_info, "shares", None)
        if s and s > 0: return s
    except Exception:
        pass
    try:
        s = stock.info.get("sharesOutstanding")
        if s and s > 0: return s
    except Exception:
        pass
    return None


def _from_yf_info(stock) -> dict:
    """Lấy PE, PB trực tiếp từ yfinance .info"""
    info = {}
    try:
        info = stock.info or {}
    except Exception:
        pass
    pe = _f(info.get("trailingPE")) or _f(info.get("forwardPE"))
    pb = _f(info.get("priceToBook"))
    if not pe and not pb:
        raise Exception("yf_info: no PE/PB")
    ind  = info.get("industry") or info.get("sector") or "N/A"
    exch = (info.get("exchange") or info.get("fullExchangeName") or "HOSE")
    exch = exch.replace("HSX", "HOSE").replace("VNM", "HOSE")
    return {"pe": pe or "N/A", "pb": pb or "N/A",
            "industry": ind, "avg_pe": 0, "avg_pb": 0, "market": exch}


def _from_yf_financials(stock, price: float) -> dict:
    """Tính PE từ income_stmt, PB từ balance_sheet — hoạt động dù API VN bị block."""
    pe = pb = None

    # PE = Price / EPS (net income / shares)
    try:
        inc = stock.income_stmt
        if inc is not None and not inc.empty:
            for key in ["Net Income", "Net Income Common Stockholders",
                        "Net Income From Continuing Operations"]:
                if key in inc.index:
                    ni = inc.loc[key].dropna()
                    if len(ni) >= 1 and float(ni.iloc[0]) > 0:
                        shares = _get_shares(stock)
                        if shares:
                            eps = float(ni.iloc[0]) / shares
                            pe = _f(price / eps, 0.5, 500)
                    break
    except Exception:
        pass

    # PB = Price / BVPS (equity / shares)
    try:
        bs = stock.balance_sheet
        if bs is not None and not bs.empty:
            for key in ["Stockholders Equity", "Total Stockholders Equity",
                        "Common Stock Equity", "Total Equity Gross Minority Interest"]:
                if key in bs.index:
                    eq = bs.loc[key].dropna()
                    if len(eq) >= 1 and float(eq.iloc[0]) > 0:
                        shares = _get_shares(stock)
                        if shares:
                            bvps = float(eq.iloc[0]) / shares
                            pb = _f(price / bvps, 0.05, 100)
                    break
    except Exception:
        pass

    if not pe and not pb:
        raise Exception("financials: cả PE và PB đều None")

    return {"pe": pe or "N/A", "pb": pb or "N/A",
            "industry": "N/A", "avg_pe": 0, "avg_pb": 0, "market": "HOSE"}


def _from_tcbs(ticker: str) -> dict:
    """TCBS — thường bị block từ US nhưng thử vẫn tốt hơn không."""
    r = requests.get(
        f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview",
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json",
                 "Origin": "https://tcinvest.tcbs.com.vn",
                 "Referer": "https://tcinvest.tcbs.com.vn/"},
        timeout=6, verify=False
    )
    if r.status_code != 200:
        raise Exception(f"TCBS {r.status_code}")
    d = r.json()
    pe = _f(d.get("pe")); pb = _f(d.get("pb"))
    if not pe and not pb:
        raise Exception("TCBS no data")
    return {
        "pe": pe or "N/A", "pb": pb or "N/A",
        "industry": d.get("industryName", "N/A"),
        "avg_pe": _f(d.get("industryPe")) or 0,
        "avg_pb": _f(d.get("industryPb")) or 0,
        "market": d.get("exchange", "HOSE").replace("HSX", "HOSE"),
    }


def _get_fundamentals(ticker: str, stock, price: float, region: str) -> dict:
    errors  = {}
    sources = [
        ("yf_info",  lambda: _from_yf_info(stock)),
        ("tcbs",     lambda: _from_tcbs(ticker)),
        ("yf_calc",  lambda: _from_yf_financials(stock, price)),
    ]
    if region != "VN":
        sources = [("yf_info", lambda: _from_yf_info(stock))]

    for name, fn in sources:
        try:
            r = fn()
            if r.get("pe") != "N/A" or r.get("pb") != "N/A":
                return r
        except Exception as e:
            errors[name] = str(e)[:60]

    return {"pe": "N/A", "pb": "N/A", "industry": "N/A",
            "avg_pe": 0, "avg_pb": 0, "market": "HOSE", "_errors": errors}


@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(ticker: str, region: str = "VN") -> dict:
    suffix = REGION_SUFFIX.get(region, "")
    yf_str = f"{ticker}{suffix}"
    price = volume = stock = None

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
                    return {"error": f"Không tìm thấy mã **'{ticker}'**."}
            price  = round(float(df["Close"].iloc[-1]), 2)
            volume = int(df["Volume"].iloc[-1])
            break
        except Exception as e:
            err = str(e).lower()
            if ("ratelimit" in err or "429" in err) and attempt < 2:
                time.sleep((attempt + 1) * 3)
            elif "timeout" in err and attempt < 2:
                time.sleep(2)
            elif attempt == 2:
                return {"error": f"Lỗi Yahoo Finance: {e}"}

    if price is None:
        return {"error": "Không lấy được giá."}

    fund = _get_fundamentals(ticker, stock, price, region)
    return {"ticker": ticker, "price": price, "volume": volume, **fund}
