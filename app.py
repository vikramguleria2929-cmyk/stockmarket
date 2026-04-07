<<<<<<< HEAD
from flask import Flask, render_template, request
import yfinance as yf
from utils import calculate_indicators
from datetime import datetime
import pandas as pd
from flask import Flask, jsonify
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
=======
from flask import Flask, render_template, request, jsonify
>>>>>>> 15ca33b91de3ef6f9d886185ec76dfa3fcb8adae
from dotenv import load_dotenv
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from email.mime.text import MIMEText
import finnhub
from pycoingecko import CoinGeckoAPI
import os, json, smtplib

# ================= LOAD ENV =================
load_dotenv()

<<<<<<< HEAD
load_dotenv()  # Load .env file


=======
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
>>>>>>> 15ca33b91de3ef6f9d886185ec76dfa3fcb8adae
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

if not FINNHUB_API_KEY:
    raise ValueError("FINNHUB_API_KEY missing")

# ================= APP =================
app = Flask(__name__)

finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
cg = CoinGeckoAPI()

ALERT_FILE = "alerts.json"

# ================= CACHE SETUP =================
crypto_cache = {
    "data": None,
    "timestamp": None,
    "ttl": 60  # Cache for 60 seconds
}

stock_cache = {
    "AAPL": {"data": None, "timestamp": None, "ttl": 30}  # Cache for 30 seconds
}

# ================= SYMBOLS =================
symbols = {
    # Indian Stocks
    "Bharti Airtel": {"type": "stock", "symbol": "BHARTIARTL.NS"},
    "Reliance Industries": {"type": "stock", "symbol": "RELIANCE.NS"},
    "TCS": {"type": "stock", "symbol": "TCS.NS"},
    "HDFC Bank": {"type": "stock", "symbol": "HDFCBANK.NS"},
    "Infosys": {"type": "stock", "symbol": "INFY.NS"},
    "ICICI Bank": {"type": "stock", "symbol": "ICICIBANK.NS"},
    "ITC": {"type": "stock", "symbol": "ITC.NS"},
    "State Bank of India": {"type": "stock", "symbol": "SBIN.NS"},

    # Global
    "Apple": {"type": "stock", "symbol": "AAPL"},
    "Microsoft": {"type": "stock", "symbol": "MSFT"},
    "Tesla": {"type": "stock", "symbol": "TSLA"},

    # Indices
    "Nifty 50": {"type": "index", "symbol": "^NSEI"},
    "BankNifty": {"type": "index", "symbol": "^NSEBANK"},

    # Crypto
    "Bitcoin": {"type": "crypto", "symbol": "bitcoin"},
    "Ethereum": {"type": "crypto", "symbol": "ethereum"},
}

# ================= HELPERS =================
def get_price(name):
    item = symbols[name]

    if item["type"] == "crypto":
        # Use cached crypto data if available
        now = datetime.now()
        if (crypto_cache["timestamp"] and 
            (now - crypto_cache["timestamp"]).seconds < crypto_cache["ttl"] and
            crypto_cache["data"]):
            crypto_data = crypto_cache["data"]
            if item["symbol"] in crypto_data:
                return crypto_data[item["symbol"]]["usd"]
        
        # If not cached or cache expired, fetch new data
        try:
            data = cg.get_price(ids=item["symbol"], vs_currencies="usd")
            crypto_cache["data"] = data
            crypto_cache["timestamp"] = now
            return data[item["symbol"]]["usd"]
        except Exception as e:
            # If API fails and we have cached data, use it
            if crypto_cache["data"] and item["symbol"] in crypto_cache["data"]:
                return crypto_cache["data"][item["symbol"]]["usd"]
            raise e

    quote = finnhub_client.quote(item["symbol"])
    return quote.get("c")

def load_alerts():
    try:
        with open(ALERT_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_alerts(alerts):
    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, indent=4)

def send_email(symbol, price, alert, diff):
    arrow = "⬆️ UP" if diff > 0 else "⬇️ DOWN"
    msg = MIMEText(f"""
Stock Alert 🚨

{symbol} {arrow}

Target : {alert['target_price']}
Current: {price}
Diff   : {diff}
""")
    msg["Subject"] = "📩 Stock Price Alert"
    msg["From"] = EMAIL_USER
    msg["To"] = alert["email"]

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASS)
    server.send_message(msg)
    server.quit()

