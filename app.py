import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import datetime

st.title("Covered Call Analysis | Risk & Reward Calculator")
st.markdown("""
### 📘 Covered Call Risk & Reward Calculator – User Guide - This tool simulates the **risk-return profile of a weekly covered call strategy**, including dynamic stop-losses, capped gains through call strikes, and real-world premium income. 
---

---

#### 🧭 How to Use the Tool

1. **Enter a stock symbol** (e.g., `TSLA`)
2. Adjust the following settings:
   - **Max % Loss Allowed** – sets a floor to limit weekly losses.
   - **ATR Multiplier** – adjusts stop-loss based on recent volatility.
   - **Weeks of History** – defines how much historical data is analyzed.
   - **1-Week Forward Strike Price (% above Monday)** – caps upside using covered calls.

---

#### 🧠 What It Does

- Dynamically calculates weekly **stop-loss levels**.
- Simulates **buy on Monday, sell on Friday (or earlier)** trades.
- Caps upside gains using the **closest out-of-the-money (OTM) call option**.
- Pulls **real options chain data** and multiplies the premium by selected weeks.
- Tracks **weekly returns, cumulative gains**, and **premium income**.
- Displays:
  - Final and annualized returns (with and without premiums).
  - Weekly trade log with gain/loss annotations.
  - A chart with color-coded weekly outcomes and stop-loss triggers.

---

#### 📊 Chart Key

- 🟩 **Green** = Week closed with gain, no stop-loss
- 🟧 **Orange** = Loss week, no stop-loss triggered
- 🟥 **Red** = Stop-loss was triggered during the week  
- 🧠 **Legend includes a success ratio:** Green/Red weeks

---

This is a practical tool to evaluate **income-focused strategies** and optimize covered call entries with downside protection. Data is sourced from Yahoo! Finance's publicly available APIs. Historical options data calculations are based on the most recent options data available and should not be considered as a reliable backtesting tool. Many variables can affect the stock options' Implied Volatility, such as upcoming earnings, mergers and wider market volatility. As such, please remember that current options premiums may not reflect historical or future values.  

""")


# Inputs
symbol = st.text_input("Enter Stock Symbol:", "TSLA")
max_loss_pct = st.slider("Max % Loss Allowed:", 5, 20, 10) / 100
atr_multiplier = st.slider("ATR Multiplier:", 1, 3, 2)
weeks_of_history = st.slider("Weeks of history for ATR Calculation and historical data:", 4, 52, 12)
strike_pct = st.slider("1-Week Forward Strike Price (% above Monday price):", 0.0, 5.0, 2.0) / 100

days_of_history = weeks_of_history * 5  # ~5 trading days per week

stock = yf.Ticker(symbol)
hist = stock.history(period=f"{days_of_history}d")

