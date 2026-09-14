"""
data_loader.py
---------------
Loads OHLCV price data (e.g. exported from NSE Bhavcopy, or any broker/data
vendor CSV) and resamples it to WEEKLY bars.

Why weekly only: per project rule, no trend/regime decision is made off a
single day's data. A trend must hold for at least a week, so every
downstream module (trend_classifier, downtrend_signals) operates on
weekly OHLCV bars only -- never daily.

Expected input CSV columns (case-insensitive, flexible naming):
    date, open, high, low, close, volume

NSE Bhavcopy columns typically look like: TIMESTAMP, OPEN, HIGH, LOW,
CLOSE, TOTTRDQTY (or similar) -- the loader below auto-maps common
column name variants so you can point it at a raw Bhavcopy export.
"""

import pandas as pd

# Common column name variants seen across NSE Bhavcopy exports / brokers
COLUMN_ALIASES = {
    "date": ["date", "timestamp", "trade_date", "trddate"],
    "open": ["open", "open_price"],
    "high": ["high", "high_price"],
    "low": ["low", "low_price"],
    "close": ["close", "close_price", "last", "ltp"],
    "volume": ["volume", "tottrdqty", "ttl_trd_qnty", "qty", "traded_qty"],
}


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    lower_cols = {c.lower().strip(): c for c in df.columns}
    rename_map = {}
    for standard_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                rename_map[lower_cols[alias]] = standard_name
                break
    df = df.rename(columns=rename_map)
    missing = [c for c in COLUMN_ALIASES if c not in df.columns]
    if missing:
        raise ValueError(
            f"Could not find columns for: {missing}. "
            f"Available columns: {list(df.columns)}"
        )
    return df[["date", "open", "high", "low", "close", "volume"]]


def load_daily_csv(path: str) -> pd.DataFrame:
    """Load a raw daily OHLCV CSV and return a clean, sorted DataFrame."""
    df = pd.read_csv(path)
    df = _map_columns(df)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    return df


def resample_to_weekly(daily_df: pd.DataFrame, week_ending: str = "FRI") -> pd.DataFrame:
    """
    Resample daily OHLCV to weekly bars.
    week_ending: NSE trading week ends Friday by default.
    """
    df = daily_df.set_index("date")
    weekly = df.resample(f"W-{week_ending}").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    weekly = weekly.dropna(subset=["open", "high", "low", "close"])
    weekly = weekly.reset_index().rename(columns={"date": "week_end"})
    return weekly


def load_weekly(path: str, week_ending: str = "FRI") -> pd.DataFrame:
    """Convenience: load a daily CSV straight to weekly bars."""
    daily = load_daily_csv(path)
    return resample_to_weekly(daily, week_ending=week_ending)
