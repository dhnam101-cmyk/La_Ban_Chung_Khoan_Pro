# 📈 La Bàn Chứng Khoán Pro AI

**Hệ thống phân tích chứng khoán thông minh tích hợp dữ liệu thời gian thực và Trí tuệ nhân tạo (Google Gemini).**

---

## 🚀 Tính năng nổi bật

* [cite_start]**Dữ liệu Real-time 100%**: Truy xuất giá khớp lệnh và khối lượng giao dịch tức thời từ các nguồn uy tín[cite: 4, 7].
* [cite_start]**Biểu đồ TradingView Chuyên nghiệp**: Tích hợp biểu đồ nến và khối lượng đa tầng, hỗ trợ đầy đủ các công cụ vẽ phân tích kỹ thuật (VSA)[cite: 8].
* [cite_start]**Phân tích AI Đa nguồn**: Sử dụng mô hình **Gemini 1.5 Flash** để tổng hợp vĩ mô và đưa ra khuyến nghị đầu tư sắc bén.
* [cite_start]**Kiến trúc Chống sập (Anti-Crash)**: Hệ thống dự phòng đa lớp đảm bảo dữ liệu luôn hiển thị ngay cả khi nguồn chính gặp sự cố[cite: 7].

---

## 🛠 Kiến trúc Hệ thống (Modular Design)

Dự án được xây dựng theo cấu trúc mô-đun hóa để đảm bảo khả năng mở rộng và dễ dàng bảo trì:

* [cite_start]📂 `ai_core/`: Quản lý bộ não AI và các kịch bản dự phòng (Fallback).
* [cite_start]📂 `components/`: Xử lý hiển thị giao diện biểu đồ TradingView[cite: 8].
* [cite_start]📂 `data/`: Trạm xử lý dữ liệu, API và cơ chế Caching bảo vệ hệ thống[cite: 4, 7].
* [cite_start]📄 `app.py`: Trung tâm điều phối và giao diện người dùng Streamlit[cite: 1].

---

## ⚙️ Hướng dẫn Cài đặt & Sử dụng

### 1. Yêu cầu hệ thống
Các thư viện cần thiết đã được liệt kê chi tiết trong tệp `requirements.txt`, bao gồm:
[cite_start]`streamlit`, `pandas`, `google-generativeai`, `tenacity`,... [cite: 1, 2, 7, 9]

### 2. Cấu hình bảo mật (Secrets)
Để hệ thống AI hoạt động, bạn cần cấu hình khóa API trong mục **Settings > Secrets** của Streamlit:
```toml
GOOGLE_API_KEY = "Mã_API_Của_Bạn"