if len(hist) < 14:
    st.error(
        f"Not enough historical data ({len(hist)} days retrieved). "
        "Try increasing weeks or using a different stock."
    )
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

    hist['Date'] = pd.to_datetime(hist['Date'])
    hist['Week'] = hist['Date'].dt.to_period('W')

    weekly_drawdowns = []
    for week, group in hist.groupby('Week'):
        high = group['Close'].cummax()
        drawdown = (group['Close'] - high) / high
        min_drawdown = drawdown.min()
        weekly_drawdowns.append(min_drawdown)

    max_weekly_drawdown_pct = min(weekly_drawdowns) * 100

    # ✅ Retrieve options chain and find closest strike for info only
    expirations = stock.options
    today = datetime.datetime.now().date()
    valid_expirations = [exp for exp in expirations if (pd.to_datetime(exp).date() - today).days >= 5]

    if not valid_expirations:
        st.error("No expiration dates at least 5 days out available!")
        bid_price = 0
        strike_price_opt = None
    else:
        chosen_exp = valid_expirations[0]
        opt_chain = stock.option_chain(chosen_exp)
        calls = opt_chain.calls

        target_strike_price = entry_price * (1 + strike_pct)

        # Filter only OTM calls (strikes >= target strike)
        otm_calls = calls[calls['strike'] >= target_strike_price]
    
    if not otm_calls.empty:
        # Get the closest OTM strike above target
        closest_call = otm_calls.sort_values('strike').iloc[0]
        strike_price_opt = closest_call['strike']
        bid_price = closest_call['bid']
    else:
        # Fallback if no OTM strikes found
        closest_call = calls.sort_values('strike').iloc[-1]
        strike_price_opt = closest_call['strike']
        bid_price = closest_call['bid']
        st.warning("No OTM call found above target. Using highest available strike as fallback.")


        strike_price_opt = closest_call['strike']
        bid_price = closest_call['bid']

    # Total premium & annualized return (info only)
    total_premium = bid_price * weeks_of_history
    annualized_return = (total_premium / entry_price) * (52 / weeks_of_history) * 100 if entry_price != 0 else 0

    # ✅ Weekly returns (always use strike_pct cap, not option strike)
    capital = 1  # normalized starting capital = $1
    weekly_returns = []

    for week, group in hist.groupby('Week'):
        if len(group) < 2:
            continue

        monday_price = group.iloc[0]['Open']
        friday_price = group.iloc[-1]['Close']

        weekly_stop_loss_atr = monday_price - (atr_multiplier * atr)
        weekly_stop_loss_max = monday_price * (1 - max_loss_pct)
        weekly_stop_loss = max(weekly_stop_loss_atr, weekly_stop_loss_max)

        strike_price_week = monday_price * (1 + strike_pct)  # always use % cap

        stop_loss_hit = group[group['Close'] <= weekly_stop_loss]

        if not stop_loss_hit.empty:
            sell_price = weekly_stop_loss
            exit_reason = f"Stop-loss hit on {stop_loss_hit.iloc[0]['Date'].date()}"
        else:
            sell_price = min(friday_price, strike_price_week)
            exit_reason = "Held to Friday or capped"

        weekly_return = (sell_price - monday_price) / monday_price
        weekly_dollar_return = capital * weekly_return
        capital *= (1 + weekly_return)

        weekly_returns.append({
            'week': str(week),
            'monday_price': monday_price,
            'friday_price': friday_price,
            'sell_price': sell_price,
            'weekly_return_pct': weekly_return * 100,
            'weekly_dollar_return': weekly_dollar_return,
            'capital_after_week': capital,
            'exit_reason': exit_reason
        })

    cumulative_return = capital - 1

    # ✅ Output
    st.subheader("Results")
    st.write(f"Entry Price: ${entry_price:.2f}")
    st.write(f"ATR (14-day) over last {weeks_of_history} weeks: {atr:.2f}")
    st.write(f"Recommended Stop-Loss Price (initial): ${stop_loss_price:.2f} ({stop_loss_drawdown_pct:.2f}%)")
    st.write(f"Max Weekly Drawdown over last {weeks_of_history} weeks: {max_weekly_drawdown_pct:.2f}%")

    if strike_price_opt is not None:
        st.write(f"Closest Call Option Expiration: {chosen_exp}")
        st.write(f"Target Strike Price (slider): {target_strike_price:.2f}")
        st.write(f"Closest Available OTM Call Option Strike: {strike_price_opt:.2f}")
        st.write(f"Option Bid Price: ${bid_price:.2f}")
        st.write(f"Projected Total Premium over {weeks_of_history} weeks: ${total_premium:.2f}")
        st.write(f"Annualized Return from Premium: {annualized_return:.2f}%")
    else:
        st.write("No valid call option found for target strike.")

    st.write(f"Cumulative Return over {len(weekly_returns)} weeks (stop-loss exit, capped at {strike_pct*100:.2f}%): {cumulative_return*100:.2f}%")
    
    final_capital_pct = capital * 100
    final_capital_value = capital * entry_price
    combined_capital_value = final_capital_value + total_premium
    
    st.write(f"Final Capital: {final_capital_pct:.2f}% of starting capital")
    st.write(f"Final Capital (dollar equivalent): ${final_capital_value:.2f}")
    st.write(f"Combined Final Capital (incl. total premium): ${combined_capital_value:.2f}")
    
    num_weeks = len(weekly_returns)
    years = num_weeks / 52 if num_weeks > 0 else 1
    
    if capital > 0 and years > 0:
        annualized_stock_return = capital ** (1 / years) - 1
    else:
        annualized_stock_return = 0
    
    if combined_capital_value > 0 and entry_price > 0 and years > 0:
        annualized_combined_return = (combined_capital_value / entry_price) ** (1 / years) - 1
    else:
        annualized_combined_return = 0
    
    st.write(f"Annualized Return (stock only): {annualized_stock_return * 100:.2f}%")
    st.write(f"Annualized Return (incl. premium): {annualized_combined_return * 100:.2f}%")




    st.dataframe(pd.DataFrame(weekly_returns))

    # ✅ Plot
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(hist['Date'], hist['Close'], label='Close Price')
    ax.set_ylabel('Price')
    ax.set_title('Price Chart with Weekly Stop-Loss Trigger Highlight (per-week recalculated)')

    # ✅ Initialize counters
    green_weeks = 0
    red_weeks = 0

    for week, group in hist.groupby('Week'):
        if group.empty or len(group) < 2:
            continue
        
        week_max = group['Close'].max()
        week_min = group['Close'].min()
    
        monday_open = group.iloc[0]['Open']
        friday_close = group.iloc[-1]['Close']
    
        weekly_stop_loss_atr = monday_open - (atr_multiplier * atr)
        weekly_stop_loss_max = monday_open * (1 - max_loss_pct)
        weekly_stop_loss = max(weekly_stop_loss_atr, weekly_stop_loss_max)
    
        stop_loss_triggered = (group['Close'] < weekly_stop_loss).any()
    
        if stop_loss_triggered:
            color = 'red'
            linewidth = 2.5
            label = 'Stop-Loss Triggered (week)'
            red_weeks += 1
            weekly_return_pct = ((weekly_stop_loss - monday_open) / monday_open) * 100  # ✅ Define it here
        else:
            weekly_return_pct = ((friday_close - monday_open) / monday_open) * 100
            if weekly_return_pct >= 0:
                color = 'green'
                label = 'Gain Week (no stop-loss)'
                green_weeks += 1
            else:
                color = 'orange'
                label = 'Loss Week (no stop-loss)'
            linewidth = 1.5

    
        if ax.get_legend_handles_labels()[1].count(label) == 0:
            ax.vlines(group['Date'].iloc[0], week_min, week_max, color=color, alpha=0.8, linewidth=linewidth, label=label)
        else:
            ax.vlines(group['Date'].iloc[0], week_min, week_max, color=color, alpha=0.8, linewidth=linewidth)
    
        # Weekly return annotation
        try:
            label_pos = week_max * 1.01 if weekly_return_pct >= 0 else week_min * 0.99
            if pd.notna(label_pos) and np.isfinite(label_pos):
                ax.annotate(
                    f"{weekly_return_pct:+.1f}%", 
                    xy=(group['Date'].iloc[0], label_pos),
                    ha='center', 
                    va='bottom' if weekly_return_pct >= 0 else 'top',
                    fontsize=8, 
                    color=color,
                    rotation=0
                )
        except Exception as e:
            st.warning(f"Annotation error on week {week}: {e}")
        from matplotlib.lines import Line2D  # Add this at the top of your file if not already
        
        # After the loop, before ax.legend()
        total_tracked = green_weeks + red_weeks
        if total_tracked > 0:
            success_ratio = green_weeks / total_tracked
            ratio_label = f"Green/Red Weeks: {green_weeks}/{red_weeks} ({success_ratio:.0%} success)"
            dummy_line = Line2D([0], [0], color='white', label=ratio_label)  # Invisible line for legend
            handles, labels = ax.get_legend_handles_labels()
            handles.append(dummy_line)
            labels.append(ratio_label)
            ax.legend(handles=handles, labels=labels)
        else:
            ax.legend()

    st.pyplot(fig)

