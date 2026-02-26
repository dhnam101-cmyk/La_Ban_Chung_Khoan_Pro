"""
La Bàn Chứng Khoán AI Pro — app.py v5.0
Hiển thị đầy đủ: Giá tham chiếu/trần/sàn, EPS, P/E, P/B, BVPS,
Vốn hóa, KLCP, Room NN, NN Mua/Bán
"""
import streamlit as st
import sys, os, json

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in [_ROOT, os.getcwd()]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from core.data_fetcher     import get_stock_data
    from components.chart_ui   import render_chart
    from components.chatbot_ui import render_chat_interface
except ModuleNotFoundError as e:
    st.error(f"❌ **Import lỗi:** `{e}`")
    st.stop()

try:
    from streamlit_mic_recorder import speech_to_text
    VOICE_ENABLED = True
except ImportError:
    VOICE_ENABLED = False

st.set_page_config(page_title="La Bàn Chứng Khoán Pro", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
/* Metrics */
[data-testid="stMetricValue"]{font-size:.95rem!important;font-weight:700}
[data-testid="stMetricDelta"]{font-size:.68rem!important}
[data-testid="stMetricLabel"]{font-size:.65rem!important;color:#aaa!important}
div[data-testid="metric-container"]{
    background:#161616;border-radius:6px;
    padding:6px 8px!important;border:1px solid #2a2a2a}

/* Bảng giá màu */
.price-up   {color:#26a69a!important;font-weight:700}
.price-down {color:#ef5350!important;font-weight:700}
.price-ref  {color:#F4A261!important;font-weight:700}

/* Section header */
.section-header{
    background:#1e1e1e;border-left:3px solid #F4A261;
    padding:4px 10px;border-radius:4px;margin:8px 0 4px 0;
    font-size:.8rem;font-weight:600;color:#F4A261;text-transform:uppercase}

.chatbot-section{margin-top:1.5rem;border-top:2px solid #F4A261;padding-top:1rem}
footer{visibility:hidden}
</style>""", unsafe_allow_html=True)


@st.cache_data
def load_locales(lang_code):
    path = os.path.join(_ROOT, "locales", f"{lang_code}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

_GKW = ["thị trường","market","nhận định","lạm phát","lãi suất","kinh tế","vĩ mô",
        "hôm nay","tuần này","tháng này","xu hướng","nên mua","nên bán","cổ phiếu nào",
        "gợi ý","recommend","inflation","interest rate","gdp","fed","ngân hàng",
        "strategy","chiến lược","danh mục","portfolio","rủi ro","risk","cơ hội",
        "tổng quan","tổng kết","diễn biến","có gì","thế nào","ra sao","như thế nào",
        "hàng hóa","dầu","vàng","đặc biệt","sự kiện"]

def classify(text):
    if not text: return "general"
    tl = text.lower().strip(); ws = tl.split()
    for kw in _GKW:
        if kw in tl: return "general"
    if len(ws)==1 and len(ws[0])<=6 and ws[0].isalnum(): return "ticker"
    if len(ws)==2 and all(len(w)<=6 and w.isalnum() for w in ws): return "ticker"
    return "general"

def fmt_price(v, region="VN"):
    """Format giá với đơn vị."""
    if v is None or v == "N/A": return "N/A"
    try:
        f = float(v)
        return f"{f:,.2f}" if region != "VN" else f"{f:,.0f}"
    except: return str(v)

def fmt_vol(v):
    if v is None or v == "N/A" or v == 0: return "N/A"
    try:
        n = int(v)
        if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
        if n >= 1_000_000:     return f"{n/1_000_000:.2f}M"
        if n >= 1_000:         return f"{n/1_000:.1f}K"
        return str(n)
    except: return str(v)

def color_price(val, ref, region="VN"):
    """Trả về (text, delta_color) dựa trên so sánh với giá tham chiếu."""
    try:
        v, r = float(val), float(ref)
        if v > r:   return fmt_price(val, region), "normal"
        elif v < r: return fmt_price(val, region), "inverse"
        else:       return fmt_price(val, region), "off"
    except: return fmt_price(val, region), "off"

# Session defaults
for k,v in [("language","vi"),("selected_model","gemini-2.0-flash"),("market_region","VN")]:
    if k not in st.session_state: st.session_state[k] = v

loc = load_locales(st.session_state["language"])

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title(loc.get("sidebar_title","⚙️ Cài đặt"))
    ld = st.selectbox(loc.get("lang_select","🌐 Ngôn ngữ:"),["Tiếng Việt (vi)","English (en)"])
    nl = "vi" if "vi" in ld else "en"
    if nl != st.session_state["language"]:
        st.session_state["language"] = nl; st.rerun()

    st.divider()
    st.subheader("🌍 Khu vực")
    mr = st.radio("Thị trường:",["🇻🇳 Việt Nam (VN)","🇺🇸 Mỹ (US)","🌐 Quốc tế"])
    st.session_state["market_region"] = "VN" if "Việt Nam" in mr else ("US" if "Mỹ" in mr else "INTL")
    if st.session_state["market_region"]=="VN":
        st.session_state["market_filter"] = st.radio("Sàn:",["Tất cả","HOSE","HNX","UPCOM"],horizontal=True)

    st.divider()
    st.subheader(loc.get("ai_config","🤖 Cấu hình AI"))
    MODEL_MAP = {
        "⚡ Gemini 2.0 Flash (Khuyên dùng)": "gemini-2.0-flash",
        "✨ Gemini 1.5 Flash":               "gemini-1.5-flash",
        "🧠 Gemini 2.0 Pro":                 "gemini-2.0-pro-exp-02-05",
    }
    cur = st.session_state["selected_model"]
    cur_lbl = next((k for k,v in MODEL_MAP.items() if v==cur),"⚡ Gemini 2.0 Flash (Khuyên dùng)")
    sel = st.selectbox(loc.get("model_select","Model:"),list(MODEL_MAP.keys()),
                       index=list(MODEL_MAP.keys()).index(cur_lbl))
    st.session_state["selected_model"] = MODEL_MAP[sel]
    if "Pro" in sel: st.warning("⚠️ Pro: ~2 req/phút. Dễ Rate Limit.")
    st.divider()
    st.markdown("**💡 Tránh Rate Limit:**\n- Dùng ⚡ Flash\n- Đợi 1–2 phút giữa các lần\n- 1,500 req/ngày miễn phí")
    st.caption("📦 v5.0 | Full Data + Search Grounding")

# ── Main ──────────────────────────────────────────────────────────────────────
st.title(loc.get("title","📈 La Bàn Chứng Khoán AI Pro"))

with st.form("sf", clear_on_submit=False):
    c1,c2 = st.columns([0.82,0.18])
    with c1:
        fi = st.text_input("s", label_visibility="collapsed",
                           placeholder="🔍 Nhập mã cổ phiếu (FPT, MBB...) hoặc câu hỏi thị trường").strip()
    with c2:
        sb = st.form_submit_button(loc.get("btn_analyze","🔍 Phân tích"), use_container_width=True)

vi_in = None
if VOICE_ENABLED:
    st.caption("🎙️ Tìm bằng giọng nói:")
    vi_in = speech_to_text(language='vi-VN', start_prompt="Bấm để nói", stop_prompt="⏹️", key='mic')

user_input  = (fi if fi else vi_in) or ""
triggered   = sb or bool(vi_in)
lang_prompt = "Tiếng Việt" if st.session_state["language"]=="vi" else "English"

def _render_stock_data(data: dict, region: str):
    """Hiển thị đầy đủ dữ liệu cổ phiếu theo layout như trang HOSE/CafeF."""

    ticker   = data.get("ticker","")
    price    = data.get("price", 0)
    ref      = data.get("ref_price")   or data.get("prev_close") or price
    ceil_p   = data.get("ceil_price",  "N/A")
    floor_p  = data.get("floor_price", "N/A")
    open_p   = data.get("open_price",  "N/A")
    high_p   = data.get("high_price",  "N/A")
    low_p    = data.get("low_price",   "N/A")
    chg      = data.get("price_change", 0)
    chg_pct  = data.get("price_change_pct", 0)

    pe    = data.get("pe", "N/A")
    pb    = data.get("pb", "N/A")
    eps   = data.get("eps", "N/A")
    bvps  = data.get("bvps", "N/A")
    roe   = data.get("roe", "N/A")
    roa   = data.get("roa", "N/A")
    avg_pe = data.get("avg_pe", 0) or "N/A"
    avg_pb = data.get("avg_pb", 0) or "N/A"
    ind   = data.get("industry", "N/A")
    mkt   = data.get("market", region)
    mc    = data.get("market_cap", "N/A")      # Tỷ đồng
    vol   = data.get("volume", 0)
    ls    = data.get("listed_shares", "N/A")
    circ  = data.get("circulating", "N/A")
    room  = data.get("foreign_room", "N/A")
    fbuy  = data.get("foreign_buy", "N/A")
    fsell = data.get("foreign_sell", "N/A")

    unit = "VNĐ" if region == "VN" else "USD"

    # Header
    chg_color = "🟢" if chg > 0 else "🔴" if chg < 0 else "🟡"
    chg_sign  = "+" if chg > 0 else ""
    st.subheader(
        f"📊 **{ticker}** — {ind} | Sàn: {mkt}  "
        f"{chg_color} {fmt_price(price, region)} {unit}  "
        f"({chg_sign}{chg:,.0f} | {chg_sign}{chg_pct:.2f}%)"
    )

    # ── BẢNG 1: Giá ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📈 Thông tin Giá</div>', unsafe_allow_html=True)
    g1, g2, g3, g4, g5, g6 = st.columns(6)
    g1.metric("Giá tham chiếu", fmt_price(ref, region),
              help="Giá đóng cửa phiên trước")
    g2.metric("Giá trần",  fmt_price(ceil_p, region),
              delta=f"+{round((float(ceil_p)-float(ref))/float(ref)*100,1)}%" if ceil_p!="N/A" and ref else None,
              delta_color="normal")
    g3.metric("Giá sàn",   fmt_price(floor_p, region),
              delta=f"-{round((float(ref)-float(floor_p))/float(ref)*100,1)}%" if floor_p!="N/A" and ref else None,
              delta_color="inverse")
    g4.metric("Giá mở cửa", fmt_price(open_p, region))
    g5.metric("Cao nhất",   fmt_price(high_p, region))
    g6.metric("Thấp nhất",  fmt_price(low_p, region))

    # ── BẢNG 2: Định giá (Fundamental) ───────────────────────────────────────
    st.markdown('<div class="section-header">💰 Chỉ số Định giá</div>', unsafe_allow_html=True)
    f1, f2, f3, f4, f5, f6 = st.columns(6)

    # EPS format (nghìn đồng)
    eps_fmt = f"{float(eps):.2f}" if eps not in ("N/A", None) else "N/A"
    bvps_fmt = f"{float(bvps):.2f}" if bvps not in ("N/A", None) else "N/A"
    roe_fmt  = f"{float(roe):.1f}%" if roe not in ("N/A", None) else "N/A"
    roa_fmt  = f"{float(roa):.1f}%" if roa not in ("N/A", None) else "N/A"

    # PE delta so ngành
    try:
        pe_d = round(float(pe) - float(avg_pe), 2) if pe!="N/A" and avg_pe!="N/A" and float(avg_pe)>0 else None
    except: pe_d = None
    try:
        pb_d = round(float(pb) - float(avg_pb), 2) if pb!="N/A" and avg_pb!="N/A" and float(avg_pb)>0 else None
    except: pb_d = None

    f1.metric("EPS cơ bản *",    f"{eps_fmt} nghìn đ", help="Lợi nhuận trên mỗi cổ phiếu")
    f2.metric("P/E",             str(pe),
              delta=f"vs ngành: {pe_d:+.2f}" if pe_d else None,
              delta_color="inverse" if pe_d and pe_d > 0 else "normal" if pe_d else "off",
              help=f"P/E TB ngành: {avg_pe}")
    f3.metric("Giá trị sổ sách/CP", f"{bvps_fmt} nghìn đ", help="Book Value per Share")
    f4.metric("P/B",             str(pb),
              delta=f"vs ngành: {pb_d:+.2f}" if pb_d else None,
              delta_color="inverse" if pb_d and pb_d > 0 else "normal" if pb_d else "off",
              help=f"P/B TB ngành: {avg_pb}")
    f5.metric("ROE",             roe_fmt, help="Return on Equity")
    f6.metric("ROA",             roa_fmt, help="Return on Assets")

    # ── BẢNG 3: Quy mô & Giao dịch ───────────────────────────────────────────
    st.markdown('<div class="section-header">🏢 Quy mô & Giao dịch</div>', unsafe_allow_html=True)
    q1, q2, q3, q4 = st.columns(4)

    mc_fmt = f"{float(mc):,.2f} tỷ đ" if mc not in ("N/A", None) else "N/A"
    q1.metric("Vốn hóa thị trường", mc_fmt)
    q2.metric("KLGD phiên",          fmt_vol(vol),  help="Khối lượng giao dịch phiên hiện tại")
    q3.metric("KLCP niêm yết",       fmt_vol(ls),   help="Số cổ phiếu đang niêm yết")
    q4.metric("KLCP lưu hành",       fmt_vol(circ or ls))

    # ── BẢNG 4: Nhà đầu tư nước ngoài ────────────────────────────────────────
    st.markdown('<div class="section-header">🌐 Nhà đầu tư Nước ngoài (NN)</div>', unsafe_allow_html=True)
    n1, n2, n3 = st.columns(3)

    # Room NN format
    if room not in ("N/A", None):
        try:
            room_fmt = f"{float(room):.2f}%"
        except:
            room_fmt = str(room)
    else:
        room_fmt = "N/A"

    n1.metric("Room NN còn lại",  room_fmt,     help="Tỷ lệ sở hữu nước ngoài còn được phép")
    n2.metric("NN Mua (KL)",      fmt_vol(fbuy), help="Khối lượng nước ngoài mua phiên này")
    n3.metric("NN Bán (KL)",      fmt_vol(fsell), help="Khối lượng nước ngoài bán phiên này")

    # Debug nếu thiếu dữ liệu
    missing = [k for k in ["pe","pb","eps"] if data.get(k) in ("N/A", None)]
    if missing:
        with st.expander(f"ℹ️ Một số chỉ số chưa có: {', '.join(missing)}"):
            errs = {**data.get("_fund_errors",{}), **{"ssi": data.get("_ssi_error","")}}
            errs = {k:v for k,v in errs.items() if v}
            if errs:
                st.code("\n".join(f"{k}: {v}" for k,v in errs.items()), language="text")
            st.caption("AI vẫn phân tích bằng Google Search với dữ liệu có sẵn.")


# ── Routing ───────────────────────────────────────────────────────────────────
if triggered and user_input:
    if classify(user_input) == "ticker":
        ticker = user_input.upper().split()[0]
        region = st.session_state["market_region"]

        with st.spinner(f"📡 Đang tải đầy đủ dữ liệu {ticker}..."):
            data = get_stock_data(ticker, region=region)

        if "error" in data:
            st.error(f"❌ {data['error']}")
        else:
            _render_stock_data(data, region)

            st.divider()
            st.subheader("📊 Biểu đồ Kỹ thuật")
            render_chart(ticker, exchange=data.get("market","HOSE"), region=region)

            st.markdown('<div class="chatbot-section">', unsafe_allow_html=True)
            st.subheader("🤖 AI Phân tích (Dữ liệu thực + Google Search)")
            render_chat_interface(ticker=ticker, lang=lang_prompt,
                                  model=st.session_state["selected_model"],
                                  mode="ticker", stock_data=data)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info(f"💡 **Phân tích thị trường** — *\"{user_input}\"*")
        st.divider()
        render_chat_interface(ticker="Thị trường", lang=lang_prompt,
                              model=st.session_state["selected_model"],
                              mode="general", initial_query=user_input)
elif not user_input:
    st.markdown("""<div style='text-align:center;padding:3rem 1rem;color:#888'>
    <h3 style='color:#F4A261'>📈 La Bàn Chứng Khoán AI Pro</h3>
    <p>Nhập <b>mã cổ phiếu</b> (FPT, VND, MBB, AAPL...) để xem đầy đủ:</p>
    <p style='color:#aaa'>Giá tham chiếu/trần/sàn · EPS · P/E · P/B · ROE · Vốn hóa · Room NN</p>
    <hr style='border-color:#333;margin:1.5rem 0'>
    <p style='font-size:.85rem'>💡 Dùng <b>⚡ Flash</b> để có quota cao nhất — 15 req/phút miễn phí</p>
    </div>""", unsafe_allow_html=True)