# ================= ROUTES =================
@app.route("/")
def index():
    page = int(request.args.get("page", 1))
    items = list(symbols.items())
    total_pages = len(items)

    name, _ = items[page - 1]
    data = {name: []}

    company_pages = {
        company.lower(): idx + 1
        for idx, (company, _) in enumerate(items)
    }

    return render_template(
        "index.html",
        data=data,
        page=page,
        total_pages=total_pages,
        company_pages=company_pages,
        year=datetime.now().year
    )

# ================= FINANCIAL DATA =================
@app.route("/real-financial-data")
def real_financial_data():
    page = int(request.args.get("page", 1))
    name = list(symbols.keys())[page - 1]

    try:
        price = get_price(name)
        return jsonify([{
            "sno": 1,
            "name": name,
            "cmp": price,
            "pe": "N/A",
            "marCap": "N/A",
            "divYld": "N/A",
            "npQtr": "N/A",
            "profitVar": "N/A",
            "salesQtr": "N/A",
            "salesVar": "N/A",
            "roce": "N/A",
        }])
    except Exception as e:
        print("Error:", e)
        return jsonify([])

# ================= ALERT =================
@app.route("/set-alert", methods=["POST"])
def set_alert():
    data = request.json
    alerts = load_alerts()

    alerts.append({
        "symbol": data["symbol"],
        "target_price": float(data["target_price"]),
        "condition": data["condition"],
        "email": data["email"]
    })

    save_alerts(alerts)
    return jsonify({"message": "✅ Alert saved"})

def check_alerts():
    alerts = load_alerts()

    for alert in alerts:
        try:
            price = finnhub_client.quote(alert["symbol"])["c"]
            diff = price - alert["target_price"]

            if alert["condition"] == "above" and price >= alert["target_price"]:
                send_email(alert["symbol"], price, alert, diff)

            if alert["condition"] == "below" and price <= alert["target_price"]:
                send_email(alert["symbol"], price, alert, diff)
        except:
            continue

scheduler = BackgroundScheduler()
scheduler.add_job(check_alerts, "interval", minutes=2)
scheduler.start()

# ================= CONTACT =================
@app.route("/contact")
def contact_page():
    return render_template("contact.html")

<<<<<<< HEAD

# ================= SEND CONTACT EMAIL =================

load_dotenv(dotenv_path=".env")


=======
>>>>>>> 15ca33b91de3ef6f9d886185ec76dfa3fcb8adae
@app.route("/send-contact", methods=["POST"])
def send_contact():
    msg = MIMEText(request.form["message"])
    msg["Subject"] = "📩 Contact Message"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER
    msg["Reply-To"] = request.form["email"]

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASS)
    server.send_message(msg)
    server.quit()

    return render_template("contact.html", message="✅ Message sent")


<<<<<<< HEAD
if __name__ == "__main__":
    # app.run(debug=True)
    pass
=======


@app.route("/real-market-overview")
def real_market_overview():
    companies = {
        "Bharti Airtel": "BHARTIARTL.NS",
        "Reliance": "RELIANCE.NS",
        "TCS": "TCS.NS",
        "HDFC Bank": "HDFCBANK.NS",
        "Infosys": "INFY.NS",
        "ICICI Bank": "ICICIBANK.NS",
        "ITC": "ITC.NS",
        "SBI": "SBIN.NS"
    }

    final = []

    for name, symbol in companies.items():
        try:
            profile = finnhub_client.company_profile2(symbol=symbol)
            market_cap = profile.get("marketCapitalization", 0) or 0

            final.append({
                "name": name,
                "value": market_cap
            })
        except:
            continue

    return jsonify(final)




@app.route("/market-overview")
def market_overview():
    data = {}

    indices = {
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "GOLD": "GC=F"
    }

    for name, symbol in indices.items():
        try:
            quote = finnhub_client.quote(symbol)
            price = quote["c"]
            prev = quote["pc"]
            change = round(((price - prev) / prev) * 100, 2)

            data[name] = {
                "price": price,
                "change": change
            }
        except:
            data[name] = {"price": None, "change": None}

    # BTC with caching
    now = datetime.now()
    btc_price = None
    
    if (crypto_cache["timestamp"] and 
        (now - crypto_cache["timestamp"]).seconds < crypto_cache["ttl"] and
        crypto_cache["data"]):
        btc_data = crypto_cache["data"]
        if "bitcoin" in btc_data:
            btc_price = btc_data["bitcoin"]["usd"]
    else:
        try:
            btc_data = cg.get_price(ids="bitcoin", vs_currencies="usd")
            crypto_cache["data"] = btc_data
            crypto_cache["timestamp"] = now
            btc_price = btc_data["bitcoin"]["usd"]
        except:
            if crypto_cache["data"] and "bitcoin" in crypto_cache["data"]:
                btc_price = crypto_cache["data"]["bitcoin"]["usd"]
    
    data["BTC"] = {
        "price": btc_price,
        "change": None
    }

    return jsonify(data)


