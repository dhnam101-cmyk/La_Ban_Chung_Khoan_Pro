import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import streamlit as st

def get_industry_benchmarks(ticker):
    """Giả lập lấy dữ liệu ngành từ CafeF/Vietstock (Dự phòng khi chưa có API trả phí)"""
    # Trong thực tế, đây là nơi cào dữ liệu trung bình ngành
    benchmarks = {
        "Ngân hàng": {"avg_pe": 12.5, "avg_pb": 1.8},
        "Bất động sản": {"avg_pe": 15.2, "avg_pb": 2.1},
        "Công nghệ": {"avg_pe": 22.0, "avg_pb": 4.5},
        "Bán lẻ": {"avg_pe": 18.5, "avg_pb": 3.2}
    }
    # Mặc định trả về Công nghệ nếu là FPT, Ngân hàng nếu là VCB...
    if ticker in ['FPT', 'CMG']: return "Công nghệ", benchmarks["Công nghệ"]
    if ticker in ['VCB', 'BID', 'CTG']: return "Ngân hàng", benchmarks["Ngân hàng"]
    return "Chưa phân loại", {"avg_pe": 0, "avg_pb": 0}

def get_stock_data(ticker):
    try:
        symbol = f"{ticker}.VN"
        stock = yf.Ticker(symbol)
        df = stock.history(period="1d")
        
        if df.empty:
            return {"error": "Không tìm thấy dữ liệu"}

        info = stock.info
        industry_name, industry_data = get_industry_benchmarks(ticker)

        return {
            "ticker": ticker,
            "price": round(df['Close'].iloc[-1], 0),
            "volume": int(df['Volume'].iloc[-1]),
            "pe": round(info.get('trailingPE', 0), 2) if info.get('trailingPE') else "N/A",
            "pb": round(info.get('priceToBook', 0), 2) if info.get('priceToBook') else "N/A",
            "industry": industry_name,
            "avg_pe": industry_data["avg_pe"],
            "avg_pb": industry_data["avg_pb"],
            "market": info.get('exchange', 'HOSE'),
            "source": "Yahoo Finance + Industry DB"
        }
    except Exception as e:
        return {"error": str(e)}
