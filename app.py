"""
La Bàn Chứng Khoán AI Pro — app.py v4.1
Import đúng subfolder: core/ và components/
"""
import streamlit as st
import sys, os, json

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in [_ROOT, os.getcwd()]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from core.data_fetcher      import get_stock_data
    from components.chart_ui    import render_chart
    from components.chatbot_ui  import render_chat_interface
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
[data-testid="stMetricValue"]{font-size:1.05rem!important;font-weight:700}
[data-testid="stMetricDelta"]{font-size:.72rem!important}
[data-testid="stMetricLabel"]{font-size:.68rem!important}
div[data-testid="metric-container"]{background:#1a1a1a;border-radius:8px;padding:8px 10px!important;border:1px solid #2e2e2e}
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
    tl = text.lower().strip()
    ws = tl.split()
    for kw in _GKW:
        if kw in tl: return "general"
    if len(ws)==1 and len(ws[0])<=6 and ws[0].isalnum(): return "ticker"
    if len(ws)==2 and all(len(w)<=6 and w.isalnum() for w in ws): return "ticker"
    return "general"

for k,v in [("language","vi"),("selected_model","gemini-2.0-flash"),("market_region","VN")]:
    if k not in st.session_state: st.session_state[k] = v

loc = load_locales(st.session_state["language"])

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
    st.caption("📦 v4.1 | Subfolder + Search Grounding")

st.title(loc.get("title","📈 La Bàn Chứng Khoán AI Pro"))
st.caption("🔍 Phân tích kết hợp dữ liệu thực tế + Google Search thông tin mới nhất")

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
    vi_in = speech_to_text(language='vi-VN', start_prompt="Bấm để nói", stop_prompt="⏹️ Dừng", key='mic')

user_input  = (fi if fi else vi_in) or ""
triggered   = sb or bool(vi_in)
lang_prompt = "Tiếng Việt" if st.session_state["language"]=="vi" else "English"

if triggered and user_input:
    if classify(user_input) == "ticker":
        ticker = user_input.upper().split()[0]
        region = st.session_state["market_region"]

        with st.spinner(f"📡 Đang tải dữ liệu {ticker}..."):
            data = get_stock_data(ticker, region=region)

        if "error" in data:
            st.error(f"❌ {data['error']}")
        else:
            st.subheader(f"📊 {ticker} — {data.get('industry','N/A')}")
            m1,m2,m3,m4,m5,m6,m7 = st.columns(7)
            price = data.get("price",0)
            unit  = " VNĐ" if region=="VN" else " USD"
            m1.metric("💰 Giá",   f"{price:,.0f}{unit}")
            m2.metric("📊 KL GD", f"{data.get('volume',0):,}")
            m3.metric("🏛️ Sàn",   data.get("market",region))

            pe=data.get("pe","N/A"); avg_pe=data.get("avg_pe",0) or 0
            pb=data.get("pb","N/A"); avg_pb=data.get("avg_pb",0) or 0
            try: pe_d = round(float(pe)-float(avg_pe),2) if pe!="N/A" and avg_pe else None
            except: pe_d=None
            try: pb_d = round(float(pb)-float(avg_pb),2) if pb!="N/A" and avg_pb else None
            except: pb_d=None

            m4.metric("📈 P/E",       str(pe))
            m5.metric("📈 P/E Ngành", str(avg_pe) if avg_pe else "N/A",
                      delta=pe_d, delta_color="inverse" if pe_d else "off")
            m6.metric("📉 P/B",       str(pb))
            m7.metric("📉 P/B Ngành", str(avg_pb) if avg_pb else "N/A",
                      delta=pb_d, delta_color="inverse" if pb_d else "off")

            if pe=="N/A" and pb=="N/A" and "_errors" in data:
                with st.expander("ℹ️ P/E, P/B chưa có — AI vẫn phân tích bằng Google Search"):
                    st.code("\n".join(f"{k}: {v}" for k,v in data["_errors"].items()))

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
    <p>Nhập <b>mã cổ phiếu</b> (FPT, VND, MBB...) hoặc <b>câu hỏi thị trường</b></p>
    <p style='color:#aaa'>AI kết hợp dữ liệu thực tế + Google Search — thông tin luôn mới nhất</p>
    <hr style='border-color:#333;margin:1.5rem 0'>
    <p style='font-size:.85rem'>💡 Dùng <b>⚡ Flash</b> để có quota cao nhất — 15 req/phút miễn phí</p>
    </div>""", unsafe_allow_html=True)
