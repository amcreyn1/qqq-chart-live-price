"""Download QQQ prices from Yahoo Finance (daily, 1h, 5m, 1m) and merge them into CSV files.

Yahoo only serves limited history for intraday bars (about 30 days of 1-minute, 60 days of 5-minute,
2 years of 1-hour). Each run merges the new bars into the existing files, so history builds up over time.
Intraday timestamps are written in US Eastern time (the exchange's clock).
"""
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

ET = ZoneInfo("America/New_York")
NOW = datetime.now(ET)


def dl(**kw):
    df = yf.download("QQQ", auto_adjust=False, progress=False, **kw)
    if df is None or df.empty:
        return pd.Series(dtype=float)
    c = df["Close"]
    if getattr(c, "ndim", 1) == 2:  # newer yfinance returns one column per ticker
        c = c.iloc[:, 0]
    return c.dropna()


def fmt_series(c, minutes):
    """Return a Series indexed by text timestamps, with unfinished bars removed."""
    if len(c) == 0:
        return c
    if minutes is None:  # daily
        if NOW.time() < time(16, 5):  # today's daily bar is partial until after the close
            c = c[[d.date() < NOW.date() for d in c.index]]
        out = c.copy()
        out.index = [d.strftime("%Y-%m-%d") for d in c.index]
        return out
    idx = c.index
    if getattr(idx, "tz", None) is None:
        idx = idx.tz_localize("UTC")
    c = c.copy()
    c.index = idx.tz_convert(ET)
    c = c[c.index <= NOW - timedelta(minutes=minutes)]  # keep only bars that have finished
    out = c.copy()
    out.index = [d.strftime("%Y-%m-%d %H:%M") for d in c.index]
    return out


def save(path, new, keep_days=None):
    if new is None or len(new) == 0:
        print(path, "- nothing new, keeping existing file")
        return
    new = pd.Series([float(v) for v in new.values], index=list(new.index))
    old = pd.Series(dtype=float)
    if os.path.exists(path):
        o = pd.read_csv(path)
        old = pd.Series(o["Close"].astype(float).values, index=o["Date"].astype(str).values)
    s = pd.concat([old, new])
    s = s[~s.index.duplicated(keep="last")].sort_index()  # newer download wins for the same timestamp
    if keep_days:
        cutoff = (NOW - timedelta(days=keep_days)).strftime("%Y-%m-%d")
        s = s[s.index >= cutoff]
    if len(s) < 2:
        return
    with open(path, "w") as f:
        f.write("Date,Close\n")
        for d, p in s.items():
            f.write(f"{d},{p:.2f}\n")
    print(path, "->", len(s), "rows, last", s.index[-1], f"{s.iloc[-1]:.2f}")


def one_minute():
    """1-minute data comes in chunks of at most 7 days per request."""
    parts = []
    end = NOW.date() + timedelta(days=1)
    for k in range(5):
        e = end - timedelta(days=7 * k)
        s = e - timedelta(days=7)
        try:
            c = dl(start=s.isoformat(), end=e.isoformat(), interval="1m")
            if len(c):
                parts.append(c)
        except Exception as ex:  # older than Yahoo allows, etc.
            print("1m chunk", s, e, "failed:", ex)
    if not parts:
        return pd.Series(dtype=float)
    c = pd.concat(parts)
    return c[~c.index.duplicated(keep="last")].sort_index()


JOBS = [
    ("qqq.csv", lambda: fmt_series(dl(period="2y", interval="1d"), None), None),
    ("qqq_1h.csv", lambda: fmt_series(dl(period="700d", interval="1h"), 60), None),
    ("qqq_5m.csv", lambda: fmt_series(dl(period="58d", interval="5m"), 5), None),
    ("qqq_1m.csv", lambda: fmt_series(one_minute(), 1), 90),  # keep about 90 days of 1-minute bars
]

for path, fetch, keep in JOBS:
    try:
        save(path, fetch(), keep)
    except Exception as ex:  # one failing interval should not stop the others
        print(path, "failed:", ex)
