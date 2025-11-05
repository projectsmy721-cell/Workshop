import streamlit as st
from fyers_apiv3 import fyersModel
import time
import datetime
import webbrowser
import threading
from flask import Flask, request
from config import APP_ID, SECRET_KEY, REDIRECT_URI, RESPONSE_TYPE, GRANT_TYPE

# Page config
st.set_page_config(
    page_title="Iron Condor Tracker",
    page_icon="📊",
    layout="wide"
)

# Flask app for auth callback
flask_app = Flask(__name__)
auth_code_received = None

@flask_app.route('/')
def receive_auth_code():
    """Receive the authorization code after login."""
    global auth_code_received
    auth_code_received = request.args.get('auth_code')
    if auth_code_received:
        return "✅ Authorization successful! You can close this tab and return to Streamlit."
    return "⚠️ No auth code received."

def run_flask():
    """Run Flask server in background."""
    flask_app.run(port=5000, use_reloader=False)

def start_flask_server():
    """Start Flask server if not already running."""
    if 'flask_started' not in st.session_state:
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        st.session_state.flask_started = True
        time.sleep(1)  # Give server time to start

def auto_authenticate():
    """Automatically authenticate with Fyers."""
    global auth_code_received
    
    # Start Flask server
    start_flask_server()
    
    # Generate auth URL
    session = fyersModel.SessionModel(
        client_id=APP_ID,
        secret_key=SECRET_KEY,
        redirect_uri=REDIRECT_URI,
        response_type=RESPONSE_TYPE,
        grant_type=GRANT_TYPE
    )
    
    auth_url = session.generate_authcode()
    
    # Open browser automatically
    webbrowser.open(auth_url)
    
    # Wait for auth code
    with st.spinner("⏳ Waiting for Fyers login... (Browser window opened)"):
        timeout = 120  # 2 minutes timeout
        start_time = time.time()
        
        while auth_code_received is None:
            time.sleep(1)
            if time.time() - start_time > timeout:
                return None, "⏱️ Authentication timeout. Please try again."
    
    # Generate access token
    session.set_token(auth_code_received)
    response = session.generate_token()
    
    if "access_token" in response:
        return response["access_token"], None
    else:
        return None, "❌ Token generation failed"

# Session state initialization
if 'access_token' not in st.session_state:
    st.session_state.access_token = None
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Symbol configuration
SYMBOLS = {
    "NIFTY": {"lot_size": 25, "prefix": "NSE:NIFTY"},
    "BANKNIFTY": {"lot_size": 15, "prefix": "NSE:BANKNIFTY"},
    "FINNIFTY": {"lot_size": 25, "prefix": "NSE:FINNIFTY"}
}

def format_symbol(base, expiry, strike, option_type):
    """Generate Fyers option symbol format"""
    year = expiry[-2:]
    month = expiry[2:5].upper()
    day = expiry[:2]
    
    # Standard weekly format: NIFTY25N1125650CE
    month_code = month[0]
    symbol = f"{base}{year}{month_code}{day}{strike}{option_type}"
    return symbol

def get_ltp_batch(symbols, access_token):
    """Fetch LTP for multiple symbols"""
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=access_token, log_path="")
    
    data = {"symbols": ",".join(symbols)}
    response = fyers.quotes(data)
    
    ltp_dict = {}
    if response.get("s") == "ok":
        for quote in response.get("d", []):
            symbol = quote.get("n", "")
            v = quote.get("v", {})
            ltp = v.get("lp") or v.get("ltp") or 0
            ltp_dict[symbol] = float(ltp) if ltp else 0.0
    
    return ltp_dict

def calculate_iron_condor(call_sell_ltp, call_buy_ltp, put_sell_ltp, put_buy_ltp, lot_size, min_qty):
    """Calculate Iron Condor metrics"""
    # Call side
    call_premium_diff = call_sell_ltp - call_buy_ltp
    call_max_profit = call_premium_diff * lot_size * min_qty
    call_sl = call_max_profit * 3
    call_target = call_max_profit * 1.5
    
    # Put side
    put_premium_diff = put_sell_ltp - put_buy_ltp
    put_max_profit = put_premium_diff * lot_size * min_qty
    put_sl = put_max_profit * 3
    put_target = put_max_profit * 1.5
    
    # Combined
    total_max_profit = call_max_profit + put_max_profit
    avg_premium = (call_premium_diff + put_premium_diff) / 2
    
    return {
        "call_premium_diff": call_premium_diff,
        "call_max_profit": call_max_profit,
        "call_sl": call_sl,
        "call_target": call_target,
        "put_premium_diff": put_premium_diff,
        "put_max_profit": put_max_profit,
        "put_sl": put_sl,
        "put_target": put_target,
        "total_max_profit": total_max_profit,
        "avg_premium": avg_premium
    }

