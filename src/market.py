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
    - max_drawdown: peak-to-trough decline, scaled by beta
    """

    results = {}

    for ticker in prices.columns: # prices df has each column as a ticker showing prices in rows
        s = prices[ticker].dropna()

        # Need atleast 63 trading days(~3 months) to compute signals
        if len(s) < 63:
            results[ticker] = {'momentum_3m': np.nan, 'vol_regime': np.nan, 'max_drawdown': np.nan}
            continue

        # If 3 month price momentum is negative == Stock falling = stress signal
        momentum = (s.iloc[-1] / s.iloc[-63]) - 1

        # Volatility regime = recent 30d vol / 252d vol
        # >1 means volatility is spiking relative to its norm == stress
        log_ret = np.log(s / s.shift(1)).dropna()
        vol_30 = log_ret.iloc[-30:].std() * np.sqrt(TRADING_DAYS)
        vol_252 = volatility[ticker].dropna().iloc[-1] if ticker in volatility.columns else vol_30 # else is for safe fallback
        vol_regime = vol_30 / vol_252


        # Max drawdown scaled by beta
        # High beta stock falling hard == amplified stress signal
        beta = fundamentals.loc[ticker, 'beta'] if ticker in fundamentals.index else 1.0    # if ticker exists in fundamentals df
        beta = beta if pd.notna(beta) else 1.0                                              # if beta exists in fundamentals and if its nan then make it 1.0 default.
        rollmax = s.expanding().max()                                                       # roll_max gives series upto that row with rolling max number
        drawdown = ((s - rollmax) / rollmax).min()                                          # How far current price is from rolling max. We do min to get the worst case/drawdown
        adj_drawdown = drawdown * beta

        results[ticker] = {
            'momentum_3m': momentum,
            'vol_regime': vol_regime,
            'max_drawdown': adj_drawdown
        }
    
    return pd.DataFrame.from_dict(results, orient='index')


def score_market(signals: pd.DataFrame) -> pd.DataFrame:
    """
    Convert raw market signals into stress scores between 0 and 1.
    1 = highest stress, 0 = safest.
    Thresholds are based on empirical rules of thumb for Indian equities.
    """
    
    scores = pd.DataFrame(index=signals.index)

    # Momentum : Deeper negative return = more stress
    scores['momentum_score'] = np.where(
        signals['momentum_3m'].isna(), 0.5,
        np.where(signals['momentum_3m'] < -0.20, 1.0, # fell > 20%
        np.where(signals['momentum_3m'] < -0.05, 0.5, # fell 5-20%
                 0.0))                                # flat or up
    )


    # Volatility regiem: spiking vol relative to norm = stress
    scores['vol_score'] = np.where(
        signals['vol_regime'].isna(), 0.5,
        np.where(signals['vol_regime'] > 1.5, 1.0,       # volatility 50% above norm
        np.where(signals['vol_regime'] > 1.1, 0.5,      # volatility mildly elevated
                 0.0))
    )


    # Drawdown: deeper beta adjusted drawdown = more stress
    scores['drawdown_score'] = np.where(
        signals['max_drawdown'].isna(), 0.5,
        np.where(signals['max_drawdown'] < -0.40, 1.0,  # > 40% drawdown
        np.where(signals['max_drawdown'] < -0.20, 0.5,  # 20-40% drawdown
                 0.0))
    )


    # Composite: equal weights across three signals
    scores['market_stress_score'] = scores[['momentum_score', 'vol_score', 'drawdown_score']].mean(axis=1)

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