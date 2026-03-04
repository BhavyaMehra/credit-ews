import pandas as pd
import numpy as np
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
config = yaml.safe_load(open(ROOT / 'config.yaml'))

TRADING_DAYS = config['model']['trading_days']


def compute_market_signals(prices: pd.DataFrame, volatility: pd.DataFrame, fundamentals: pd.DataFrame) -> pd.DataFrame:
    """
    Compute three raw market stress signals for each ticker:
    - momentum_3m: 3-month price return (negative = falling)
    - vol_regime: ratio of 30d to 252d volatility (>1 = spiking vol)
    - drawdown_6m: how far current price is from its 6-month peak (current stress, not historical worst case)
    - relative_return_6m: stock return vs Nifty 50 over 6 months (firm-specific underperformance)
    """

    # Extract Nifty benchmark and remove from ticker loop
    nifty = prices["^NSEI"].dropna() if "^NSEI" in prices.columns else None
    tickers = [t for t in prices.columns if t != "^NSEI"]

    results = {}

    for ticker in tickers:
        s = prices[ticker].dropna()

        if len(s) < 63:
            results[ticker] = {
                'momentum_3m': np.nan,
                'vol_regime': np.nan,
                'drawdown_6m': np.nan,
                'relative_return_6m': np.nan
            }
            continue

        # 3-month momentum
        momentum = (s.iloc[-1] / s.iloc[-63]) - 1

        # Vol regime: 30d vs 252d vol
        log_ret = np.log(s / s.shift(1)).dropna()
        vol_30 = log_ret.iloc[-30:].std() * np.sqrt(TRADING_DAYS)
        vol_252 = volatility[ticker].dropna().iloc[-1] if ticker in volatility.columns else vol_30
        vol_regime = vol_30 / vol_252

        # 6-month drawdown from recent peak — captures current equity stress
        # No beta adjustment: Merton already incorporates equity volatility
        s_6m = s.iloc[-126:]
        peak_6m = s_6m.expanding().max()
        drawdown_6m = ((s_6m - peak_6m) / peak_6m).iloc[-1]  # current distance from 6m peak

        # Relative return vs Nifty over 6 months — isolates firm-specific stress
        if nifty is not None and len(nifty) >= 126:
            stock_ret_6m = (s.iloc[-1] / s.iloc[-126]) - 1
            nifty_ret_6m = (nifty.iloc[-1] / nifty.iloc[-126]) - 1
            relative_return_6m = stock_ret_6m - nifty_ret_6m
        else:
            relative_return_6m = np.nan

        results[ticker] = {
            'momentum_3m': momentum,
            'vol_regime': vol_regime,
            'drawdown_6m': drawdown_6m,
            'relative_return_6m': relative_return_6m
        }

    return pd.DataFrame.from_dict(results, orient='index')



def score_market(signals: pd.DataFrame) -> pd.DataFrame:
    """
    Convert raw market signals into stress scores between 0 and 1.
    1 = highest stress, 0 = safest.
    """

    scores = pd.DataFrame(index=signals.index)

    # Momentum — negative return = stress
    scores['momentum_score'] = np.where(
        signals['momentum_3m'].isna(), 0.5,
        np.where(signals['momentum_3m'] < -0.15, 1.0,  # fell > 15%
        np.where(signals['momentum_3m'] < -0.05, 0.5,  # fell 5-15%
                 0.0))
    )

    # Vol regime — spiking vol relative to norm = stress
    scores['vol_score'] = np.where(
        signals['vol_regime'].isna(), 0.5,
        np.where(signals['vol_regime'] > 1.5, 1.0,   # vol 50% above norm
        np.where(signals['vol_regime'] > 1.1, 0.5,   # vol mildly elevated
                 0.0))
    )

    # 6-month drawdown from recent peak — how stressed is the stock right now
    scores['drawdown_score'] = np.where(
        signals['drawdown_6m'].isna(), 0.5,
        np.where(signals['drawdown_6m'] < -0.20, 1.0,  # > 20% below 6m peak
        np.where(signals['drawdown_6m'] < -0.08, 0.5,  # 8-20% below peak
                 0.0))
    )

    # Relative return vs Nifty — firm-specific underperformance = stress
    scores['relative_score'] = np.where(
        signals['relative_return_6m'].isna(), 0.5,
        np.where(signals['relative_return_6m'] < -0.15, 1.0,  # underperformed Nifty by > 15%
        np.where(signals['relative_return_6m'] < -0.05, 0.5,  # mild underperformance
                 0.0))
    )

    # Composite: equal weights across four signals
    scores['market_stress_score'] = scores[[
        'momentum_score', 'vol_score', 'drawdown_score', 'relative_score'
    ]].mean(axis=1)

    print(f'[Market] Stress scored for {scores.shape[0]} companies.')

    return scores


def run_market(prices: pd.DataFrame, volatility: pd.DataFrame, fundamentals: pd.DataFrame) -> pd.DataFrame:
    """
    Run full market signal pipeline. Return raw signals + scores combined.
    """

    print("\n=== Market Signal Analysis ===")

    signals = compute_market_signals(prices, volatility, fundamentals)
    scores = score_market(signals)

    result = pd.concat([signals, scores], axis=1)
    return result


if __name__ == "__main__":
    from data_ingestion import run_ingestion
    from db import write_market

    data = run_ingestion()
    results = run_market(data['prices'], data['volatility'], data['fundamentals'])
    write_market(results)
    print("\nMarket results pushed to Postgres.")