# 📈 La Bàn Chứng Khoán AI Pro — v2.0

Hệ thống phân tích chứng khoán thông minh tích hợp dữ liệu thời gian thực và Google Gemini AI.

---

## 🆕 Thay đổi trong v2.0

| Vấn đề (v1) | Giải pháp (v2) |
|---|---|
| `YFRateLimitError` làm sập app | Retry logic 3 lần + thông báo thân thiện |
| "Quote not found" khi nhập câu hỏi | Smart Routing phân biệt ticker vs câu hỏi |
| AI crash do không có dữ liệu | Truyền `stock_data` dict vào prompt |
| Biểu đồ nhỏ, metrics to | Chart 750px, metrics thu gọn 7 cột |
| Chatbot nằm lẫn với chart | Chatbot luôn render bên dưới chart |

---

## 🚀 Tính năng

- **Dữ liệu Real-time**: Giá, khối lượng từ Yahoo Finance + cơ bản từ TCBS
- **Smart Routing**: Tự động phân biệt mã cổ phiếu vs câu hỏi thị trường
- **Biểu đồ Nến Full-size**: Candlestick + SMA 20/50 + Volume sub-chart
- **Đa khu vực**: Việt Nam (VN), Mỹ (US), Quốc tế
- **Chatbot AI**: Gemini 2.0 Flash/Pro với context dữ liệu thực tế
- **Voice Input/Output**: Tìm kiếm và nghe phân tích bằng giọng nói

---

## 🛠 Cài đặt

```bash
pip install -r requirements.txt
```

### Cấu hình API Key

Tạo file `.streamlit/secrets.toml`:
```toml
GOOGLE_API_KEY = "your_gemini_api_key"
```

> Lấy key miễn phí: https://aistudio.google.com/

### Chạy ứng dụng

```bash
streamlit run app.py
```

---

## 📁 Cấu trúc File

```
├── app.py              # Entry point, Smart Routing, UI layout
├── data_fetcher.py     # Lấy dữ liệu (yfinance + TCBS), có retry
├── chart_ui.py         # Biểu đồ Plotly full-size
├── chatbot_ui.py       # Giao diện chat AI
├── ai_engine.py        # Tích hợp Google Gemini
├── requirements.txt
└── locales/
    ├── vi.json         # Tiếng Việt
    └── en.json         # English
```

---

## ⚠️ Lưu ý

- Đây là công cụ phân tích tham khảo, **không phải lời khuyên đầu tư chính thức**
- Dữ liệu Yahoo Finance có thể bị rate-limit — hãy đợi 30s nếu gặp lỗi
- Gemini Free Tier có giới hạn 15 requests/phút
