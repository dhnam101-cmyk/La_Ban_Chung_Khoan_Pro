import streamlit as st
import yfinance as yf
from streamlit_lightweight_charts import renderLightweightCharts

def render_tradingview_chart(ticker, exchange="HOSE"):
    # Giải pháp dứt điểm: Dùng Lightweight Charts tự vẽ để không bao giờ bị dính bản quyền TradingView
    try:
        stock = yf.Ticker(f"{ticker}.VN")
        df = stock.history(period="1y")
        
        if df.empty:
            st.warning(f"Không có dữ liệu biểu đồ cho mã {ticker}")
            return

        # Chuyển đổi dữ liệu ngày tháng
        df = df.reset_index()
        candles = []
        for _, row in df.iterrows():
            candles.append({
                "time": row['Date'].strftime('%Y-%m-%d'),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close'])
            })

        # Cấu hình giao diện biểu đồ (Theme tối chuyên nghiệp)
        chartOptions = {
            "height": 550,
            "layout": {
                "textColor": 'rgba(255, 255, 255, 0.9)',
                "background": {"type": 'solid', "color": '#121212'}
            },
            "grid": {
                "vertLines": {"color": 'rgba(197, 203, 206, 0.1)'},
                "horzLines": {"color": 'rgba(197, 203, 206, 0.1)'}
            },
            "crosshair": {"mode": 1},
            "timeScale": {"borderColor": 'rgba(197, 203, 206, 0.8)', "timeVisible": True}
        }

        seriesCandleChart = [{
            "type": 'Candlestick',
            "data": candles,
            "options": {
                "upColor": '#26a69a',
                "downColor": '#ef5350',
                "borderVisible": False,
                "wickUpColor": '#26a69a',
                "wickDownColor": '#ef5350'
            }
        }]

        renderLightweightCharts([
            {"chart": chartOptions, "series": seriesCandleChart}
        ], f'chart_{ticker}')

    except Exception as e:
        st.error(f"Lỗi vẽ biểu đồ: {e}")
