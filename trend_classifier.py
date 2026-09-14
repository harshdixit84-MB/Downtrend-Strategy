"""
trend_classifier.py
--------------------
Phase 1 of the project: classify the market regime (UPTREND / DOWNTREND /
SIDEWAYS) using ONLY price action and volume, on WEEKLY bars.

Three ingredients, each pure price/volume, no derived oscillators:

1. Swing structure (Dow Theory)
   - Higher Highs + Higher Lows  -> uptrend structure
   - Lower Highs  + Lower Lows   -> downtrend structure
   - Overlapping / no clear sequence -> sideways

2. Distribution weeks (adapted from IBD's daily "distribution day" concept
   to weekly bars, since this project only acts on weekly closes):
   - A "distribution week" = close down >= DECLINE_THRESHOLD vs prior week,
     on volume higher than the prior week.
   - A cluster of these within a rolling window signals institutional
     selling pressure building.

3. Volume trend during the move
   - Rising average volume on down-weeks vs up-weeks -> selling pressure
     is real / expanding (supports a downtrend read)
   - Falling volume on down-weeks -> selling may be drying up (weakens a
     downtrend read, even if price structure still looks bearish)

NOTE: Thresholds below (DECLINE_THRESHOLD, window sizes) are starting
defaults, not finalized -- flagged as open items per the project notes.
Swap them out once real NSE weekly data is available to tune against.
"""

import pandas as pd

# ---- Tunable parameters (placeholders -- revisit with real data) ----
ZIGZAG_THRESHOLD = 0.03      # 3% reversal required to register a new swing point (filters weekly noise)
DECLINE_THRESHOLD = 0.005    # 0.5% weekly decline to qualify as a "distribution week" (weekly equivalent of IBD's 0.2% daily rule, scaled up since weekly bars move more per bar)
DISTRIBUTION_WINDOW = 8      # rolling window, in weeks, to count distribution weeks (~ equivalent of IBD's 25-session/~5-week daily window, widened for weekly bars)
DISTRIBUTION_ALERT_COUNT = 4 # 4+ distribution weeks in the window = meaningful warning
VOLUME_TREND_WINDOW = 4      # weeks used to compare up-week vs down-week volume


def find_swings(weekly_df: pd.DataFrame, threshold: float = ZIGZAG_THRESHOLD) -> pd.DataFrame:
    """
    Flags swing highs/lows using a zigzag: a pivot only registers once
    price has reversed by at least `threshold` (default 3%) from the
    running extreme. This filters normal weekly noise out and keeps only
    swings large enough to matter for a weekly trend read -- a plain
    "higher than neighbors" fractal check (the first version of this
    function) was too noise-sensitive on weekly bars and almost never
    produced a clean, unbroken run of swings.
    """
    df = weekly_df.reset_index(drop=True).copy()
    df["swing_high"] = False
    df["swing_low"] = False
    n = len(df)
    if n < 3:
        return df

    trend = None  # 'up' or 'down', unknown until first threshold break
    extreme_idx = 0
    extreme_price = df["close"].iloc[0]

    for i in range(1, n):
        price = df["close"].iloc[i]
        if trend is None:
            change = (price - extreme_price) / extreme_price
            if change >= threshold:
                trend = "up"
                df.at[extreme_idx, "swing_low"] = True
                extreme_idx, extreme_price = i, price
            elif change <= -threshold:
                trend = "down"
                df.at[extreme_idx, "swing_high"] = True
                extreme_idx, extreme_price = i, price
            elif price > extreme_price or price < extreme_price:
                # keep tracking the running extreme until a threshold break happens
                if abs((price - df["close"].iloc[extreme_idx]) / df["close"].iloc[extreme_idx]) > 0:
                    pass
        elif trend == "up":
            if price > extreme_price:
                extreme_idx, extreme_price = i, price
            elif (extreme_price - price) / extreme_price >= threshold:
                df.at[extreme_idx, "swing_high"] = True
                trend = "down"
                extreme_idx, extreme_price = i, price
        elif trend == "down":
            if price < extreme_price:
                extreme_idx, extreme_price = i, price
            elif (price - extreme_price) / extreme_price >= threshold:
                df.at[extreme_idx, "swing_low"] = True
                trend = "up"
                extreme_idx, extreme_price = i, price

    # close out the final running extreme as a pivot too
    if trend == "up":
        df.at[extreme_idx, "swing_high"] = True
    elif trend == "down":
        df.at[extreme_idx, "swing_low"] = True

    # use the actual weekly high/low of the pivot bar, not just the close,
    # so downstream Upthrust detection compares against real intraweek levels
    return df


