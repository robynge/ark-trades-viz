"""Download daily stock prices for all tickers in ARK trades data."""

import os
import pandas as pd
import yfinance as yf

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PRICES_DIR = os.path.join(DATA_DIR, "prices")
TRADES_FILE = os.path.join(DATA_DIR, "ark_trades_summary.xlsx")

START_DATE = "2025-05-01"
END_DATE = "2026-03-01"


def main():
    os.makedirs(PRICES_DIR, exist_ok=True)

    trades = pd.read_excel(TRADES_FILE)
    tickers = sorted(trades["Ticker"].dropna().unique())
    print(f"Found {len(tickers)} unique tickers")

    # Filter out non-standard tickers (numeric = foreign exchange tickers)
    valid_tickers = [t for t in tickers if isinstance(t, str) and not t.isdigit()]
    skipped = [t for t in tickers if t not in valid_tickers]
    if skipped:
        print(f"Skipping non-US tickers: {skipped}")

    failed = []
    for i, ticker in enumerate(valid_tickers, 1):
        csv_path = os.path.join(PRICES_DIR, f"{ticker}.csv")
        if os.path.exists(csv_path):
            print(f"[{i}/{len(valid_tickers)}] {ticker} — already exists, skipping")
            continue

        print(f"[{i}/{len(valid_tickers)}] Downloading {ticker}...", end=" ")
        try:
            df = yf.download(ticker, start=START_DATE, end=END_DATE, progress=False)
            if df.empty:
                print("WARNING: no data returned")
                failed.append(ticker)
                continue
            # Flatten multi-level columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.to_csv(csv_path)
            print(f"OK ({len(df)} rows)")
        except Exception as e:
            print(f"FAILED: {e}")
            failed.append(ticker)

    if failed:
        print(f"\nFailed tickers ({len(failed)}): {failed}")
    else:
        print("\nAll downloads completed successfully!")


if __name__ == "__main__":
    main()
