"""
generate_test_data.py
-----------------------
Creates a synthetic daily OHLCV CSV in NSE-Bhavcopy-like column names,
with a deliberate regime shift (uptrend for ~26 weeks, then a downtrend
for ~20 weeks, including a couple of Upthrust-style failed rallies) so
the pipeline can be smoke-tested end-to-end before real NSE data is
plugged in.

This is NOT meant to validate the strategy's edge -- it's a plumbing
test only: does the CSV load, resample, classify, and scan without
errors, and do the outputs look sane.
"""

import numpy as np
import pandas as pd

np.random.seed(7)

start_price = 22000.0  # Nifty-ish level
n_days = 330  # ~65 weeks of trading days

dates = pd.bdate_range("2024-01-01", periods=n_days)

# Phase A: uptrend (first ~130 trading days, ~26 weeks)
up_days = 130
up_rets = np.random.normal(0.0009, 0.008, up_days)

# Phase B: downtrend with two upthrust-style bear rallies (~200 days, ~39 weeks)
down_days = n_days - up_days
down_rets = np.random.normal(-0.0012, 0.011, down_days)
# inject two sharp relief rallies that partially retrace, then fail
down_rets[40:45] += 0.012   # rally leg 1
down_rets[46:50] -= 0.018   # failure / SOW leg 1
down_rets[100:105] += 0.010  # rally leg 2
down_rets[106:110] -= 0.016  # failure / SOW leg 2

all_rets = np.concatenate([up_rets, down_rets])
close = start_price * np.exp(np.cumsum(all_rets))

open_ = close * (1 + np.random.normal(0, 0.002, n_days))
high = np.maximum(open_, close) * (1 + np.abs(np.random.normal(0, 0.003, n_days)))
low = np.minimum(open_, close) * (1 - np.abs(np.random.normal(0, 0.003, n_days)))

base_vol = 250_000_000  # illustrative traded quantity, NSE-index-futures-ish scale
vol_noise = np.random.normal(1.0, 0.25, n_days)
# volume tends to expand on the down-leg (esp. the SOW breaks) -- built in on purpose
vol_multiplier = np.ones(n_days)
vol_multiplier[up_days:] *= 1.15
vol_multiplier[up_days + 46: up_days + 50] *= 1.6
vol_multiplier[up_days + 106: up_days + 110] *= 1.8
volume = (base_vol * vol_noise * vol_multiplier).clip(min=1_000_000).astype(int)

df = pd.DataFrame({
    "TIMESTAMP": dates.strftime("%d-%m-%Y"),
    "OPEN": open_.round(2),
    "HIGH": high.round(2),
    "LOW": low.round(2),
    "CLOSE": close.round(2),
    "TOTTRDQTY": volume,
})

out_path = "/home/claude/harsh/data/sample_nifty_daily.csv"
df.to_csv(out_path, index=False)
print(f"Wrote {len(df)} daily rows to {out_path}")
print(df.head(3))
print(df.tail(3))
