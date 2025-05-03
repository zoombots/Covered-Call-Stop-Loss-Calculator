import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt

st.title("Covered Call Stop-Loss Calculator with Weekly Max Drawdown")

# Inputs
symbol = st.text_input("Enter Stock Symbol:", "TSLA")
max_loss_pct = st.slider("Max % Loss Allowed:", 5, 20, 10) / 100
atr_multiplier = st.slider("ATR Multiplier:", 1, 3, 2)
weeks_of_history = st.slider("Number of Weeks for ATR Calculation:", 4, 52, 12)

if st.button("Calculate"):
    days_of_history = weeks_of_history * 5  # ~5 trading days per week
    
    stock = yf.Ticker(symbol)
    hist = stock.history(period=f"{days_of_history}d")

    if len(hist) < 14:
        st.error(f"Not enough historical data ({len(hist)} days retrieved). Try increasing weeks or using a different stock.")
    else:
        # ATR calculation
        high_low = hist['High'] - hist['Low']
        high_close = np.abs(hist['High'] - hist['Close'].shift())
        low_close = np.abs(hist['Low'] - hist['Close'].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)

        atr = true_range.rolling(window=14).mean().iloc[-1]

        entry_price = stock.history(period="1d")['Close'][-1]
        stop_loss_atr = entry_price - (atr_multiplier * atr)
        stop_loss_max = entry_price * (1 - max_loss_pct)
        stop_loss_price = max(stop_loss_atr, stop_loss_max)

        # Calculate % drawdown of stop-loss from entry
        stop_loss_drawdown_pct = ((stop_loss_price - entry_price) / entry_price) * 100  # should be negative

        # 🟢 Weekly Max Drawdown Calculation
        hist = hist.reset_index()

        # ✅ Ensure first column is named 'Date' no matter what
        first_col_name = hist.columns[0]
        if first_col_name != 'Date':
            hist.rename(columns={first_col_name: '
