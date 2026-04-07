import yfinance as yf
import requests
import pandas as pd

class YahooClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })

    def ticker(self, symbol):
        return yf.Ticker(symbol, session=self.session)

    def history(self, symbol, period="1d", interval=None):
        try:
            t = self.ticker(symbol)
            df = t.history(period=period, interval=interval, timeout=30)
            return df if not df.empty else pd.DataFrame()
        except Exception as e:
            print(f"[Yahoo history error] {symbol}:", e)
            return pd.DataFrame()

    def price(self, symbol):
        """Cloud-safe price fetch"""
        df = self.history(symbol, period="1d", interval="1m")
        if not df.empty:
            return float(df["Close"].iloc[-1])
        return None

    def info_safe(self, symbol):
        """Never trust ticker.info in cloud"""
        try:
            t = self.ticker(symbol)
            info = t.info
            return info if isinstance(info, dict) else {}
        except:
            return {}