def classify_structure(weekly_df: pd.DataFrame, n_swings: int = 3) -> dict:
    """
    Looks at the last n_swings swing highs and n_swings swing lows and
    classifies the sequence as bullish (HH+HL), bearish (LH+LL), or mixed.
    """
    swung = find_swings(weekly_df)
    highs = swung[swung["swing_high"]].tail(n_swings)
    lows = swung[swung["swing_low"]].tail(n_swings)

    def is_rising(series):
        return all(series.iloc[i] < series.iloc[i + 1] for i in range(len(series) - 1))

    def is_falling(series):
        return all(series.iloc[i] > series.iloc[i + 1] for i in range(len(series) - 1))

    structure = "SIDEWAYS"
    if len(highs) >= 2 and len(lows) >= 2:
        higher_highs = is_rising(highs["high"])
        higher_lows = is_rising(lows["low"])
        lower_highs = is_falling(highs["high"])
        lower_lows = is_falling(lows["low"])
        if higher_highs and higher_lows:
            structure = "UPTREND"
        elif lower_highs and lower_lows:
            structure = "DOWNTREND"

    return {
        "structure": structure,
        "recent_swing_highs": highs[["week_end", "high"]].to_dict("records"),
        "recent_swing_lows": lows[["week_end", "low"]].to_dict("records"),
    }


def count_distribution_weeks(weekly_df: pd.DataFrame,
                              decline_threshold: float = DECLINE_THRESHOLD,
                              window: int = DISTRIBUTION_WINDOW) -> dict:
    """
    Counts "distribution weeks" (down >= threshold on rising volume) in the
    most recent `window` weeks.
    """
    df = weekly_df.copy()
    df["pct_change"] = df["close"].pct_change()
    df["vol_change"] = df["volume"].diff()
    df["is_distribution_week"] = (df["pct_change"] <= -decline_threshold) & (df["vol_change"] > 0)

    recent = df.tail(window)
    count = int(recent["is_distribution_week"].sum())
    return {
        "distribution_week_count": count,
        "window_weeks": window,
        "alert": count >= DISTRIBUTION_ALERT_COUNT,
        "distribution_weeks": recent[recent["is_distribution_week"]][["week_end", "close", "volume"]].to_dict("records"),
    }


def volume_trend_read(weekly_df: pd.DataFrame, window: int = VOLUME_TREND_WINDOW) -> dict:
    """
    Compares average volume on up-weeks vs down-weeks over the recent
    window to judge whether the move (up or down) is backed by real
    volume, or fading.
    """
    df = weekly_df.copy()
    df["pct_change"] = df["close"].pct_change()
    recent = df.tail(window)

    up_weeks = recent[recent["pct_change"] > 0]
    down_weeks = recent[recent["pct_change"] < 0]

    avg_up_vol = up_weeks["volume"].mean() if len(up_weeks) else float("nan")
    avg_down_vol = down_weeks["volume"].mean() if len(down_weeks) else float("nan")

    read = "INCONCLUSIVE"
    if pd.notna(avg_up_vol) and pd.notna(avg_down_vol):
        if avg_down_vol > avg_up_vol * 1.1:
            read = "SELLING_PRESSURE_EXPANDING"
        elif avg_up_vol > avg_down_vol * 1.1:
            read = "BUYING_PRESSURE_EXPANDING"
        else:
            read = "BALANCED"

    return {
        "avg_up_week_volume": avg_up_vol,
        "avg_down_week_volume": avg_down_vol,
        "read": read,
    }


def classify_regime(weekly_df: pd.DataFrame) -> dict:
    """
    Combines structure + distribution weeks + volume trend into a single
    regime call: UPTREND / DOWNTREND / SIDEWAYS, with the supporting
    evidence attached so the call is auditable, not a black box.
    """
    if len(weekly_df) < 10:
        return {"regime": "INSUFFICIENT_DATA", "reason": "need at least 10 weekly bars"}

    structure = classify_structure(weekly_df)
    distribution = count_distribution_weeks(weekly_df)
    volume_trend = volume_trend_read(weekly_df)

    regime = structure["structure"]

    # Downtrend confirmation requires structure AND at least one volume
    # confirmation (distribution cluster or expanding selling-pressure read)
    # -- structure alone can be a fakeout.
    if regime == "DOWNTREND":
        confirmed = distribution["alert"] or volume_trend["read"] == "SELLING_PRESSURE_EXPANDING"
        if not confirmed:
            regime = "DOWNTREND_UNCONFIRMED"

    if regime == "UPTREND":
        confirmed = volume_trend["read"] != "SELLING_PRESSURE_EXPANDING"
        if not confirmed:
            regime = "UPTREND_UNCONFIRMED"

    return {
        "regime": regime,
        "structure": structure,
        "distribution": distribution,
        "volume_trend": volume_trend,
    }
