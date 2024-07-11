import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
import time

# Set page layout to wide
st.set_page_config(layout="wide")
st.markdown('<style>div.block-container{padding-top:1rem; padding-left: -1rem;}</style>',unsafe_allow_html=True)
# Initialize MetaTrader 5
@st.cache_resource
def init_mt5():
    if not mt5.initialize():
        st.error("MetaTrader5 initialization failed")
        mt5.shutdown()
        exit()
    return True

init_mt5()

# Function to get account info
@st.cache_data(ttl=1)
def get_account_info():
    account_info = mt5.account_info()
    if account_info is None:
        st.error("Failed to get account information")
        return None, None
    balance = account_info.balance
    profit = account_info.profit
    return balance, profit

# Function to fetch data from MetaTrader 5
@st.cache_data(ttl=1)
def fetch_data(symbol, timeframe, n=1000):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
    if rates is None:
        st.error(f"Failed to get rates for {symbol} on timeframe {timeframe}")
        return None
    rates_frame = pd.DataFrame(rates)
    rates_frame['time'] = pd.to_datetime(rates_frame['time'], unit='s')
    return rates_frame

# Define timeframe mapping for MetaTrader 5
timeframe_mapping = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1
}

# Function to close open positions
def close_order(position):
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": position.ticket,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask,
        "deviation": 10,
        "magic": 0,
        "comment": "Close trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(request)
    return result

# Function to place orders
def place_order(symbol, lot, order_type, price, stop_loss, take_profit):
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": stop_loss,
        "tp": take_profit,
        "deviation": 10,
        "magic": 0,
        "comment": "Automated trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(request)
    return result

# Fetch account info
balance, profit = get_account_info()
if balance is not None and profit is not None:
    st.header("Super Trend EA")
    st.write(f"Account Balance: ${balance:.2f}")
else:
    st.stop()  # Stop execution if account info is not available

# Sidebar for configuration
st.sidebar.header('Trade Configuration')
symbols = ["XAUUSD","EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"]
symbol = st.sidebar.selectbox("Symbol", symbols)
timeframe = st.sidebar.selectbox("Timeframe", ["M15", "M30", "H1", "H4", "D1", "M5"])
lot_size = st.sidebar.number_input("Lot Size", min_value=0.01, max_value=100.0, value=0.10, step=0.01)
take_profit = st.sidebar.number_input("Take Profit (pips)", min_value=0, max_value=100000, value=3000, step=1)
stop_loss = st.sidebar.number_input("Stop Loss (pips)", min_value=0, max_value=100000, value=3000, step=1)
trade_direction = st.sidebar.selectbox("Trade Direction", ["Both", "Only Buy", "Only Sell"])
num_candles = st.sidebar.number_input("Number of Candles", min_value=50, max_value=5000, value=200, step=25)

# Add buttons for instant BUY and SELL orders
if st.sidebar.button("Instant BUY"):
    open_positions = mt5.positions_get(symbol=symbol)
    if not open_positions:
        df = fetch_data(symbol, timeframe_mapping[timeframe], 1)
        if df is not None and len(df) > 0:
            price = df['close'].iloc[-1]
            sl = price - (stop_loss * 0.01)
            tp = price + (take_profit * 0.01)
            result = place_order(symbol, lot_size, mt5.ORDER_TYPE_BUY, price, sl, tp)
            st.write(f"Placed BUY order at {price}, SL: {sl}, TP: {tp}, Result: {result}")
    else:
        st.write("An open position already exists. No new BUY order placed.")

if st.sidebar.button("Instant SELL"):
    open_positions = mt5.positions_get(symbol=symbol)
    if not open_positions:
        df = fetch_data(symbol, timeframe_mapping[timeframe], 1)
        if df is not None and len(df) > 0:
            price = df['close'].iloc[-1]
            sl = price + (stop_loss * 0.01)
            tp = price - (take_profit * 0.01)
            result = place_order(symbol, lot_size, mt5.ORDER_TYPE_SELL, price, sl, tp)
            st.write(f"Placed SELL order at {price}, SL: {sl}, TP: {tp}, Result: {result}")
    else:
        st.write("An open position already exists. No new SELL order placed.")

if st.sidebar.button("Close All"):
    open_positions = mt5.positions_get(symbol=symbol)
    if open_positions:
        for pos in open_positions:
            close_order(pos)
        st.write("Closed all open positions.")
    else:
        st.write("No open positions to close.")

# Define parameters directly in the code
atr_period = 14
supertrend_period = 10
multiplier = 3.0
chart_width = 1300
chart_height = 800

# Placeholder for dynamic content
account_info_placeholder = st.empty()
chart_placeholder = st.empty()

# Calculate ATR manually
def calculate_atr(df, period):
    df['tr'] = np.maximum((df['high'] - df['low']),
                          np.maximum(abs(df['high'] - df['close'].shift(1)),
                                     abs(df['low'] - df['close'].shift(1))))
    df['atr'] = df['tr'].rolling(window=period, min_periods=1).mean()
    return df

