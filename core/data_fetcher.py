import yfinance as yf
import requests
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_fixed

# --- TẦNG 1: TCBS ---
def get_fundamentals_tcbs(ticker):
    url = f"https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview"
    res = requests.get(url, timeout=5)
    if res.status_code == 200:
        data = res.json()
        return {
            "pe": round(data.get("pe", 0), 2) if data.get("pe") else "N/A",
            "pb": round(data.get("pb", 0), 2) if data.get("pb") else "N/A",
            "industry": data.get("industryName", "Chưa phân loại"),
            "avg_pe": round(data.get("industryPe", 0), 2) if data.get("industryPe") else 0,
            "avg_pb": round(data.get("industryPb", 0), 2) if data.get("industryPb") else 0,
            "market": data.get("exchange", "HOSE").replace("HSX", "HOSE"),
            "source": "TCBS API"
        }
    raise Exception("TCBS lỗi")

# --- TẦNG 2: VNDIRECT ---
def get_fundamentals_vndirect(ticker):
    headers = {'User-Agent': 'Mozilla/5.0'}
    r1 = requests.get(f"https://finfo-api.vndirect.com.vn/v4/ratios/latest?filter=ticker:{ticker}", headers=headers, timeout=5)
    r2 = requests.get(f"https://finfo-api.vndirect.com.vn/v4/stocks?q=code:{ticker}", headers=headers, timeout=5)
    
    if r1.status_code == 200 and r2.status_code == 200:
        r1_data = r1.json().get('data', [{}])[0]
        r2_data = r2.json().get('data', [{}])[0]
        return {
            "pe": round(r1_data.get("pe", 0), 2) if r1_data.get("pe") else "N/A",
            "pb": round(r1_data.get("pb", 0), 2) if r1_data.get("pb") else "N/A",
            "industry": r2_data.get("industryName", "Chưa phân loại"),
            "avg_pe": 0, "avg_pb": 0,
            "market": r2_data.get("floor", "HOSE").upper(),
            "source": "VNDirect API"
        }
    raise Exception("VNDirect lỗi")

# --- TRUNG TÂM ĐIỀU PHỐI ---
@st.cache_data(ttl=300, show_spinner=False)
@retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
def get_stock_data(ticker):
    try:
        # Lấy Giá từ Yahoo
        stock = yf.Ticker(f"{ticker}.VN")
        df = stock.history(period="1d")
        if df.empty: return {"error": f"Không tìm thấy dữ liệu mã {ticker}"}
        price, volume = round(df['Close'].iloc[-1], 0), int(df['Volume'].iloc[-1])

        # Lấy P/E, P/B từ TCBS -> VNDirect -> Yahoo
        fund_data = {}
        try:
            fund_data = get_fundamentals_tcbs(ticker)
        except Exception:
            try:
                fund_data = get_fundamentals_vndirect(ticker)
            except Exception:
                info = stock.info
                fund_data = {
                    "pe": round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else "N/A",
                    "pb": round(info.get('priceToBook', 0), 2) if info.get('priceToBook') else "N/A",
                    "industry": info.get('industry', 'Chưa phân loại'),
                    "avg_pe": 0, "avg_pb": 0, "market": "HOSE", "source": "Yahoo"
                }

        return {"ticker": ticker, "price": price, "volume": volume, **fund_data}
    except Exception as e:
        return {"error": f"Lỗi hệ thống: {str(e)}"}
