"""
================================================================================
  chart_ui.py — Render biểu đồ nến (Candlestick) với Plotly
  
  Improvements:
  ✅ Biểu đồ chiếm tối đa diện tích màn hình (height=750)
  ✅ Thêm đường SMA 20 & 50 ngày
  ✅ Thêm sub-chart khối lượng (Volume)
  ✅ Xử lý lỗi YFRateLimitError riêng
  ✅ Hỗ trợ đa khu vực thị trường
================================================================================
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time


def _fetch_chart_data(ticker: str, region: str = "VN", period: str = "1y") -> pd.DataFrame:
    """
    Tải dữ liệu OHLCV cho biểu đồ.
    Có retry logic chống YFRateLimitError.
    """
    suffix_map = {"VN": ".VN", "US": "", "INTL": ""}
    suffix     = suffix_map.get(region, "")
    yf_str     = f"{ticker}{suffix}"
    
    for attempt in range(3):
        try:
            df = yf.download(yf_str, period=period, progress=False, timeout=12)
            if not df.empty:
                return df
            # Thử không suffix
            if suffix:
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
    Vẽ biểu đồ candlestick full-width với sub-chart khối lượng.
    Được tối ưu để chiếm tối đa không gian hiển thị.
    """
    
    # ── Bộ chọn khung thời gian ──────────────────────────────────────────────
    tf_col1, tf_col2 = st.columns([0.7, 0.3])
    with tf_col2:
        period_map = {
            "1 tháng": "1mo",
            "3 tháng": "3mo",
            "6 tháng": "6mo",
            "1 năm":   "1y",
            "2 năm":   "2y",
            "5 năm":   "5y"
        }
        period_label = st.selectbox(
            "Khung thời gian:",
            list(period_map.keys()),
            index=3,  # Mặc định "1 năm"
            key=f"period_{ticker}"
        )
    period = period_map[period_label]
    
    # ── Tải dữ liệu ──────────────────────────────────────────────────────────
    with st.spinner(f"Đang tải biểu đồ {ticker}..."):
        df = _fetch_chart_data(ticker, region=region, period=period)
    
    if df is None or df.empty:
        st.warning(
            f"⚠️ Không có dữ liệu biểu đồ cho **{ticker}**. "
            "Có thể do giới hạn API Yahoo Finance — thử lại sau 30 giây."
        )
        return
    
    # ── Chuẩn hoá columns (yfinance đôi khi trả MultiIndex) ──────────────────
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    df = df.rename(columns=str.capitalize)  # Open, High, Low, Close, Volume
    
    # ── Tính SMA ─────────────────────────────────────────────────────────────
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()
    
    # ── Tạo layout 2 hàng: Chart (80%) + Volume (20%) ────────────────────────
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.78, 0.22]
    )
    
    # ── Nến (Candlestick) ─────────────────────────────────────────────────────
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name=ticker,
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
            increasing_fillcolor='#26a69a',
            decreasing_fillcolor='#ef5350',
        ),
        row=1, col=1
    )
    
    # ── Đường SMA ─────────────────────────────────────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df['SMA20'],
            name='SMA 20', mode='lines',
            line=dict(color='#F4A261', width=1.2, dash='solid')
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df['SMA50'],
            name='SMA 50', mode='lines',
            line=dict(color='#4FC3F7', width=1.2, dash='solid')
        ),
        row=1, col=1
    )
    
    # ── Biểu đồ Khối lượng ────────────────────────────────────────────────────
    # Tô màu xanh/đỏ theo nến tăng/giảm
    colors_vol = [
        '#26a69a' if row['Close'] >= row['Open'] else '#ef5350'
        for _, row in df.iterrows()
    ]
    fig.add_trace(
        go.Bar(
            x=df.index, y=df['Volume'],
            name='Khối lượng',
            marker_color=colors_vol,
            marker_line_width=0,
            opacity=0.7
        ),
        row=2, col=1
    )
    
    # ── Layout tổng thể ───────────────────────────────────────────────────────
    fig.update_layout(
        height=750,                     # Chiếm tối đa không gian
        margin=dict(l=0, r=0, t=20, b=0),
        template="plotly_dark",
        paper_bgcolor="#121212",
        plot_bgcolor="#121212",
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.01,
            xanchor="right",  x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11)
        ),
        hovermode='x unified',          # Tooltip thống nhất theo trục X
        xaxis_rangeslider_visible=False
    )
    
    # Grid lines
    grid_cfg = dict(showgrid=True, gridcolor='#2a2a2a', gridwidth=1)
    fig.update_xaxes(**grid_cfg)
    fig.update_yaxes(**grid_cfg, side='right')
    
    # Nhãn trục Y
    fig.update_yaxes(title_text="Giá", row=1, col=1)
    fig.update_yaxes(title_text="KL", row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'scrollZoom': True          # Cho phép zoom bằng scroll
    })
