"""
run.py
------
Entry point. Point this at a daily OHLCV CSV (e.g. NSE Bhavcopy export)
for one instrument (index or stock) and it will:

  1. Resample to WEEKLY bars (per project rule: no daily decisions)
  2. Classify the current regime (Phase 1: trend_classifier)
  3. If the regime is a CONFIRMED downtrend, scan for Wyckoff
     Upthrust / Sign-of-Weakness setups (Phase 2: downtrend_signals)

Usage:
    python run.py path/to/daily_ohlcv.csv

Output: a plain-text summary printed to stdout. Nothing here places a
trade or computes position size yet -- that's intentionally deferred
until entry rules are finalized.
"""

import sys
import json
from data_loader import load_weekly
from trend_classifier import classify_regime
from downtrend_signals import scan


def summarize(weekly_df, scan_result):
    lines = []
    lines.append(f"Weekly bars analyzed : {len(weekly_df)}")
    lines.append(f"Latest week ending   : {weekly_df['week_end'].iloc[-1].date()}")
    lines.append(f"Latest weekly close  : {weekly_df['close'].iloc[-1]:.2f}")
    lines.append("")
    lines.append(f"REGIME CALL: {scan_result['regime']}")
    lines.append("")

    if scan_result["regime"] == "DOWNTREND":
        ev = scan_result["regime_evidence"]
        lines.append("-- Evidence --")
        lines.append(f"  Structure: {ev['structure']['structure']}")
        d = ev["distribution"]
        lines.append(f"  Distribution weeks: {d['distribution_week_count']} in last {d['window_weeks']} weeks "
                      f"(alert={d['alert']})")
        vt = ev["volume_trend"]
        lines.append(f"  Volume trend read: {vt['read']}")
        lines.append("")
        lines.append(f"-- Downtrend setups found: {len(scan_result['setups'])} --")
        for s in scan_result["setups"]:
            sow = f"SOW confirmed on {s['sow_week_end']}" if s["sow_confirmed"] else "no SOW confirmation yet"
            lines.append(f"  Upthrust week {s['week_end'].date() if hasattr(s['week_end'], 'date') else s['week_end']} "
                         f"| close {s['close']:.2f} vs resistance {s['reference_resistance']:.2f} | {sow}")
        lines.append("")
        lines.append(f"NOTE: {scan_result['note']}")
    else:
        lines.append(scan_result.get("note", "No confirmed downtrend -- scanner idle."))

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py path/to/daily_ohlcv.csv")
        sys.exit(1)

    csv_path = sys.argv[1]
    weekly_df = load_weekly(csv_path)

    if len(weekly_df) < 10:
        print(f"Only {len(weekly_df)} weekly bars available -- need at least 10 for a reliable regime read.")
        sys.exit(1)

    scan_result = scan(weekly_df)
    print(summarize(weekly_df, scan_result))

    # Also dump machine-readable output for downstream use
    out_path = csv_path.rsplit(".", 1)[0] + "_scan_result.json"
    with open(out_path, "w") as f:
        json.dump(scan_result, f, default=str, indent=2)
    print(f"\nFull scan result written to: {out_path}")


if __name__ == "__main__":
    main()