def authentication_page():
    """Automated Fyers authentication"""
    st.title("🔐 Fyers Authentication")
    st.info("Click below to authenticate. Your browser will open automatically.")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("🚀 Login with Fyers", type="primary"):
            token, error = auto_authenticate()
            
            if token:
                st.session_state.access_token = token
                st.session_state.authenticated = True
                st.success("✅ Authentication successful!")
                time.sleep(1)
                st.rerun()
            else:
                st.error(error or "Authentication failed")
    
    with col2:
        st.markdown("""
        **How it works:**
        1. Click the button above
        2. Browser opens Fyers login page
        3. Login with your credentials
        4. Automatically redirected back
        5. Start tracking!
        
        *Make sure popups are enabled for this site*
        """)

def main_app():
    """Main Iron Condor tracking interface"""
    st.title("📊 Real-Time Iron Condor Position Tracker")
    
    # Sidebar inputs
    with st.sidebar:
        st.header("⚙️ Position Setup")
        
        # Symbol selection
        selected_symbol = st.selectbox("Select Symbol", list(SYMBOLS.keys()))
        lot_size = SYMBOLS[selected_symbol]["lot_size"]
        
        # Expiry date
        expiry_date = st.text_input("Expiry Date (DDMMMYY)", value="11NOV25")
        
        st.divider()
        
        # Quantity inputs
        st.subheader("📦 Quantity")
        num_lots = st.number_input("Number of Lots", min_value=1, value=1, step=1)
        min_qty = st.number_input("Minimum Quantity", min_value=1, value=25, step=1)
        
        st.divider()
        
        # Call side strikes
        st.subheader("📞 Call Side")
        call_sell_strike = st.number_input("Call Sell Strike", min_value=0, value=25700, step=50)
        call_buy_strike = st.number_input("Call Buy Strike", min_value=0, value=25750, step=50)
        
        st.divider()
        
        # Put side strikes
        st.subheader("📉 Put Side")
        put_sell_strike = st.number_input("Put Sell Strike", min_value=0, value=25100, step=50)
        put_buy_strike = st.number_input("Put Buy Strike", min_value=0, value=25050, step=50)
        
        st.divider()
        
        # Refresh rate
        refresh_rate = st.slider("Refresh Rate (seconds)", 1, 10, 3)
        
        # Start tracking button
        start_tracking = st.button("🚀 Start Live Tracking", type="primary")
        
        if st.button("🔓 Logout"):
            st.session_state.authenticated = False
            st.session_state.access_token = None
            st.rerun()
    
    # Main content area
    if start_tracking or 'tracking_active' in st.session_state:
        st.session_state.tracking_active = True
        
        # Generate symbols
        base_symbol = SYMBOLS[selected_symbol]["prefix"]
        
        call_sell_symbol = format_symbol(base_symbol, expiry_date, call_sell_strike, "CE")
        call_buy_symbol = format_symbol(base_symbol, expiry_date, call_buy_strike, "CE")
        put_sell_symbol = format_symbol(base_symbol, expiry_date, put_sell_strike, "PE")
        put_buy_symbol = format_symbol(base_symbol, expiry_date, put_buy_strike, "PE")
        
        symbols = [call_sell_symbol, call_buy_symbol, put_sell_symbol, put_buy_symbol]
        
        # Create placeholders for live updates
        time_placeholder = st.empty()
        metrics_container = st.container()
        call_container = st.container()
        put_container = st.container()
        summary_container = st.container()
        
        # Add stop button
        stop_col1, stop_col2 = st.columns([1, 5])
        with stop_col1:
            if st.button("⏹️ Stop Tracking"):
                st.session_state.tracking_active = False
                st.rerun()
        
        while st.session_state.tracking_active:
            # Fetch LTPs
            ltp_data = get_ltp_batch(symbols, st.session_state.access_token)
            
            if ltp_data:
                call_sell_ltp = ltp_data.get(call_sell_symbol, 0)
                call_buy_ltp = ltp_data.get(call_buy_symbol, 0)
                put_sell_ltp = ltp_data.get(put_sell_symbol, 0)
                put_buy_ltp = ltp_data.get(put_buy_symbol, 0)
                
                # Calculate metrics
                metrics = calculate_iron_condor(
                    call_sell_ltp, call_buy_ltp, 
                    put_sell_ltp, put_buy_ltp,
                    lot_size, min_qty
                )
                
                # Display time
                current_time = datetime.datetime.now().strftime("%H:%M:%S")
                time_placeholder.markdown(f"### 🕐 Last Update: {current_time}")
                
                # Display metrics
                with metrics_container:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("💰 Total Max Profit", f"₹{metrics['total_max_profit']:.2f}")
                    with col2:
                        st.metric("📊 Avg Premium", f"₹{metrics['avg_premium']:.2f}")
                    with col3:
                        st.metric("🎯 Combined Target", f"₹{metrics['call_target'] + metrics['put_target']:.2f}")
                    with col4:
                        st.metric("🛑 Combined SL", f"₹{metrics['call_sl'] + metrics['put_sl']:.2f}")
                
                # Call side details
                with call_container:
                    st.subheader("📞 Call Side")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(f"Sell {call_sell_strike}", f"₹{call_sell_ltp:.2f}")
                    with col2:
                        st.metric(f"Buy {call_buy_strike}", f"₹{call_buy_ltp:.2f}")
                    with col3:
                        delta_color = "normal" if metrics['call_premium_diff'] > 0 else "inverse"
                        st.metric("Premium Diff", f"₹{metrics['call_premium_diff']:.2f}", delta_color=delta_color)
                    with col4:
                        st.metric("Max Profit", f"₹{metrics['call_max_profit']:.2f}")
                    
                    col5, col6 = st.columns(2)
                    with col5:
                        st.metric("🎯 Target", f"₹{metrics['call_target']:.2f}")
                    with col6:
                        st.metric("🛑 Stop Loss", f"₹{metrics['call_sl']:.2f}")
                
                # Put side details
                with put_container:
                    st.subheader("📉 Put Side")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(f"Sell {put_sell_strike}", f"₹{put_sell_ltp:.2f}")
                    with col2:
                        st.metric(f"Buy {put_buy_strike}", f"₹{put_buy_ltp:.2f}")
                    with col3:
                        delta_color = "normal" if metrics['put_premium_diff'] > 0 else "inverse"
                        st.metric("Premium Diff", f"₹{metrics['put_premium_diff']:.2f}", delta_color=delta_color)
                    with col4:
                        st.metric("Max Profit", f"₹{metrics['put_max_profit']:.2f}")
                    
                    col5, col6 = st.columns(2)
                    with col5:
                        st.metric("🎯 Target", f"₹{metrics['put_target']:.2f}")
                    with col6:
                        st.metric("🛑 Stop Loss", f"₹{metrics['put_sl']:.2f}")
                
                # Summary table
                with summary_container:
                    st.subheader("📋 Position Summary")
                    summary_data = {
                        "Metric": ["Total Max Profit", "Call Max Profit", "Put Max Profit", "Avg Premium", "Risk:Reward"],
                        "Value": [
                            f"₹{metrics['total_max_profit']:.2f}",
                            f"₹{metrics['call_max_profit']:.2f}",
                            f"₹{metrics['put_max_profit']:.2f}",
                            f"₹{metrics['avg_premium']:.2f}",
                            "1:1.5 (Target) / 1:3 (SL)"
                        ]
                    }
                    st.table(summary_data)
            
            else:
                st.error("❌ Could not fetch LTP data. Check symbol formats or market hours.")
                st.session_state.tracking_active = False
                break
            
            time.sleep(refresh_rate)
            st.rerun()
    else:
        st.info("👈 Configure your Iron Condor position in the sidebar and click 'Start Live Tracking'")
        
        # Display example
        st.subheader("📖 How to Use")
        st.markdown("""
        1. **Select Symbol**: Choose NIFTY, BANKNIFTY, or FINNIFTY
        2. **Enter Expiry**: Format DDMMMYY (e.g., 11NOV25)
        3. **Set Strikes**: Enter your Iron Condor strikes
        4. **Configure Quantity**: Number of lots and minimum quantity
        5. **Start Tracking**: Click the button to begin live monitoring
        
        **Iron Condor Setup:**
        - **Call Spread**: Sell lower strike, Buy higher strike
        - **Put Spread**: Sell higher strike, Buy lower strike
        - Max profit = Premium collected on both sides
        """)

# Main app logic
if not st.session_state.authenticated:
    authentication_page()
else:
    main_app()