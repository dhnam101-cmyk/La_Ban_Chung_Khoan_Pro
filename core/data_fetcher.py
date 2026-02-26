"""
core/data_fetcher.py — v9.0

THỰC TẾ ĐÃ XÁC NHẬN:
  ✅ Hoạt động từ Streamlit Cloud (US server):
      - yfinance .info          → PE, PB (có), EPS/BVPS/ROE/ROA (không có cho VN)
      - yfinance fast_info      → shares, market_cap
      - yfinance income_stmt    → Net Income, Basic EPS (tính được EPS, ROE, ROA)
      - yfinance balance_sheet  → Equity, Total Assets (tính được BVPS, PB, ROE, ROA)
      - yfinance history(5d)    → open, high, low, close, volume

  ❌ BỊ BLOCK từ US server (DNS fail):
      - VnDirect, TCBS, SSI, Fireant, CafeF, HOSE, HNX

CHIẾN LƯỢC v9:
  Mọi field đều tính từ yfinance với NHIỀU LỚP fallback:
  
  EPS:   .info.trailingEps → income_stmt["Basic EPS"] → income_stmt["Diluted EPS"]
         → tính: Net Income / Shares
  
  BVPS:  .info.bookValue → tính: Total Equity / Shares
  
  ROE:   .info.returnOnEquity → tính: Net Income / Total Equity × 100
  
  ROA:   .info.returnOnAssets → tính: Net Income / Total Assets × 100
  
  PE:    .info.trailingPE → .info.forwardPE → tính: Price / EPS
  
  PB:    .info.priceToBook → tính: Price / BVPS
  
  Shares: fast_info.shares → .info.sharesOutstanding → income_stmt implied
  
  Room NN: Không lấy được → hiển thị N/A với note rõ lý do
  NN Mua/Bán: Không lấy được → N/A
  Giá open/high/low: yfinance history (LUÔN CÓ)
  Giá trần/sàn: tính ±7% từ prev_close (HOSE), chuẩn xác
"""

import yfinance as yf
import streamlit as st
import time

REGION_SUFFIX = {"VN": ".VN", "US": "", "INTL": ""}


def _f(v, lo=0.0001, hi=1e15):
    """Safe float với range check."""
    try:
        x = float(str(v).replace(",", "").replace(" ", ""))
        return round(x, 4) if lo < abs(x) < hi else None
    except:
        return None


def _i(v, lo=1):
    """Safe int."""
    try:
        x = int(float(str(v).replace(",", "").replace(" ", "")))
        return x if x >= lo else None
    except:
        return None


def _pick(*vals):
    """Giá trị đầu tiên hợp lệ."""
    for v in vals:
        if v not in (None, "N/A", "", 0):
            return v
    return None


def _get_row(df, *keys):
    """Lấy giá trị đầu tiên từ DataFrame theo tên row."""
    for k in keys:
        if k in df.index:
            row = df.loc[k].dropna()
            if len(row) >= 1:
                try:
                    return float(row.iloc[0])
                except:
                    pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  CÁC EXTERNAL APIs — thử nhưng không phụ thuộc
# ══════════════════════════════════════════════════════════════════════════════
def _try_vndirect(ticker: str) -> dict:
    try:
        import requests, urllib3
        urllib3.disable_warnings()
        url = (
            "https://finfo-api.vndirect.com.vn/v4/ratios/latest"
            f"?filter=code:{ticker}"
            "&fields=pe,pb,eps,bvps,roe,roa,industryPe,industryPb,industryName,"
            "exchange,capitalisation,listedShare,foreignPercent"
        )
        r = requests.get(url,
            headers={"User-Agent":"Mozilla/5.0","Accept":"application/json",
                     "Referer":"https://www.vndirect.com.vn/"},
            timeout=5, verify=False)
        if r.status_code != 200:
            return {}
        data = r.json().get("data", [])
        if not data:
            return {}
        d = data[0]
        def cv(v):  # VNĐ → nghìn đồng nếu cần
            f = _f(v, lo=-1e9, hi=1e9)
            return round(f/1000, 2) if f and abs(f) > 100 else f
        return {
            "pe_vd":   _f(d.get("pe")),
            "pb_vd":   _f(d.get("pb")),
            "eps_vd":  cv(d.get("eps")),
            "bvps_vd": cv(d.get("bvps")),
            "roe_vd":  _f(d.get("roe")),
            "roa_vd":  _f(d.get("roa")),
            "ape_vd":  _f(d.get("industryPe")),
            "apb_vd":  _f(d.get("industryPb")),
            "ind_vd":  d.get("industryName"),
            "mkt_vd":  d.get("exchange","").replace("HSX","HOSE"),
            "sh_vd":   _i(d.get("listedShare"), lo=1000),
            "mc_vd":   _f(d.get("capitalisation"), lo=0),
            "room_vd": _f(d.get("foreignPercent"), lo=0, hi=100),
        }
    except:
        return {}


