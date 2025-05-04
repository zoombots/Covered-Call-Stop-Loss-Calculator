import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import datetime

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
    st.error(f"Not enough
