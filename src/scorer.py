import pandas as pd
import numpy as np
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
config = yaml.safe_load(open(ROOT / "config.yaml"))

# Weights from config: merton=0.40, financials=0.35, market=0.25
WEIGHTS = config["scoring_weights"]


def compute_ews_score(merton_results: pd.DataFrame, financial_results: pd.DataFrame, market_results: pd.DataFrame) -> pd.DataFrame:
    """
    Combine Merton PD, financial stress and market stress into a single Early Warning Score (EWS) btw 0 and 1.
    1 = Highest default risk, 0 = safest.
    """

    scores = pd.DataFrame(index=merton_results.index)

    # AFTER RUNNING THE MODEL WITH RAW PD we observed it is near-zero for most companies, killing the signal.
    # Percentile rank spreads it across 0-1 based on relative risk within the universe.
    # A company with the highest PD gets 1.0, lowest gets 0.0 — regardless of absolute values.
    scores['merton_score'] = merton_results['probability_of_default'].rank(pct=True)

    # Pull composite scores from other modules
    scores['financial_score'] = financial_results['financial_stress_score']
    scores['market_score'] = market_results['market_stress_score']

    # weighted composite
    scores['ews_score'] = (
        scores['merton_score'] * WEIGHTS['merton']  +
        scores['financial_score'] * WEIGHTS['financials'] +
        scores['market_score'] * WEIGHTS['market']
    )

    # Rank companies: 1 == most at risk
    scores['ews_rank'] = scores['ews_score'].rank(ascending=False).astype(int)

    print(f'[Scorer] EWS computed for {scores.shape[0]} companies.')
    return scores 


def run_scorer(merton_results: pd.DataFrame, financial_results: pd.DataFrame, market_results: pd.DataFrame) -> pd.DataFrame:
    """
    Run full EWS scoring pipeline.
    """
    print("\n=== EWS Scoring ===")
    scores = compute_ews_score(merton_results, financial_results, market_results)
    return scores


if __name__ == "__main__":
    from data_ingestion import run_ingestion
    from merton import run_merton
    from financials import run_financials
    from market import run_market
    from db import write_ews

    data = run_ingestion()
    merton_results = run_merton(data['fundamentals'], data['volatility'])
    financial_results = run_financials(data['fundamentals'])
    market_results = run_market(data['prices'], data['volatility'], data['fundamentals'])

    scores = run_scorer(merton_results, financial_results, market_results)
    write_ews(scores)
    print("\nEWS scores pushed to Postgres.")
