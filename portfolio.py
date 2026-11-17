"""
Stock Portfolio Performance Tracker
-----------------------------------
- Enter tickers, buy prices and share quantities
- Looks up current prices (S&P 500 CSV first, then yfinance, then manual entry)
- Shows value and % gain/loss per holding plus portfolio totals
- Appends every run to portfolio_summary.csv

Run:  python portfolio.py
Optional: pip install yfinance   (for live prices)
"""

import csv
import os
from datetime import datetime

PRICE_DATASET = "sp500.csv"             # downloaded S&P 500 dataset (optional)
SUMMARY_FILE = "portfolio_summary.csv"  # output log

TICKER_COLS = ("symbol", "ticker")
PRICE_COLS = ("price", "close", "current price", "last")


# ---------- Price lookup ----------
def load_csv_prices(path):
    """Read {ticker: price} from a CSV. Column names are auto-detected."""
    prices = {}
    if not os.path.exists(path):
        return prices
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return prices
        cols = {name.strip().lower(): name for name in reader.fieldnames}
        t_col = next((cols[c] for c in TICKER_COLS if c in cols), None)
        p_col = next((cols[c] for c in PRICE_COLS if c in cols), None)
        if not t_col or not p_col:
            return prices
        for row in reader:
            try:
                prices[row[t_col].strip().upper()] = float(row[p_col])
            except (ValueError, AttributeError):
                continue
    return prices


def fetch_live_price(ticker):
    """Try yfinance; return None if unavailable or it fails."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def get_price(ticker, csv_prices):
    if ticker in csv_prices:
        return csv_prices[ticker]
    live = fetch_live_price(ticker)
    if live is not None:
        return live
    return ask_float(f"  Could not find a price for {ticker}. Enter current price: ")


# ---------- Input helpers ----------
def ask_float(prompt, minimum=0.0):
    while True:
        try:
            value = float(input(prompt))
            if value > minimum:
                return value
            print(f"  Value must be greater than {minimum}.")
        except ValueError:
            print("  Please enter a valid number.")


def collect_portfolio():
    """Return {ticker: {'buy_price': x, 'shares': y}}."""
    portfolio = {}
    print("Enter your holdings (press Enter on an empty ticker to finish).\n")
    while True:
        ticker = input("Ticker symbol: ").strip().upper()
        if not ticker:
            if portfolio:
                break
            print("  Add at least one holding.")
            continue
        buy_price = ask_float("  Buy price per share: ")
        shares = ask_float("  Number of shares: ")

        if ticker in portfolio:  # merge repeat buys using weighted average cost
            old = portfolio[ticker]
            total_shares = old["shares"] + shares
            avg = (old["buy_price"] * old["shares"] + buy_price * shares) / total_shares
            portfolio[ticker] = {"buy_price": avg, "shares": total_shares}
        else:
            portfolio[ticker] = {"buy_price": buy_price, "shares": shares}
    return portfolio


# ---------- Calculations ----------
def evaluate(portfolio, csv_prices):
    rows = []
    for ticker, pos in portfolio.items():
        current = get_price(ticker, csv_prices)
        invested = pos["buy_price"] * pos["shares"]
        value = current * pos["shares"]
        gain = value - invested
        pct = (gain / invested) * 100
        rows.append({
            "ticker": ticker,
            "shares": pos["shares"],
            "buy_price": pos["buy_price"],
            "current_price": current,
            "invested": invested,
            "market_value": value,
            "gain_loss": gain,
            "gain_loss_pct": pct,
        })
    return rows


def totals(rows):
    invested = sum(r["invested"] for r in rows)
    value = sum(r["market_value"] for r in rows)
    gain = value - invested
    pct = (gain / invested) * 100 if invested else 0.0
    return invested, value, gain, pct


# ---------- Output ----------
def print_report(rows, invested, value, gain, pct):
    print("\n" + "=" * 78)
    print(f"{'Ticker':<8}{'Shares':>8}{'Buy':>10}{'Now':>10}{'Invested':>12}{'Value':>12}{'P/L %':>10}")
    print("-" * 78)
    for r in rows:
        print(f"{r['ticker']:<8}{r['shares']:>8.2f}{r['buy_price']:>10.2f}"
              f"{r['current_price']:>10.2f}{r['invested']:>12.2f}"
              f"{r['market_value']:>12.2f}{r['gain_loss_pct']:>+9.2f}%")
    print("-" * 78)
    print(f"Total invested : ${invested:,.2f}")
    print(f"Current value  : ${value:,.2f}")
    print(f"Gain / Loss    : ${gain:+,.2f} ({pct:+.2f}%)")
    print("=" * 78)


def log_to_csv(rows, invested, value, gain, pct):
    """Append this run to the summary file (header written only once)."""
    fields = ["timestamp", "ticker", "shares", "buy_price", "current_price",
              "invested", "market_value", "gain_loss", "gain_loss_pct"]
    is_new = not os.path.exists(SUMMARY_FILE) or os.path.getsize(SUMMARY_FILE) == 0
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(SUMMARY_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            writer.writeheader()
        for r in rows:
            writer.writerow({"timestamp": stamp, **{k: round(v, 2) if isinstance(v, float) else v
                                                    for k, v in r.items()}})
        writer.writerow({
            "timestamp": stamp, "ticker": "TOTAL", "shares": "",
            "buy_price": "", "current_price": "",
            "invested": round(invested, 2), "market_value": round(value, 2),
            "gain_loss": round(gain, 2), "gain_loss_pct": round(pct, 2),
        })
    print(f"\nSummary saved to {SUMMARY_FILE}")


def main():
    csv_prices = load_csv_prices(PRICE_DATASET)
    if csv_prices:
        print(f"Loaded {len(csv_prices)} prices from {PRICE_DATASET}")
    else:
        print(f"No usable prices in {PRICE_DATASET}; will try yfinance, then manual entry.")

    portfolio = collect_portfolio()
    rows = evaluate(portfolio, csv_prices)
    invested, value, gain, pct = totals(rows)
    print_report(rows, invested, value, gain, pct)
    log_to_csv(rows, invested, value, gain, pct)


if __name__ == "__main__":
    main()