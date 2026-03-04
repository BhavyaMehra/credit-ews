"""
pipeline.py — Credit EWS Orchestrator
Single entry point to run the full early warning system.
"""

from data_ingestion import run_ingestion
from merton import run_merton
from financials import run_financials
from market import run_market
from scorer import run_scorer
from db import run_db_write


def run_pipeline():

    # ── Step 1: Data Ingestion ─────────────────────────
    print("\n=== Starting EWS Pipeline ===")

    data = run_ingestion()

    prices       = data["prices"]
    volatility   = data["volatility"]
    fundamentals = data["fundamentals"]

    # ── Step 2: Merton Model ───────────────────────────
    # Back-solves for asset value + volatility → DD and PD per ticker
    merton_results = run_merton(fundamentals, volatility)

    # ── Step 3: Financial Ratios ───────────────────────
    # ICR, D/E, current ratio, ROA, D/A → scored 0-1
    financial_results = run_financials(fundamentals)

    # ── Step 4: Market Signals ─────────────────────────
    # Momentum, vol regime, beta-adjusted drawdown → scored 0-1
    market_results = run_market(prices, volatility, fundamentals)

    # ── Step 5: EWS Composite Score ────────────────────
    # Merton 40% + Financials 35% + Market 25% → ranked 1 = most at risk
    ews_results = run_scorer(merton_results, financial_results, market_results)

    # ── Step 6: Write to Postgres ──────────────────────
    run_db_write(data, merton_results, financial_results, market_results, ews_results)

    print("\n=== Pipeline Complete ===")


if __name__ == "__main__":
    run_pipeline()