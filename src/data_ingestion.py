import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yaml
from dotenv import dotenv_values
from pathlib import Path

# ── Load config ───────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
config = yaml.safe_load(open(ROOT / "config.yaml"))

TICKERS = list(config["universe"].keys())
LOOKBACK = config["model"]["lookback_years"]
TRADING_DAYS = config["model"]["trading_days"]

END_DATE = datetime.today()
START_DATE = END_DATE - timedelta(days=365 * LOOKBACK)


# ── Price Data ────────────────────────────────────────────
def fetch_prices() -> pd.DataFrame:
    """Fetch adjusted close prices for all tickers."""
    df = yf.download(
        TICKERS,
        start=START_DATE,
        end=END_DATE,
        auto_adjust=True,
        progress=False
    )["Close"]

    if isinstance(df, pd.Series):
        df = df.to_frame(name=TICKERS[0])

    df.dropna(how="all", inplace=True)
    print(f"[Prices] {df.shape[0]} rows x {df.shape[1]} tickers")
    return df


# ── Volatility ────────────────────────────────────────────
def compute_volatility(prices: pd.DataFrame) -> pd.DataFrame:
    """Annualised rolling volatility (input to Merton model)."""
    log_returns = np.log(prices / prices.shift(1)).dropna(how="all")
    vol = log_returns.rolling(TRADING_DAYS).std() * np.sqrt(TRADING_DAYS)
    print(f"[Volatility] Computed for {vol.shape[1]} tickers")
    return vol


# ── Fundamentals ──────────────────────────────────────────
def fetch_fundamentals_single(ticker: str) -> dict:
    """Fetch balance sheet + income statement for one ticker."""
    tk = yf.Ticker(ticker)
    info = tk.info

    bs = tk.balance_sheet
    if bs.empty:
        return {}
    latest_bs = bs.iloc[:, 0]

    inc = tk.income_stmt
    latest_inc = inc.iloc[:, 0] if not inc.empty else pd.Series(dtype=float)

    def get(col, *keys):
        for k in keys:
            if k in col.index and pd.notna(col[k]):
                return float(col[k])
        return np.nan

    return {
        "ticker":               ticker,
        "market_cap":           info.get("marketCap", np.nan),
        "total_debt":           get(latest_bs, "Total Debt", "Long Term Debt"),
        "current_assets":       get(latest_bs, "Current Assets"),
        "current_liabilities":  get(latest_bs, "Current Liabilities"),
        "total_assets":         get(latest_bs, "Total Assets"),
        "total_equity":         get(latest_bs, "Stockholders Equity", "Total Stockholder Equity"),
        "ebit":                 get(latest_inc, "EBIT", "Operating Income"),
        "interest_expense":     get(latest_inc, "Interest Expense"),
        "revenue":              get(latest_inc, "Total Revenue"),
        "net_income":           get(latest_inc, "Net Income"),
        "beta":                 info.get("beta", np.nan),
        "sector":               info.get("sector", "Unknown"),
    }


def fetch_fundamentals() -> pd.DataFrame:
    """Loop all tickers, return one row per company."""
    rows = []
    for t in TICKERS:
        try:
            row = fetch_fundamentals_single(t)
            if row:
                rows.append(row)
                print(f"  ✓ {t}")
            else:
                print(f"  ✗ {t} — empty")
        except Exception as e:
            print(f"  ✗ {t} — {e}")

    df = pd.DataFrame(rows).set_index("ticker")
    print(f"[Fundamentals] {df.shape[0]} companies loaded")
    return df


# ── Master Call ───────────────────────────────────────────
def run_ingestion():
    print("\n=== Data Ingestion Started ===")
    prices = fetch_prices()
    volatility = compute_volatility(prices)
    fundamentals = fetch_fundamentals()
    print("\n=== Ingestion Complete ===")
    return {
        "prices": prices,
        "volatility": volatility,
        "fundamentals": fundamentals
    }


if __name__ == "__main__":
    from db import create_tables, write_prices, write_fundamentals
    data = run_ingestion()
    create_tables()
    write_prices(data['prices'], data['volatility'])
    write_fundamentals(data['fundamentals'])

    
    