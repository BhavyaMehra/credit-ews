import pandas as pd
import numpy as np
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
config = yaml.safe_load(open(ROOT / "config.yaml"))

def compute_ratios(fundamentals: pd.DataFrame) -> pd.DataFrame:
    """Compute financial ratios for all companies."""
    df = fundamentals.copy()

    # Interest Coverage Ratio
    df["interest_coverage"] = df["ebit"] / df["interest_expense"].abs()

    # Debt to Equity
    df["debt_to_equity"] = df["total_debt"] / df["total_equity"].abs()

    # Current Ratio
    df["current_ratio"] = df["current_assets"] / df["current_liabilities"]

    # Return on Assets
    df["roa"] = df["net_income"] / df["total_assets"]

    # Debt to Assets
    df["debt_to_assets"] = df["total_debt"] / df["total_assets"]

    ratios = df[[
        "interest_coverage",
        "debt_to_equity",
        "current_ratio",
        "roa",
        "debt_to_assets"
    ]]

    print(f"[Ratios] Computed for {ratios.shape[0]} companies")
    return ratios


def score_ratios(ratios: pd.DataFrame) -> pd.DataFrame:
    """
    Score each ratio 0 to 1.
    1 = most stressed, 0 = safest.
    """
    scores = pd.DataFrame(index=ratios.index)

    # Interest Coverage — lower is worse
    scores["icr_score"] = np.where(
        ratios["interest_coverage"].isna(), 0.5,
        np.where(ratios["interest_coverage"] < 1, 1.0,
        np.where(ratios["interest_coverage"] < 3, 0.6,
        0.0))
    )

    # Debt to Equity — higher is worse
    scores["de_score"] = np.where(
        ratios["debt_to_equity"].isna(), 0.5,
        np.where(ratios["debt_to_equity"] > 3, 1.0,
        np.where(ratios["debt_to_equity"] > 1, 0.6,
        0.0))
    )

    # Current Ratio — lower is worse
    scores["cr_score"] = np.where(
        ratios["current_ratio"].isna(), 0.5,
        np.where(ratios["current_ratio"] < 1, 1.0,
        np.where(ratios["current_ratio"] < 2, 0.4,
        0.0))
    )

    # ROA — lower is worse
    scores["roa_score"] = np.where(
        ratios["roa"].isna(), 0.5,
        np.where(ratios["roa"] < 0, 1.0,
        np.where(ratios["roa"] < 0.05, 0.5,
        0.0))
    )

    # Debt to Assets — higher is worse
    scores["da_score"] = np.where(
        ratios["debt_to_assets"].isna(), 0.5,
        np.where(ratios["debt_to_assets"] > 0.6, 1.0,
        np.where(ratios["debt_to_assets"] > 0.3, 0.5,
        0.0))
    )

    # Composite financial stress score — equal weights for now
    scores["financial_stress_score"] = scores[[
        "icr_score", "de_score", "cr_score", "roa_score", "da_score"
    ]].mean(axis=1)

    print(f"[Scores] Financial stress scored for {scores.shape[0]} companies")
    return scores


def run_financials(fundamentals: pd.DataFrame) -> pd.DataFrame:
    """Run full financial ratio analysis."""
    print("\n=== Financial Ratio Analysis ===")
    ratios = compute_ratios(fundamentals)
    scores = score_ratios(ratios)
    
    # Combine ratios and scores into one DataFrame
    result = pd.concat([ratios, scores], axis=1)
    return result


if __name__ == "__main__":
    from data_ingestion import run_ingestion
    from db import write_financials

    data = run_ingestion()
    results = run_financials(data["fundamentals"])
    write_financials(results)
