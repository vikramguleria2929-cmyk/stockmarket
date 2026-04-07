from flask import Flask, render_template, request
import yfinance as yf
from utils import calculate_indicators
from datetime import datetime
import pandas as pd
from flask import Flask, jsonify
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from dotenv import load_dotenv
import os
import json
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler


load_dotenv()  # Load .env file


EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")


ALERT_FILE = "alerts.json"

app = Flask(__name__)


# Symbols: (symbol_name, is_index)
symbols = {
    # ===== INDIAN STOCKS =====
    "Bharti Airtel": ("BHARTIARTL.NS", False),
    "Reliance Industries": ("RELIANCE.NS", False),
    "TCS": ("TCS.NS", False),
    "HDFC Bank": ("HDFCBANK.NS", False),
    "Infosys": ("INFY.NS", False),
    "ICICI Bank": ("ICICIBANK.NS", False),
    "ITC": ("ITC.NS", False),
    "State Bank of India": ("SBIN.NS", False),
    "Bajaj Finance": ("BAJFINANCE.NS", False),
    "Wipro": ("WIPRO.NS", False),
    "Vodafone Idea": ("IDEA.NS", False),

    # ===== INDIAN INDICES =====
    "Nifty 50": ("^NSEI", True),
    "BankNifty": ("^NSEBANK", True),

    # ===== CRYPTO =====
    "Bitcoin": ("BTC-USD", True),
    "Ethereum": ("ETH-USD", True),
    "Binance Coin": ("BNB-USD", True),
    "Solana": ("SOL-USD", True),
    "Dogecoin": ("DOGE-USD", True),

    # ===== GLOBAL STOCKS =====
    "Apple": ("AAPL", False),
    "Microsoft": ("MSFT", False),
    "Tesla": ("TSLA", False),
    "Amazon": ("AMZN", False),
    "Google": ("GOOGL", False),

    # ===== COMMODITIES =====
    "Gold": ("GC=F", True),
    "Silver": ("SI=F", True),
    "Crude Oil": ("CL=F", True),
}


