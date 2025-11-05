# config.py
APP_ID = "6UI8IGJH2H-100"  # your app id with suffix (-100)
SECRET_KEY = "S7QBNQHVZR"   # your Fyers secret key
REDIRECT_URI = "http://127.0.0.1:5000"
RESPONSE_TYPE = "code"
GRANT_TYPE = "authorization_code"

# Add the strike symbols you want to fetch LTP for 👇
# Example: NIFTY24NOV24500CE, NIFTY24NOV24500PE, etc.
STRIKE_SYMBOLS = [
    "NSE:NIFTY11NOV25700CE",
    "NSE:NIFTY11NOV25750CE",
    "NSE:NIFTY11NOV23300PE",
    "NSE:NIFTY11NOV23350PE"
]
