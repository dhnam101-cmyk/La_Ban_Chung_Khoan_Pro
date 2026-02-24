import yfinance as yf
import requests
from bs4 import BeautifulSoup
import streamlit as st

def get_from_yahoo(ticker):
    """Nguồn 1: Yahoo Finance"""
    stock = yf.Ticker(f"{ticker}.VN")
    df = stock.history(period="1d")
    if df.empty: raise Exception("Yahoo Empty")
    return {"price": df['Close'].iloc[-1], "source": "Yahoo"}

def get_from_cafef(ticker):
    """Nguồn 2: Cào dữ liệu từ CafeF (Dự phòng)"""
    url = f"https://s.cafef.vn/hose/{ticker}-cong-ty-co-phan.chn"
    res = requests.get(url, timeout=5)
    soup = BeautifulSoup(res.text, 'html.parser')
    price = soup.find("div", {"class": "cp-price"}).text # Giả lập logic cào
    return {"price": float(price) * 1000, "source": "CafeF"}

def get_stock_data(ticker):
    """Hệ thống điều phối đa nguồn"""
    sources = [get_from_yahoo, get_from_cafef]
    
    for fetch_method in sources:
        try:
            data = fetch_method(ticker)
            if data: return data
        except:
            continue # Thất bại nguồn này, nhảy sang nguồn kế tiếp
            
    return {"price": 0, "source": "All Sources Failed"}