def fetch_data(symbol, is_index=False):
    """
    Fetch stock/index data and calculate indicators.
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="1m")
        if df.empty:
            df = ticker.history(period="5d", interval="5m")
        if df.empty:
            print(f"No data returned for {symbol}")
            return []

        df = df.reset_index()
        if "Datetime" not in df.columns and "Date" in df.columns:
            df.rename(columns={"Date": "Datetime"}, inplace=True)

        df["Datetime"] = pd.to_datetime(df["Datetime"])

        if not is_index:
            # Resample for better visualization
            df = df.resample("15min", on="Datetime").agg({
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum"
            }).dropna().reset_index()
        else:
            df["Volume"] = 0

        df = calculate_indicators(df)
        return df.tail(200).to_dict(orient="records")

    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return []


@app.route("/")
def index():
    """
    Main page with pagination: 1 company per page.
    """
    page = int(request.args.get("page", 1))
    per_page = 1  # Show 1 company per page

    all_companies = list(symbols.keys())
    total_pages = len(all_companies)

    # Determine which company to show
    start = (page - 1) * per_page
    end = start + per_page
    visible_symbols = list(symbols.items())[start:end]

    # Fetch data for the selected company
    data_dict = {name: fetch_data(symbol, is_index)
                 for name, (symbol, is_index) in visible_symbols}

    # For search/autocomplete in template
    company_pages = {c.lower(): i+1 for i, c in enumerate(all_companies)}

    return render_template(
        "index.html",
        data=data_dict,
        page=page,
        total_pages=total_pages,
        company_pages=company_pages,
        year=datetime.now().year
    )


# =======================================================================================

@app.route('/real-financial-data')
def real_financial_data():
    import yfinance as yf
    page = int(request.args.get("page", 1))
    per_page = 1
    all_companies = list(symbols.keys())
    start = (page - 1) * per_page
    end = start + per_page
    visible_companies = all_companies[start:end]

    final = []
    for i, sym in enumerate(visible_companies):
        symbol, is_index = symbols[sym]
        try:
            t = yf.Ticker(symbol)
            info = t.info

            # Get price data - handle different data types
            current_price = info.get("currentPrice")
            if current_price is None:
                current_price = info.get("regularMarketPrice")
            if current_price is None:
                current_price = info.get("previousClose")
            if current_price is None:
                current_price = info.get("open")

            # Check if this is a commodity/crypto (no financial metrics)
            is_commodity_or_crypto = sym in [
                "Crude Oil", "Silver", "Gold", "Bitcoin", "Ethereum", "Binance Coin", "Solana", "Dogecoin"]

            if is_commodity_or_crypto or is_index:
                # For commodities, crypto, and indices - show limited data
                market_cap = info.get("marketCap")
                if market_cap:
                    market_cap_cr = market_cap / 10000000
                else:
                    market_cap_cr = 0

                final.append({
                    "sno": i + 1,
                    "name": sym,
                    "cmp": current_price if current_price else 0,
                    "pe": "N/A",  # Not applicable
                    "marCap": market_cap_cr if market_cap_cr else 0,
                    "divYld": "N/A",  # Not applicable
                    "npQtr": "N/A",  # Not applicable
                    "profitVar": "N/A",  # Not applicable
                    "salesQtr": "N/A",  # Not applicable
                    "salesVar": "N/A",  # Not applicable
                    "roce": "N/A",  # Not applicable
                })
            else:
                # For regular companies - show all financial metrics
                # Market Cap in Crores
                market_cap = info.get("marketCap")
                if market_cap:
                    market_cap_cr = market_cap / 10000000
                else:
                    market_cap_cr = 0

                # Dividend Yield (convert from decimal to percentage)
                div_yield = info.get("dividendYield", 0)
                if div_yield:
                    div_yield_pct = div_yield * 100
                else:
                    div_yield_pct = 0

                # Profit Margin (convert to percentage)
                profit_margin = info.get("profitMargins", 0)
                if profit_margin:
                    profit_var_pct = profit_margin * 100
                else:
                    profit_var_pct = 0

                # Revenue Growth (convert to percentage)
                revenue_growth = info.get("revenueGrowth", 0)
                if revenue_growth:
                    sales_var_pct = revenue_growth * 100
                else:
                    sales_var_pct = 0

                # ROCE (convert to percentage)
                roce = info.get("returnOnEquity", 0)
                if roce:
                    roce_pct = roce * 100
                else:
                    roce_pct = 0

                final.append({
                    "sno": i + 1,
                    "name": sym,
                    "cmp": current_price if current_price else 0,
                    "pe": info.get("trailingPE", 0),
                    "marCap": market_cap_cr if market_cap_cr else 0,
                    "divYld": div_yield_pct if div_yield_pct else 0,
                    "npQtr": info.get("netIncomeToCommon", 0),
                    "profitVar": profit_var_pct if profit_var_pct else 0,
                    "salesQtr": info.get("totalRevenue", 0),
                    "salesVar": sales_var_pct if sales_var_pct else 0,
                    "roce": roce_pct if roce_pct else 0,
                })

        except Exception as e:
            print(f"Error fetching data for {sym}: {e}")
            # Return empty data with N/A for all fields
            final.append({
                "sno": i + 1,
                "name": sym,
                "cmp": 0,
                "pe": "N/A",
                "marCap": 0,
                "divYld": "N/A",
                "npQtr": "N/A",
                "profitVar": "N/A",
                "salesQtr": "N/A",
                "salesVar": "N/A",
                "roce": "N/A",
            })

    return jsonify(final)

# =========================================real market overview for pie cart =====================================


@app.route('/real-market-overview')
def real_market_overview():
    import yfinance as yf

    # Symbols for the pie chart (example: top stocks)
    symbols_list = {
        "Bharti Airtel": "BHARTIARTL.NS",
        "Reliance Industries": "RELIANCE.NS",
        "TCS": "TCS.NS",
        "HDFC Bank": "HDFCBANK.NS",
        "Infosys": "INFY.NS",
        "ICICI Bank": "ICICIBANK.NS",
        "ITC": "ITC.NS",
        "State Bank of India": "SBIN.NS",
        "Bajaj Finance": "BAJFINANCE.NS",
        "Wipro": "WIPRO.NS",
        "Vodafone Idea": "IDEA.NS",
    }

    final = []
    for name, symbol in symbols_list.items():
        try:
            t = yf.Ticker(symbol)
            info = t.info
            # Using Market Cap for pie chart distribution
            value = info.get("marketCap", 0) or 0
            final.append({
                "name": name,
                "value": value
            })
        except:
            continue

    return jsonify(final)

# ================================================market overview=================================


@app.route("/market-overview")
def market_overview():
    indices = {
        "NIFTY 50": "^NSEI",
        "BankNifty": "^NSEBANK",
        "Sensex": "^BSESN",
        "USD/INR": "INR=X",
        "Gold": "GC=F"
    }

    data = {}

    for name, symbol in indices.items():
        try:
            ticker = yf.Ticker(symbol)
            price = ticker.history(period="1d")["Close"].iloc[-1]
            prev = ticker.history(period="2d")["Close"].iloc[0]
            change = round(((price - prev) / prev) * 100, 2)

            data[name] = {
                "price": round(price, 2),
                "change": change
            }
        except:
            data[name] = {"price": None, "change": None}

    return jsonify(data)

# ===========================================compare-stocks========================================================


@app.route("/compare-stocks-page")
def compare_stocks_page():
    return render_template("compareStocks.html")


@app.route("/compare-stocks")
def compare_stocks():
    symbols = {
        "Bharti Airtel": "BHARTIARTL.NS",
        "Reliance Industries": "RELIANCE.NS",
        "TCS": "TCS.NS",
        "HDFC Bank": "HDFCBANK.NS",
        "Infosys": "INFY.NS",
        "ICICI Bank": "ICICIBANK.NS",
        "ITC": "ITC.NS",
        "State Bank of India": "SBIN.NS",
        "Bajaj Finance": "BAJFINANCE.NS",
        "Wipro": "WIPRO.NS",
        "Vodafone Idea": "IDEA.NS"
    }

    data = []

    for name, symbol in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            cmp = hist["Close"].iloc[-1]
            pe = ticker.info.get("trailingPE", 0)
            market_cap = ticker.info.get("marketCap", 0) / 1e7  # Rs.Cr.
            div_yield = ticker.info.get(
                "dividendYield", 0) * 100 if ticker.info.get("dividendYield") else 0
            np_qtr = round(cmp * 1000 / 1e7, 2)  # Dummy net profit
            profit_var = round(((cmp - cmp*0.95)/cmp)*100, 2)  # Dummy %
            sales_qtr = round(cmp * 2000 / 1e7, 2)  # Dummy sales
            sales_var = round(((cmp - cmp*0.9)/cmp)*100, 2)  # Dummy %
            roce = round(((cmp*0.15)/cmp)*100, 2)  # Dummy ROCE %

            data.append({
                "name": name,
                "symbol": symbol,
                "cmp": round(cmp, 2),
                "pe": round(pe, 2),
                "marCap": round(market_cap, 2),
                "divYld": round(div_yield, 2),
                "npQtr": np_qtr,
                "profitVar": profit_var,
                "salesQtr": sales_qtr,
                "salesVar": sales_var,
                "roce": roce
            })
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")

    # Sort by CMP descending (most profitable at top)
    data.sort(key=lambda x: x["cmp"], reverse=True)

    return jsonify({"status": "success", "data": data})

# ==============hot cart page=====================================================


@app.route("/hotchart")
def hot_chart_page():
    return render_template("hotchart.html")


# ================= HOT CHART REAL DATA API =====================

@app.route("/hotchart-data")
def hotchart_data():
    import yfinance as yf

    symbols = [
        "BHARTIARTL.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS",
        "ICICIBANK.NS", "ITC.NS", "SBIN.NS", "BAJFINANCE.NS", "WIPRO.NS",
        "IDEA.NS"
    ]

    data = []

    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="2d")

            if hist.empty:
                continue

            current = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[0]
            change = current - prev
            change_percent = round((change / prev) * 100, 2)

            volume = hist["Volume"].iloc[-1]

            data.append({
                "symbol": sym.replace(".NS", ""),
                "current_price": round(current, 2),
                "change": round(change, 2),
                "change_percent": change_percent,
                "volume": int(volume)
            })
        except:
            continue

    # split data into categories
    top_gainers = sorted(
        data, key=lambda x: x["change_percent"], reverse=True)[:5]
    top_losers = sorted(data, key=lambda x: x["change_percent"])[:5]
    most_active = sorted(data, key=lambda x: x["volume"], reverse=True)[:5]

    return jsonify({
        "gainers": top_gainers,
        "losers": top_losers,
        "active": most_active
    })


# ==============================for footer show show data =====================

@app.route('/footer-data')
def footer_data():
    # Get the current page number from request args
    page = request.args.get('page', 1, type=int)

    # Get all companies
    all_companies = list(symbols.keys())
    total_pages = len(all_companies)

    # Determine which company is on this page
    current_company = ""
    if 1 <= page <= total_pages:
        current_company = all_companies[page - 1]

    # Clean company name (remove extra spaces, etc.)
    current_company_clean = current_company.strip().upper().split()[
        0] if current_company else ""

    # Define the specific tickers for the footer (BTC, ETH, SPY, AAPL, VIX)
    footer_symbols = {
        "BTC": "BTC-USD",      # Bitcoin
        "ETH": "ETH-USD",      # Ethereum
        "SPY": "SPY",          # S&P 500 ETF
        "AAPL": "AAPL",        # Apple
        "VIX": "^VIX",         # Volatility Index
    }

    # Add Indian market indices for context
    indian_indices = {
        "NIFTY": "^NSEI",      # Nifty 50
        "SENSEX": "^BSESN",    # Sensex
        "BANKNIFTY": "^NSEBANK"  # Bank Nifty
    }

    # Merge all symbols
    all_symbols = {**footer_symbols, **indian_indices}

    # Prepare response data
    response_data = {
        "current_company": current_company,
        "current_company_clean": current_company_clean,
        "page": page,
        "total_pages": total_pages,
        "timestamp": datetime.now().isoformat(),
        "footer_tickers": {},
    }

    # Fetch data for all tickers
    for display_name, symbol in all_symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Get current price
            current_price = info.get("currentPrice")
            if current_price is None:
                current_price = info.get("regularMarketPrice")
            if current_price is None:
                current_price = info.get("regularMarketPreviousClose")
            if current_price is None:
                current_price = info.get("previousClose")
            if current_price is None:
                # Try to get from history if info doesn't have price
                hist = ticker.history(period="1d", interval="1m")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]

            # Get previous close
            previous_close = info.get("previousClose")
            if previous_close is None:
                hist = ticker.history(period="2d")
                if len(hist) >= 2:
                    previous_close = hist['Close'].iloc[-2]
                elif current_price is not None:
                    # If we can't get previous close, assume no change
                    previous_close = current_price

            # Calculate change
            change = 0
            change_percent = 0
            if current_price is not None and previous_close is not None and previous_close != 0:
                change = current_price - previous_close
                change_percent = (change / previous_close) * 100

            response_data["footer_tickers"][display_name] = {
                "symbol": symbol,
                "price": round(current_price, 2) if current_price is not None else None,
                "change": round(change, 2) if current_price is not None else None,
                "change_percent": round(change_percent, 2) if current_price is not None else None,
                "is_positive": change >= 0 if current_price is not None else None,
                "name": display_name
            }

        except Exception as e:
            print(f"Error fetching {display_name} ({symbol}): {e}")
            response_data["footer_tickers"][display_name] = {
                "symbol": symbol,
                "price": None,
                "change": None,
                "change_percent": None,
                "is_positive": None,
                "name": display_name
            }

    return jsonify(response_data)

# ============================== Email send System =====================


def send_email(symbol, current_price, alert, diff):
    arrow = "⬆️ UP" if diff > 0 else "⬇️ DOWN"
    sign = "+" if diff > 0 else ""

    message = f"""
