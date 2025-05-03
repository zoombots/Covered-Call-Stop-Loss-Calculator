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
        hist.rename(columns={hist.columns[0]: 'Date'}, inplace=True)  # ensure 'Date' column

        hist['Week'] = hist['Date'].dt.to_period('W')
        
        weekly_drawdowns = []
        
        for week, group in hist.groupby('Week'):
            high = group['Close'].cummax()
            drawdown = (group['Close'] - high) / high
            min_drawdown = drawdown.min()
            weekly_drawdowns.append(min_drawdown)
        
        max_weekly_drawdown_pct = min(weekly_drawdowns) * 100  # negative %

        st.subheader("Results")
        st.write(f"Entry Price: ${entry_price:.2f}")
        st.write(f"ATR (14-day) over last {weeks_of_history} weeks: {atr:.2f}")

        # ✅ Updated display:
        st.write(f"Recommended Stop-Loss Price: ${stop_loss_price:.2f} ({stop_loss_drawdown_pct:.2f}%)")
        st.write(f"Max Weekly Drawdown over last {weeks_of_history} weeks: {max_weekly_drawdown_pct:.2f}%")

 # Optional: plot price + weekly drawdown marker with color-coded stop-loss trigger
fig, ax = plt.subplots(figsize=(10,4))
ax.plot(hist['Date'], hist['Close'], label='Close Price')
ax.set_ylabel('Price')
ax.set_title('Price Chart with Weekly Max Drawdown and Stop-Loss Trigger')

for week, group in hist.groupby('Week'):
    week_max = group['Close'].max()
    week_min = group['Close'].min()

    # Color code: red if stop-loss would have triggered
    if week_min < stop_loss_price:
        color = 'red'
        linewidth = 2.5  # make it thicker for emphasis
    else:
        color = 'green'
        linewidth = 1.5

    ax.vlines(group['Date'].iloc[0], week_min, week_max, color=color, alpha=0.8, linewidth=linewidth)

# Add horizontal line for stop-loss
ax.axhline(stop_loss_price, color='purple', linestyle='--', label='Stop-Loss Price')

ax.legend()
st.pyplot(fig)

