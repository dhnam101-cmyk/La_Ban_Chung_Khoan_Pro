import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

def render_tradingview_chart(ticker, exchange="HOSE"):
    try:
        # Lấy dữ liệu 1 năm từ Yahoo
        df = yf.download(f"{ticker}.VN", period="1y", progress=False)
        if df.empty:
            st.warning(f"Không có dữ liệu biểu đồ cho {ticker}")
            return

        # Vẽ biểu đồ Nến (Candlestick) bằng Plotly
        fig = go.Figure(data=[go.Candlestick(
            x=df.index,
            open=df['Open'].squeeze(),
            high=df['High'].squeeze(),
            low=df['Low'].squeeze(),
            close=df['Close'].squeeze(),
            increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
        )])

        # Tùy chỉnh kích thước SIÊU TO (Height = 700) và giao diện Dark Mode
        fig.update_layout(
            height=700, 
            margin=dict(l=0, r=0, t=10, b=0),
            template="plotly_dark",
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            xaxis_rangeslider_visible=False,
            xaxis=dict(showgrid=True, gridcolor='#333333'),
            yaxis=dict(showgrid=True, gridcolor='#333333', side='right')
        )
        
        # Hiển thị biểu đồ full chiều rộng
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi vẽ biểu đồ: {e}")
