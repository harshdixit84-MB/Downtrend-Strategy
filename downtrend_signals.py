"""
downtrend_signals.py
---------------------
Phase 2: downtrend SETUP scanner (price + volume only), weekly bars.

Detects two classic Wyckoff-style bearish patterns on top of a confirmed
downtrend (from trend_classifier.classify_regime):

  1. Upthrust (UT) — price pokes above a recent resistance/swing-high week
     but closes back below it, ideally on unremarkable/declining volume
     (a failed rally = trapped buyers, not real demand).

  2. Sign of Weakness (SOW) — a subsequent break below the prior reaction
     low on rising volume, confirming the failed rally is turning into
     renewed selling.

IMPORTANT: This module only flags SETUPS (candidate short zones). It does
NOT decide entries, position sizing, or stops yet -- per the project
notes, entry rules are still to be discussed. Treat `scan()` output as a
watchlist, not a trade signal.
"""

import pandas as pd
from trend_classifier import classify_regime, find_swings


def detect_upthrusts(weekly_df: pd.DataFrame, zigzag_threshold: float = 0.03) -> pd.DataFrame:
    """
    Flags weeks where price traded above a recent swing-high resistance
    level intra-week but closed back below it.
    """
    df = find_swings(weekly_df, threshold=zigzag_threshold).copy()
    df["is_upthrust"] = False
    df["reference_resistance"] = float("nan")

    last_swing_high = None
    for i in range(len(df)):
        if df["swing_high"].iloc[i]:
            last_swing_high = df["high"].iloc[i]
            continue
        if last_swing_high is not None:
            week_high = df["high"].iloc[i]
            week_close = df["close"].iloc[i]
            if week_high > last_swing_high and week_close < last_swing_high:
                df.at[df.index[i], "is_upthrust"] = True
                df.at[df.index[i], "reference_resistance"] = last_swing_high
    return df


def detect_sign_of_weakness(weekly_df: pd.DataFrame, upthrust_df: pd.DataFrame,
                             lookahead_weeks: int = 3) -> pd.DataFrame:
    """
    For each detected upthrust week, checks whether, within the next
    `lookahead_weeks`, price breaks below the prior reaction low on
    volume higher than the average of the preceding down-weeks.
    """
    df = upthrust_df.copy()
    df["sow_confirmed"] = False
    df["sow_week_end"] = None

    upthrust_indices = df.index[df["is_upthrust"]].tolist()
    for idx in upthrust_indices:
        pos = df.index.get_loc(idx)
        if pos < 2:
            continue
        prior_low = df["low"].iloc[max(0, pos - 4):pos].min()
        prior_down_weeks = df.iloc[max(0, pos - 4):pos]
        prior_down_weeks = prior_down_weeks[prior_down_weeks["close"] < prior_down_weeks["open"]]
        avg_down_vol = prior_down_weeks["volume"].mean() if len(prior_down_weeks) else df["volume"].iloc[pos]

        window_end = min(len(df), pos + 1 + lookahead_weeks)
        for j in range(pos + 1, window_end):
            if df["low"].iloc[j] < prior_low and df["volume"].iloc[j] > avg_down_vol:
                df.at[df.index[idx], "sow_confirmed"] = True
                df.at[df.index[idx], "sow_week_end"] = df["week_end"].iloc[j]
                break
    return df


def scan(weekly_df: pd.DataFrame) -> dict:
    """
    Full Phase 2 scan: only looks for setups if Phase 1 confirms a
    downtrend regime. Returns the regime context plus any detected
    upthrust / SOW setups.
    """
    regime_info = classify_regime(weekly_df)
    regime = regime_info.get("regime")

    if regime not in ("DOWNTREND",):
        return {
            "regime": regime,
            "note": "Regime is not a CONFIRMED downtrend -- scanner stays idle. "
                    "(DOWNTREND_UNCONFIRMED means price structure looks bearish "
                    "but volume hasn't confirmed it yet.)",
            "setups": [],
        }

    upthrusts = detect_upthrusts(weekly_df)
    scored = detect_sign_of_weakness(weekly_df, upthrusts)

    setups = scored[scored["is_upthrust"]][[
        "week_end", "high", "close", "reference_resistance", "sow_confirmed", "sow_week_end"
    ]].to_dict("records")

    return {
        "regime": regime,
        "regime_evidence": regime_info,
        "setups": setups,
        "note": "These are candidate short ZONES only. Entry trigger, stop "
                "placement, and position sizing are not finalized yet -- "
                "TODO per project notes.",
    }