def _try_tcbs(ticker: str) -> dict:
    try:
        import requests, urllib3
        urllib3.disable_warnings()
        r = requests.get(
            f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview",
            headers={"User-Agent":"Mozilla/5.0","Accept":"application/json",
                     "Origin":"https://tcinvest.tcbs.com.vn",
                     "Referer":"https://tcinvest.tcbs.com.vn/"},
            timeout=5, verify=False)
        if r.status_code != 200:
            return {}
        d = r.json()
        def cv(v):
            f = _f(v, lo=-1e9, hi=1e9)
            return round(f/1000, 2) if f and abs(f) > 100 else f
        return {
            "pe_tc":   _f(d.get("pe")),
            "pb_tc":   _f(d.get("pb")),
            "eps_tc":  cv(d.get("eps")),
            "bvps_tc": cv(d.get("bvps")),
            "roe_tc":  _f(d.get("roe")),
            "roa_tc":  _f(d.get("roa")),
            "ape_tc":  _f(d.get("industryPe")),
            "apb_tc":  _f(d.get("industryPb")),
            "ind_tc":  d.get("industryName"),
            "mkt_tc":  d.get("exchange","").replace("HSX","HOSE"),
            "sh_tc":   _i(d.get("outstandingShare") or d.get("shareIssued"), lo=1000),
            "mc_tc":   _f(d.get("marketCap"), lo=0),
        }
    except:
        return {}


def _try_ssi_room(ticker: str) -> dict:
    try:
        import requests, urllib3
        urllib3.disable_warnings()
        r = requests.get(
            "https://iboard-query.ssi.com.vn/v2/stock/full",
            params={"symbol": ticker},
            headers={"User-Agent":"Mozilla/5.0","Accept":"application/json",
                     "Origin":"https://iboard.ssi.com.vn",
                     "Referer":"https://iboard.ssi.com.vn/"},
            timeout=5, verify=False)
        if r.status_code != 200:
            return {}
        raw = r.json()
        d   = raw.get("data") or raw
        if isinstance(d, list):
            m = [x for x in d if str(x.get("symbol","")).upper() == ticker.upper()]
            d = m[0] if m else {}
        if not isinstance(d, dict):
            return {}
        def g(*ks):
            for k in ks:
                v = d.get(k)
                if v not in (None,"",0): return v
            return None
        result = {}
        room = _f(g("currentRoom","foreignCurrentRoom","room","fRoom"), lo=0, hi=100)
        fbuy = _i(g("foreignBuyVolume","foreignBuyQtty","fb"), lo=0)
        fsell= _i(g("foreignSellVolume","foreignSellQtty","fs"), lo=0)
        ref  = _f(g("referencePrice","refPrice","r"))
        ceil = _f(g("ceilPrice","ceiling","ce"))
        fl   = _f(g("floorPrice","floor","f"))
        sh   = _i(g("listedShare","shareIssued","listVol"), lo=1000)
        if room is not None: result["room_si"] = room
        if fbuy is not None: result["fbuy_si"] = fbuy
        if fsell is not None:result["fsell_si"]= fsell
        if ref:  result["ref_si"]  = ref
        if ceil: result["ceil_si"] = ceil
        if fl:   result["fl_si"]   = fl
        if sh:   result["sh_si"]   = sh
        return result
    except:
        return {}