Stock Alert 🚨

{symbol} price {arrow} 

Target Price : {alert['target_price']}
Current Price: {round(current_price, 2)}
Difference   : {sign}{round(diff, 2)}

Condition    : {alert['condition'].upper()}
"""

    msg = MIMEText(message)
    msg["Subject"] = "📩 Stock Price Alert"
    msg["From"] = EMAIL_USER
    msg["To"] = alert["email"]

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASS)
    server.send_message(msg)
    server.quit()


def load_alerts():
    try:
        with open(ALERT_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_alerts(alerts):
    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, indent=4)

# ==================alert route=============================


@app.route("/alert")
def alert_page():
    return render_template("alert.html")


@app.route("/set-alert", methods=["POST"])
def set_alert():
    data = request.json

    user_symbol = data["symbol"].strip()

    final_symbol = None
    for name, (sym, _) in symbols.items():
        if user_symbol.lower() == name.lower() or user_symbol.upper() == sym.replace(".NS", ""):
            final_symbol = sym
            break

    if not final_symbol:
        return jsonify({"message": "❌ Invalid company name or symbol"}), 400

    alert = {
        "symbol": final_symbol,
        "target_price": float(data["target_price"]),
        "condition": data["condition"],
        "email": data["email"]
    }

    alerts = load_alerts()
    alerts.append(alert)
    save_alerts(alerts)

    return jsonify({"message": "✅ Alert saved successfully"})


# ===============alert function check alert=========================


def check_alerts():
    alerts = load_alerts()

    for alert in alerts:
        try:
            price = yf.Ticker(alert["symbol"]).history(
                period="1d")["Close"].iloc[-1]
            price = float(price)

            target = alert["target_price"]
            diff = price - target

            # ⬆️ ABOVE CONDITION
            if alert["condition"] == "above" and price >= target:
                send_email(alert["symbol"], price, alert, diff)

            # ⬇️ BELOW CONDITION
            elif alert["condition"] == "below" and price <= target:
                send_email(alert["symbol"], price, alert, diff)

        except Exception as e:
            print("Alert error:", e)

scheduler = BackgroundScheduler()
scheduler.add_job(
    check_alerts,
    "interval",
    minutes=1,
    max_instances=1,  
    coalesce=True      
)
scheduler.start()


# ===================delete alert button====================

@app.route("/get-alerts")
def get_alerts():
    return jsonify(load_alerts())


@app.route("/delete-alert/<int:index>", methods=["POST"])
def delete_alert(index):
    alerts = load_alerts()
    if index < len(alerts):
        alerts.pop(index)
        save_alerts(alerts)
        return jsonify({"message": "Alert removed"})
    return jsonify({"message": "Invalid index"}), 400


# ========================AboutUs==========================================

@app.route("/about")
def about_page():
    return render_template("about.html")


# =====================contactus===========================================


@app.route("/contact")
def contact_page():
    return render_template("contact.html")


# ================= SEND CONTACT EMAIL =================

load_dotenv(dotenv_path=".env")


@app.route("/send-contact", methods=["POST"])
def send_contact():
    user_email = request.form.get("email")
    user_message = request.form.get("message")

    email_body = f"""
New Contact Message 📩

User Email:
{user_email}

User Message:
{user_message}
"""

    msg = MIMEText(email_body)
    msg["Subject"] = "📬 New Contact Message"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER
    msg["Reply-To"] = user_email

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASS)
    server.send_message(msg)
    server.quit()

    return render_template("contact.html", message="✅ Message sent successfully")


# ================= SEND CONTACT =================


if __name__ == "__main__":
    app.run(debug=False)
