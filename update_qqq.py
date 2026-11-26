"""Download QQQ daily closes from Yahoo Finance and write qqq.csv (Date,Close)."""
import yfinance as yf

df = yf.download("QQQ", period="2y", interval="1d", auto_adjust=False, progress=False)
close = df["Close"]
if getattr(close, "ndim", 1) == 2:  # newer yfinance returns one column per ticker
    close = close.iloc[:, 0]
close = close.dropna()
if len(close) < 50:
    raise SystemExit("Too little data returned; keeping the existing qqq.csv")

with open("qqq.csv", "w") as f:
    f.write("Date,Close\n")
    for d, p in close.items():
        f.write(f"{d.strftime('%Y-%m-%d')},{float(p):.2f}\n")
print("wrote", len(close), "rows, last", close.index[-1].date(), float(close.iloc[-1]))
