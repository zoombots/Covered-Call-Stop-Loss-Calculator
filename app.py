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
strike_pct = st.slider("1-Week Forward Strike Price (% above Monday price):", 0.0, 5.0, 2.0) / 100

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

    stop_loss_drawdown_pct = ((stop_loss_price - entry_price) / entry_price) * 100

    hist = hist.reset_index()
    first_col_name = hist.columns[0]
    if first_col_name != 'Date':
        hist.rename(columns={first_col_name: 'Date'}, inplace=True)

    hist['Week'] = hist['Date'].dt.to_period('W')

    weekly_drawdowns = []
    for week, group in hist.groupby('Week'):
        high = group['Close'].cummax()
        drawdown = (group['Close'] - high) / high
        min_drawdown = drawdown.min()
        weekly_drawdowns.append(min_drawdown)

    max_weekly_drawdown_pct = min(weekly_drawdowns) * 100

    # ✅ Cumulative return block
    weekly_returns = []
    for week, group in hist.groupby('Week'):
        if len(group) < 2:
            continue
        monday_price = group.iloc[0]['Open']
        friday_price = group.iloc[-1]['Close']
        strike_price = monday_price * (1 + strike_pct)
        actual_sell_price = min(friday_price, strike_price)
        weekly_return = (actual_sell_price - monday_price) / monday_price
        weekly_returns.append(weekly_return)

    cumulative_return = np.prod([1 + r for r in weekly_returns]) - 1 if weekly_returns else 0

    # ✅ Output
    st.subheader("Results")
    st.write(f"Entry Price: ${entry_price:.2f}")
    st.write(f"ATR (14-day) over last {weeks_of_history} weeks: {atr:.2f}")
    st.write(f"Recommended Stop-Loss Price (initial): ${stop_loss_price:.2f} ({stop_loss_drawdown_pct:.2f}%)")
    st.write(f"Max Weekly Drawdown over last {weeks_of_history} weeks: {max_weekly_drawdown_pct:.2f}%")
    st.write(f"Cumulative Return over {len(weekly_returns)} weeks (buy Monday open, sell Friday close or strike cap at {strike_pct*100:.2f}%): {cumulative_return*100:.2f}%")

    # ✅ Updated plotting with weekly recalculated stop-loss
    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(hist['Date'], hist['Close'], label='Close Price')
    ax.set_ylabel('Price')
    ax.set_title('Price Chart with Weekly Stop-Loss Trigger Highlight (per-week recalculated)')

    for week, group in hist.groupby('Week'):
        week_max = group['Close'].max()
        week_min = group['Close'].min()

        # ✅ Recalculate stop-loss at start of the week (Monday open)
        monday_open = group.iloc[0]['Open']
        weekly_stop_loss_atr = monday_open - (atr_multiplier * atr)
        weekly_stop_loss_max = monday_open * (1 - max_loss_pct)
        weekly_stop_loss = max(weekly_stop_loss_atr, weekly_stop_loss_max)

        # ✅ Check if stop-loss was triggered that week
        stop_loss_triggered = (group['Close'] < weekly_stop_loss).any()

        if stop_loss_triggered:
            color = 'red'
            linewidth = 2.5
            label = 'Stop-Loss Triggered (week)'
        else:
            color = 'green'
            linewidth = 1