# ══════════════════════════════════════════════════════════════════════════════
#  HÀM CHÍNH
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def get_stock_data(ticker: str, region: str = "VN") -> dict:
    ticker = ticker.upper().strip()
    suffix = REGION_SUFFIX.get(region, "")
    stock  = None
    price  = open_p = high = low = volume = prev = None

    # ── BƯỚC 1: yfinance history (LUÔN CÓ) ───────────────────────────────────
    for yf_str in [f"{ticker}{suffix}", ticker]:
        for attempt in range(3):
            try:
                s  = yf.Ticker(yf_str)
                df = s.history(period="5d", timeout=12)
                if df is not None and not df.empty:
                    last  = df.iloc[-1]
                    prev2 = df.iloc[-2] if len(df) >= 2 else last
                    price  = round(float(last["Close"]), 2)
                    open_p = round(float(last["Open"]),  2) if last["Open"]  > 0 else None
                    high   = round(float(last["High"]),  2) if last["High"]  > 0 else None
                    low    = round(float(last["Low"]),   2) if last["Low"]   > 0 else None
                    volume = int(last["Volume"])
                    prev   = round(float(prev2["Close"]), 2)
                    stock  = s
                    break
            except Exception as e:
                err = str(e).lower()
                if ("ratelimit" in err or "429" in err) and attempt < 2:
                    time.sleep((attempt+1)*3)
                elif "timeout" in err and attempt < 2:
                    time.sleep(2)
        if price: break

    if not price:
        return {"error": f"Không tìm thấy mã **'{ticker}'**."}

    # ── BƯỚC 2: yfinance .info + fast_info ───────────────────────────────────
    info = {}
    try: info = stock.info or {}
    except: pass

    # Shares — nhiều nguồn
    shares = _pick(
        _i(getattr(getattr(stock, "fast_info", None), "shares", None), lo=1000),
        _i(info.get("sharesOutstanding"), lo=1000),
    )

    # PE, PB từ .info (thường có cho VN)
    pe_info = _pick(_f(info.get("trailingPE")), _f(info.get("forwardPE")))
    pb_info = _f(info.get("priceToBook"))

    # EPS, BVPS, ROE, ROA từ .info (thường KHÔNG có cho VN → tính bên dưới)
    eps_info  = _f(info.get("trailingEps"), lo=-1e9, hi=1e9)
    bvps_info = _f(info.get("bookValue"))
    roe_r = info.get("returnOnEquity")
    roa_r = info.get("returnOnAssets")
    roe_info  = round(float(roe_r)*100, 2) if roe_r else None
    roa_info  = round(float(roa_r)*100, 2) if roa_r else None

    industry = info.get("industry") or info.get("sector") or "N/A"
    market   = (info.get("exchange") or "HOSE").replace("HSX","HOSE").replace("VNM","HOSE")
    mc_info  = _f(info.get("marketCap"), lo=0)

    # ── BƯỚC 3: Tính từ financial statements ─────────────────────────────────
    ni = equity = total_assets = None
    eps_stmt = bvps_stmt = roe_stmt = roa_stmt = None
    pe_calc  = pb_calc  = None

    try:
        inc = stock.income_stmt
        if inc is not None and not inc.empty:
            # Net Income
            ni = _get_row(inc,
                "Net Income",
                "Net Income Common Stockholders",
                "Net Income From Continuing Operations",
                "Net Income Including Noncontrolling Interests",
            )
            # EPS trực tiếp từ income_stmt (nếu có)
            eps_direct = _get_row(inc, "Basic EPS", "Diluted EPS", "EPS")
            if eps_direct:
                # Đơn vị: VNĐ nếu > 100, nghìn đồng nếu nhỏ hơn
                if abs(eps_direct) > 100:
                    eps_stmt = round(eps_direct / 1000, 2)
                else:
                    eps_stmt = round(eps_direct, 2)

            # Tính EPS từ NI/Shares nếu chưa có
            if not eps_stmt and ni and shares and shares > 0 and ni > 0:
                eps_vnd   = ni / shares          # VNĐ/CP
                eps_stmt  = round(eps_vnd / 1000, 2)   # → nghìn đồng
                pe_calc   = _f(price / eps_vnd, lo=0.1, hi=500)
    except:
        pass

    try:
        bs = stock.balance_sheet
        if bs is not None and not bs.empty:
            equity = _get_row(bs,
                "Stockholders Equity",
                "Total Stockholders Equity",
                "Common Stock Equity",
                "Total Equity Gross Minority Interest",
            )
            total_assets = _get_row(bs, "Total Assets")

            if equity and shares and shares > 0 and equity > 0:
                bvps_vnd  = equity / shares       # VNĐ/CP
                bvps_stmt = round(bvps_vnd / 1000, 2)  # → nghìn đồng
                pb_calc   = _f(price / bvps_vnd, lo=0.05, hi=100)

                if ni and ni > 0:
                    roe_stmt = round(ni / equity * 100, 2)

            if total_assets and ni and ni > 0 and total_assets > 0:
                roa_stmt = round(ni / total_assets * 100, 2)
    except:
        pass

    # ── BƯỚC 4: Thử API VN (không phụ thuộc, bonus nếu có) ───────────────────
    ext = {}
    for fn in [lambda: _try_vndirect(ticker),
               lambda: _try_tcbs(ticker),
               lambda: _try_ssi_room(ticker)]:
        try:
            ext.update({k: v for k, v in fn().items() if v not in (None, "", 0)})
        except:
            pass

    # ── BƯỚC 5: Waterfall — ưu tiên API VN → .info → tính từ financials ──────
    def pick_field(*vals):
        return _pick(*vals) or "N/A"

    pe   = pick_field(ext.get("pe_vd"),   ext.get("pe_tc"),   pe_info,  pe_calc)
    pb   = pick_field(ext.get("pb_vd"),   ext.get("pb_tc"),   pb_info,  pb_calc)
    eps  = pick_field(ext.get("eps_vd"),  ext.get("eps_tc"),  eps_info, eps_stmt)
    bvps = pick_field(ext.get("bvps_vd"), ext.get("bvps_tc"), bvps_info,bvps_stmt)
    roe  = pick_field(ext.get("roe_vd"),  ext.get("roe_tc"),  roe_info, roe_stmt)
    roa  = pick_field(ext.get("roa_vd"),  ext.get("roa_tc"),  roa_info, roa_stmt)
    avg_pe   = _pick(ext.get("ape_vd"), ext.get("ape_tc")) or 0
    avg_pb   = _pick(ext.get("apb_vd"), ext.get("apb_tc")) or 0
    industry = _pick(ext.get("ind_vd"), ext.get("ind_tc"), industry) or "N/A"
    market   = _pick(ext.get("mkt_vd"), ext.get("mkt_tc"), ext.get("mkt_si"), market) or "HOSE"

    # KLCP
    shares_best = _pick(
        _i(getattr(getattr(stock,"fast_info",None),"shares",None), lo=1000),
        ext.get("sh_vd"), ext.get("sh_tc"), ext.get("sh_si"),
        shares
    )
    if shares_best: shares_best = int(shares_best)

    # Vốn hóa = KLCP × Giá (ưu tiên tuyệt đối)
    if shares_best and price:
        mc = round(shares_best * price / 1e9, 2)
    else:
        mc_raw = _pick(ext.get("mc_vd"), ext.get("mc_tc"), mc_info)
        if mc_raw:
            mc_raw = float(mc_raw)
            mc = (round(mc_raw/1e9,2) if mc_raw > 1e12 else
                  round(mc_raw/1e6,2) if mc_raw > 1e9  else
                  round(mc_raw/1e3,2) if mc_raw > 1e3  else
                  round(mc_raw, 2))
        else:
            mc = "N/A"

    # Giá trần/sàn
    ref   = _pick(ext.get("ref_si"), prev)
    ceil  = _pick(ext.get("ceil_si"), round(float(ref)*1.07, 0) if ref else None)
    floor = _pick(ext.get("fl_si"),  round(float(ref)*0.93, 0) if ref else None)

    # Room NN, NN Mua/Bán
    room  = _pick(ext.get("room_si"), ext.get("room_vd")) or "N/A"
    fbuy  = _pick(ext.get("fbuy_si"))  or "N/A"
    fsell = _pick(ext.get("fsell_si")) or "N/A"

    # % thay đổi
    try:
        price_change     = round(price - float(ref), 2) if ref else 0
        price_change_pct = round((price - float(ref)) / float(ref) * 100, 2) if ref else 0
    except:
        price_change = price_change_pct = 0

    # Format numbers đẹp
    def fmt2(v, dec=2):
        if v in (None, "N/A", ""): return "N/A"
        try: return round(float(v), dec)
        except: return v

    return {
        "ticker":       ticker,
        "price":        price,
        "open_price":   open_p  or "N/A",
        "high_price":   high    or "N/A",
        "low_price":    low     or "N/A",
        "volume":       volume  or 0,
        "ref_price":    ref     or "N/A",
        "ceil_price":   ceil    or "N/A",
        "floor_price":  floor   or "N/A",
        "price_change": price_change,
        "price_change_pct": price_change_pct,
        "market":       market,
        "industry":     industry,
        # Chỉ số định giá
        "pe":    fmt2(pe),
        "pb":    fmt2(pb),
        "eps":   fmt2(eps),
        "bvps":  fmt2(bvps),
        "roe":   fmt2(roe),
        "roa":   fmt2(roa),
        "avg_pe": avg_pe,
        "avg_pb": avg_pb,
        # Quy mô
        "listed_shares": shares_best or "N/A",
        "circulating":   shares_best or "N/A",
        "market_cap":    mc,
        # NN
        "foreign_room":  room,
        "foreign_buy":   fbuy,
        "foreign_sell":  fsell,
        # Debug
        "_calc_source": {
            "eps":  "financials" if eps_stmt and eps == fmt2(eps_stmt) else "api/info",
            "bvps": "financials" if bvps_stmt and bvps == fmt2(bvps_stmt) else "api/info",
            "roe":  "financials" if roe_stmt and roe == fmt2(roe_stmt) else "api/info",
            "roa":  "financials" if roa_stmt and roa == fmt2(roa_stmt) else "api/info",
            "ni":   f"{ni:,.0f}" if ni else "N/A",
            "equity": f"{equity:,.0f}" if equity else "N/A",
        }
    }
