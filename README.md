# Harsh — India Market Regime & Downtrend Strategy

Price-action + volume only (no RSI/MACD/ADX or other derived oscillators),
built for Indian markets (NSE), weekly timeframe.

## Project rules (locked in so far)
- **Market**: Indian (NSE) — indices and liquid stocks.
- **Data allowed**: price (OHLC) and volume only.
- **Timeframe**: WEEKLY. No trend/regime call is ever made off a single
  day — a trend needs at least a week to count. All modules resample
  daily data to weekly bars before doing anything else.
- **Entry rules**: not finalized yet. This repo currently produces
  regime calls (Phase 1) and short-setup *zones* (Phase 2) — not trade
  entries, stops, or position sizes.
- **Scope**: what else gets added is still to be discussed.

## Structure

```
harsh/
├── src/
│   ├── data_loader.py        # CSV -> daily DataFrame -> weekly OHLCV
│   ├── trend_classifier.py   # Phase 1: regime = UPTREND / DOWNTREND / SIDEWAYS
│   ├── downtrend_signals.py  # Phase 2: Wyckoff Upthrust / Sign-of-Weakness scanner
│   └── run.py                 # entry point, ties it all together
├── tests/
│   └── generate_test_data.py  # synthetic Nifty-like data w/ a built-in regime shift, for smoke-testing
├── data/
│   └── sample_nifty_daily.csv # output of the above
└── README.md
```

## How the regime call works (Phase 1)

Three price/volume-only ingredients, combined:

1. **Structure (Dow Theory)** — zigzag swing detector (3% reversal
   threshold, filters weekly noise) finds real swing highs/lows, then
   checks whether the last few are Higher-Highs+Higher-Lows (uptrend) or
   Lower-Highs+Lower-Lows (downtrend).
2. **Distribution weeks** — a week closing down ≥0.5% on volume higher
   than the prior week. 4+ of these in an 8-week rolling window is
   flagged as a real warning (adapted from IBD's daily "distribution
   day" concept, scaled to weekly bars).
3. **Volume trend** — is average volume expanding on down-weeks vs
   up-weeks (or vice versa) over the last 4 weeks?

A `DOWNTREND` call requires *both* bearish structure *and* at least one
volume confirmation (distribution cluster or expanding selling pressure).
Structure alone without volume backing is downgraded to
`DOWNTREND_UNCONFIRMED` — this exists specifically to avoid calling a
downtrend on price shape alone, which is the most common way naive
trend-following whipsaws.

## How the downtrend scanner works (Phase 2)

Only runs when Phase 1 returns a **confirmed** `DOWNTREND`. Looks for:

- **Upthrust (UT)**: price pokes above a recent swing-high resistance
  intra-week but closes back below it — a failed breakout / trapped
  buyers.
- **Sign of Weakness (SOW)**: within the following weeks, price breaks
  the prior reaction low on volume higher than the recent down-week
  average — confirms the failed rally is turning into renewed selling.

Output is a list of **candidate short zones**, each flagged with whether
SOW has confirmed yet. This is a watchlist, not a trade signal — see
"Open items" below.

## Running it

```bash
cd src
python run.py ../data/sample_nifty_daily.csv
```

Point it at a real daily OHLCV CSV (NSE Bhavcopy export or any broker/
vendor CSV — `data_loader.py` auto-maps common column name variants,
including raw Bhavcopy headers like `TIMESTAMP`, `OPEN`, `TOTTRDQTY`)
instead of the synthetic sample once real data is available.

## Smoke test

`tests/generate_test_data.py` builds a synthetic daily CSV with a
deliberate uptrend → downtrend shift, including two "failed rally"
patterns designed to look like Upthrust/SOW setups. This validates the
plumbing (load → resample → classify → scan runs without errors and
finds *something* sensible) — it is **not** a strategy validation, since
the data is synthetic. Real backtesting still needs real NSE data.

## Open items (intentionally not decided yet)
- **Entry trigger**: exactly when/how to enter once a setup + SOW
  confirmation appears (immediate on SOW break? retest of broken
  support? something else?) — TBD.
- **Stop-loss placement and position sizing** — TBD, but the plan is to
  keep it price-based (e.g. stop above the Upthrust high, risk sized off
  that distance) rather than volatility-indicator-based, consistent with
  the price/volume-only constraint.
- **Uptrend and sideways strategies** — only the downtrend side has been
  built out so far, per current priority.
- **Parameter tuning** — `ZIGZAG_THRESHOLD` (3%), `DECLINE_THRESHOLD`
  (0.5%), `DISTRIBUTION_WINDOW` (8 weeks), `DISTRIBUTION_ALERT_COUNT`
  (4) are first-pass defaults, not yet validated against real Indian
  market data. Revisit once real weekly NSE data is available.
- **Real data source**: NSE Bhavcopy (free, daily) is the standard route
  for Indian EOD price/volume data for backtesting.
