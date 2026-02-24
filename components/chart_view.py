import streamlit.components.v1 as components

def render_tradingview_chart(ticker):
    """
    Hàm nhúng biểu đồ TradingView chuyên nghiệp vào Streamlit.
    Hỗ trợ Nến Nhật, Khối lượng (Volume), và các công cụ vẽ VSA.
    """
    # Xử lý mã cổ phiếu: Thêm tiền tố sàn (VD: HOSE:) để TradingView dễ nhận diện
    # Tạm thời cấu hình mặc định là mã VN, nếu không tìm thấy TV sẽ tự tìm quốc tế.
    tv_symbol = f"HOSE:{ticker}" if len(ticker) <= 4 else ticker

    # Đoạn mã HTML/JS lấy trực tiếp từ hệ thống của TradingView
    html_code = f"""
    <div class="tradingview-widget-container" style="height:100%;width:100%">
      <div class="tradingview-widget-container__widget" style="height:calc(100% - 32px);width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {{
      "autosize": true,
      "symbol": "{tv_symbol}",
      "interval": "D",
      "timezone": "Asia/Ho_Chi_Minh",
      "theme": "dark",
      "style": "1",
      "locale": "vi_VN",
      "enable_publishing": false,
      "backgroundColor": "rgba(14, 17, 23, 1)",
      "gridColor": "rgba(42, 46, 57, 0.06)",
      "hide_top_toolbar": false,
      "hide_legend": false,
      "save_image": false,
      "container_id": "tradingview_chart_{ticker}",
      "support_host": "https://www.tradingview.com"
    }}
      </script>
    </div>
    """
    
    # Hiển thị lên Streamlit với chiều cao 550px
    components.html(html_code, height=550)