@app.route("/compare-stocks")
def compare_stocks():
    stocks = {
        "Bharti Airtel": "BHARTIARTL.NS",
        "Reliance": "RELIANCE.NS",
        "TCS": "TCS.NS",
        "HDFC Bank": "HDFCBANK.NS",
        "Infosys": "INFY.NS",
        "ICICI Bank": "ICICIBANK.NS",
        "ITC": "ITC.NS",
        "SBI": "SBIN.NS"
    }

    data = []

    for name, symbol in stocks.items():
        try:
            quote = finnhub_client.quote(symbol)
            profile = finnhub_client.company_profile2(symbol=symbol)

            data.append({
                "name": name,
                "symbol": symbol,
                "cmp": quote["c"],
                "pe": "N/A",
                "marCap": profile.get("marketCapitalization", 0),
                "divYld": "N/A",
                "npQtr": "N/A",
                "profitVar": "N/A",
                "salesQtr": "N/A",
                "salesVar": "N/A",
                "roce": "N/A"
            })
        except:
            continue

    data.sort(key=lambda x: x["cmp"], reverse=True)
    return jsonify({"status": "success", "data": data})



@app.route("/hotchart-data")
def hotchart_data():
    symbols = [
        "BHARTIARTL.NS", "RELIANCE.NS", "TCS.NS",
        "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"
    ]

    data = []

    for sym in symbols:
        try:
            q = finnhub_client.quote(sym)
            change_percent = ((q["c"] - q["pc"]) / q["pc"]) * 100

            data.append({
                "symbol": sym.replace(".NS", ""),
                "current_price": q["c"],
                "change": round(q["c"] - q["pc"], 2),
                "change_percent": round(change_percent, 2),
                "volume": q["v"]
            })
        except:
            continue

    return jsonify({
        "gainers": sorted(data, key=lambda x: x["change_percent"], reverse=True)[:5],
        "losers": sorted(data, key=lambda x: x["change_percent"])[:5],
        "active": sorted(data, key=lambda x: x["volume"], reverse=True)[:5]
    })



@app.route("/footer-data")
def footer_data():
    data = {}
    now = datetime.now()

    # Get crypto data with caching
    crypto = None
    if (crypto_cache["timestamp"] and 
        (now - crypto_cache["timestamp"]).seconds < crypto_cache["ttl"] and
        crypto_cache["data"]):
        crypto = crypto_cache["data"]
    else:
        try:
            crypto = cg.get_price(ids="bitcoin,ethereum", vs_currencies="usd")
            crypto_cache["data"] = crypto
            crypto_cache["timestamp"] = now
        except Exception as e:
            # If API call fails, use cached data
            if crypto_cache["data"]:
                crypto = crypto_cache["data"]
            else:
                # Return empty data but don't crash
                return jsonify({
                    "BTC": {"price": None, "change": None},
                    "ETH": {"price": None, "change": None},
                    "AAPL": {"price": None, "change": None, "is_positive": False}
                })

    if crypto:
        data["BTC"] = {"price": crypto["bitcoin"]["usd"], "change": None}
        data["ETH"] = {"price": crypto["ethereum"]["usd"], "change": None}
    else:
        data["BTC"] = {"price": None, "change": None}
        data["ETH"] = {"price": None, "change": None}

    # Get AAPL data with caching
    aapl = None
    if (stock_cache["AAPL"]["timestamp"] and 
        (now - stock_cache["AAPL"]["timestamp"]).seconds < stock_cache["AAPL"]["ttl"] and
        stock_cache["AAPL"]["data"]):
        aapl = stock_cache["AAPL"]["data"]
    else:
        try:
            aapl = finnhub_client.quote("AAPL")
            stock_cache["AAPL"]["data"] = aapl
            stock_cache["AAPL"]["timestamp"] = now
        except Exception as e:
            if stock_cache["AAPL"]["data"]:
                aapl = stock_cache["AAPL"]["data"]
    
    if aapl:
        data["AAPL"] = {
            "price": aapl["c"],
            "change": round(aapl["c"] - aapl["pc"], 2),
            "is_positive": aapl["c"] >= aapl["pc"]
        }
    else:
        data["AAPL"] = {
            "price": None,
            "change": None,
            "is_positive": False
        }

    return jsonify(data)



# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
>>>>>>> 15ca33b91de3ef6f9d886185ec76dfa3fcb8adae
