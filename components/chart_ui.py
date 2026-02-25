import streamlit as st
import streamlit.components.v1 as components

def render_tradingview_chart(ticker, exchange="HOSE"):
    # BỘ LỌC ÉP SÀN: Ngăn chặn lỗi Popup TradingView khi Yahoo trả về mã sàn lạ (VSE)
    exch_upper = str(exchange).upper()
    if exch_upper not in ["HOSE", "HNX", "UPCOM"]:
        exch_upper = "HOSE"
        
    tv_symbol = f"{exch_upper}:{ticker}"
    
    html_code = f"""
    <div class="tradingview-widget-container" style="height:100%;width:100%">
      <div id="tv_{ticker}" style="height:calc(100% - 32px);width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
      "autosize": true,
      "symbol": "{tv_symbol}",
      "interval": "D",
      "timezone": "Asia/Ho_Chi_Minh",
      "theme": "dark",
      "style": "1",
      "locale": "vi_VN",
      "enable_publishing": false,
      "backgroundColor": "#121212",
      "gridColor": "#1f1f1f",
      "hide_top_toolbar": false,
      "hide_legend": false,
      "save_image": false,
      "container_id": "tv_{ticker}"
      }});
      </script>
    </div>
    """
    # Chiều cao 700px để bạn thoải mái dùng các công cụ phân tích kỹ thuật
    components.html(html_code, height=700)
