"""
================================================================================
  components/chart_ui.py — Biểu đồ Candlestick full-size với Plotly
  Features:
  ✅ Chiếm tối đa diện tích màn hình (height=750)
  ✅ Candlestick + SMA 20/50 + Volume sub-chart
  ✅ Bộ chọn khung thời gian (1mo → 5y)
  ✅ Xử lý YFRateLimitError, retry 3 lần
  ✅ Hỗ trợ đa khu vực VN / US / INTL
================================================================================
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time


def _fetch_chart_data(ticker: str, region: str = "VN", period: str = "1y") -> pd.DataFrame:
    """Tải OHLCV với retry chống rate limit."""
    suffix_map = {"VN": ".VN", "US": "", "INTL": ""}
    yf_str     = f"{ticker}{suffix_map.get(region, '')}"

    for attempt in range(3):
        try:
            df = yf.download(yf_str, period=period, progress=False, timeout=12)
            if not df.empty:
                return df
            if suffix_map.get(region):              # Thử không suffix
                df = yf.download(ticker, period=period, progress=False, timeout=12)
                if not df.empty:
                    return df
            return pd.DataFrame()
        except Exception as e:
            err = str(e).lower()
            if ("ratelimit" in err or "429" in err or "too many" in err) and attempt < 2:
                time.sleep((attempt + 1) * 4)
            else:
                return pd.DataFrame()
    return pd.DataFrame()


def render_chart(ticker: str, exchange: str = "HOSE", region: str = "VN"):
    """
    Vẽ biểu đồ candlestick full-width.
    Gọi hàm này TRƯỚC render_chat_interface để chatbot nằm bên dưới.
    """

    # Bộ chọn khung thời gian
    _, tf_col = st.columns([0.65, 0.35])
    with tf_col:
        period_map = {
            "1 tháng": "1mo", "3 tháng": "3mo", "6 tháng": "6mo",
            "1 năm": "1y",    "2 năm":   "2y",  "5 năm":   "5y",
        }
        period_label = st.selectbox(
            "Khung thời gian:", list(period_map.keys()),
            index=3, key=f"period_{ticker}"
        )
    period = period_map[period_label]

    with st.spinner(f"Đang tải biểu đồ {ticker}..."):
        df = _fetch_chart_data(ticker, region=region, period=period)

    if df is None or df.empty:
        st.warning(
            f"⚠️ Không có dữ liệu biểu đồ cho **{ticker}**. "
            "Yahoo Finance có thể đang giới hạn — thử lại sau 30 giây."
        )
        return

    # Chuẩn hoá MultiIndex columns nếu có
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    df.columns = [c.capitalize() for c in df.columns]

    # Tính SMA
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()

    # Layout 2 hàng: chart 78% + volume 22%
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=[0.78, 0.22]
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'],
        low=df['Low'],   close=df['Close'],
        name=ticker,
        increasing_line_color='#26a69a', decreasing_line_color='#ef5350',
        increasing_fillcolor='#26a69a',  decreasing_fillcolor='#ef5350',
    ), row=1, col=1)

    # SMA lines
    fig.add_trace(go.Scatter(
        x=df.index, y=df['SMA20'], name='SMA 20',
        mode='lines', line=dict(color='#F4A261', width=1.3)
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['SMA50'], name='SMA 50',
        mode='lines', line=dict(color='#4FC3F7', width=1.3)
    ), row=1, col=1)

    # Volume bars (màu theo nến tăng/giảm)
    vol_colors = [
        '#26a69a' if row['Close'] >= row['Open'] else '#ef5350'
        for _, row in df.iterrows()
    ]
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'], name='KL',
        marker_color=vol_colors, marker_line_width=0, opacity=0.7
    ), row=2, col=1)

    # Layout
    fig.update_layout(
        height=750,
        margin=dict(l=0, r=0, t=20, b=0),
        template="plotly_dark",
        paper_bgcolor="#121212",
        plot_bgcolor="#121212",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="right", x=1, bgcolor="rgba(0,0,0,0)", font=dict(size=11)
        ),
        hovermode='x unified',
        xaxis_rangeslider_visible=False,
    )
    grid = dict(showgrid=True, gridcolor='#2a2a2a', gridwidth=1)
    fig.update_xaxes(**grid)
    fig.update_yaxes(**grid, side='right')
    fig.update_yaxes(title_text="Giá", row=1, col=1)
    fig.update_yaxes(title_text="KL",  row=2, col=1)

    st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'scrollZoom': True
    })