# Calculate SuperTrend
def supertrend(df, period=10, multiplier=3):
    df = calculate_atr(df, period)
    df['hl2'] = (df['high'] + df['low']) / 2
    df['upperband'] = df['hl2'] + (multiplier * df['atr'])
    df['lowerband'] = df['hl2'] - (multiplier * df['atr'])
    
    df['SuperTrend'] = np.nan
    df['Direction'] = np.nan
    df['Buy/Sell'] = ''
    
    for i in range(1, len(df)):
        if df.loc[i-1, 'close'] > df.loc[i-1, 'SuperTrend']:
            df.loc[i, 'SuperTrend'] = max(df.loc[i, 'lowerband'], df.loc[i-1, 'SuperTrend'])
            df.loc[i, 'Direction'] = 'up'
            if df.loc[i, 'close'] < df.loc[i, 'SuperTrend']:
                df.loc[i, 'Buy/Sell'] = 'SELL'
        else:
            df.loc[i, 'SuperTrend'] = min(df.loc[i, 'upperband'], df.loc[i-1, 'SuperTrend'])
            df.loc[i, 'Direction'] = 'down'
            if df.loc[i, 'close'] > df.loc[i, 'SuperTrend']:
                df.loc[i, 'Buy/Sell'] = 'BUY'
    
    df['SuperTrend'].fillna(df['lowerband'], inplace=True)
    
    return df

# Function to plot chart
def plot_chart(df):
    fig = go.Figure(data=[go.Candlestick(x=df['time'],
                                         open=df['open'],
                                         high=df['high'],
                                         low=df['low'],
                                         close=df['close'],
                                         name='Candlesticks',
                                         increasing_line_color='green',
                                         decreasing_line_color='red')])

    # Separate the SuperTrend into uptrend and downtrend
    df['SuperTrend_Up'] = np.where(df['Direction'] == 'up', df['SuperTrend'], np.nan)
    df['SuperTrend_Down'] = np.where(df['Direction'] == 'down', df['SuperTrend'], np.nan)

    fig.add_trace(go.Scatter(x=df['time'], y=df['SuperTrend_Up'], mode='lines', name='SuperTrend Up', line=dict(color='green')))
    fig.add_trace(go.Scatter(x=df['time'], y=df['SuperTrend_Down'], mode='lines', name='SuperTrend Down', line=dict(color='red')))

    # Add Buy/Sell markers
    for i in range(1, len(df)):
        if df['Buy/Sell'][i] == 'BUY':
            fig.add_annotation(x=df['time'][i], y=df['SuperTrend'][i],
                               text="BUY", showarrow=True, arrowhead=1, ax=0, ay=-40, bgcolor="green", font=dict(color="white"))
        elif df['Buy/Sell'][i] == 'SELL':
            fig.add_annotation(x=df['time'][i], y=df['SuperTrend'][i],
                               text="SELL", showarrow=True, arrowhead=1, ax=0, ay=40, bgcolor="red", font=dict(color="white"))

    fig.update_layout(title=f'Forex Data with SuperTrend - {symbol}',
                      yaxis_title='Price',
                      xaxis_title='Time',
                      width=chart_width,
                      height=chart_height,
                      xaxis_rangeslider_visible=False)
    
    chart_placeholder.plotly_chart(fig)

# Main loop to update the chart and account info every second
def update_dashboard():
    while True:
        balance, profit = get_account_info()
        if balance is not None and profit is not None:
            account_info_placeholder.write(f"Account Balance: ${balance:.2f}")
            account_info_placeholder.write(f"Current Profit: ${profit:.2f}")
        else:
            account_info_placeholder.write("Failed to retrieve account information")

        df = fetch_data(symbol, timeframe_mapping[timeframe], num_candles)

        if df is not None:
            df = supertrend(df, supertrend_period, multiplier)
            plot_chart(df)

            # Check and execute trades based on the conditions for the previous closed candle
            open_positions = mt5.positions_get(symbol=symbol)
            if open_positions:
                for pos in open_positions:
                    if pos.type == mt5.ORDER_TYPE_BUY and df['Buy/Sell'].iloc[-2] == 'SELL':
                        close_order(pos)
                        st.write(f"Closed BUY order at {pos.price_open}")
                    elif pos.type == mt5.ORDER_TYPE_SELL and df['Buy/Sell'].iloc[-2] == 'BUY':
                        close_order(pos)
                        st.write(f"Closed SELL order at {pos.price_open}")
            else:
                if df['Buy/Sell'].iloc[-2] == 'BUY' and (trade_direction == "Both" or trade_direction == "Only Buy"):
                    price = df['close'].iloc[-1]
                    sl = price - (stop_loss * 0.01)  # Adjusted pip value
                    tp = price + (take_profit * 0.01)  # Adjusted pip value
                    result = place_order(symbol, lot_size, mt5.ORDER_TYPE_BUY, price, sl, tp)
                    st.write(f"Placed BUY order at {price}, SL: {sl}, TP: {tp}, Result: {result}")
                elif df['Buy/Sell'].iloc[-2] == 'SELL' and (trade_direction == "Both" or trade_direction == "Only Sell"):
                    price = df['close'].iloc[-1]
                    sl = price + (stop_loss * 0.01)  # Adjusted pip value
                    tp = price - (take_profit * 0.01)  # Adjusted pip value
                    result = place_order(symbol, lot_size, mt5.ORDER_TYPE_SELL, price, sl, tp)
                    st.write(f"Placed SELL order at {price}, SL: {sl}, TP: {tp}, Result: {result}")

        time.sleep(1)  # Update every 1 second

update_dashboard()

# Shutdown MetaTrader 5
mt5.shutdown()
