import numpy as np
from scipy.stats import norm
from scipy.optimize import fsolve
import pandas as pd
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent  
config = yaml.safe_load(open(ROOT / 'config.yaml'))

RISK_FREE_RATE = config['model']['risk_free_rate']
TRADING_DAYS = config['model']['trading_days']


def compute_d1_d2(V, sigma_V, D, r, T):
    """Compute d1 and d2 for Black Scholes formula"""
    d1 = (np.log(V / D) + (r + 0.5 * sigma_V**2) * T) / (sigma_V * np.sqrt(T))
    d2 = d1 - sigma_V * np.sqrt(T) # How many stddev company is away from default

    return d1, d2


def black_scholes_call(V, sigma_V, D, r, T):
    """Equity value as a call option on firm assets"""
    d1, d2 = compute_d1_d2(V, sigma_V, D, r, T)
    E = V * norm.cdf(d1) - D * np.exp(-r* T) * norm.cdf(d2)
    return E


def merton_equations(params, E, sigma_E, D, r, T):
    """
    Two equations that must equal zero when we find the correct asset values and asset volatility
    """

    V, sigma_V = params

    d1, d2 = compute_d1_d2(V, sigma_V, D, r, T)

    # Equation 1 - Black scholes equity pricing
    eq1 = V * norm.cdf(d1) - D * np.exp(-r * T) * norm.cdf(d2) - E

    # Equation 2 - Volatility relationship
    eq2 = norm.cdf(d1) * sigma_V * V - sigma_E * E

    return [eq1, eq2]


def solve_merton(E, sigma_E, D, r=RISK_FREE_RATE, T=1.0):
    """
    Solve for asset value and asset volatility using iterative solver.
    Inputs scaled to crores for numerical stability.
    """

    # Scale down to crores for numerical stability
    scale = 1e7
    E_scaled = E / scale
    D_scaled = D / scale

    # Initial guess
    V0 = E_scaled + D_scaled                                         # assets must be equal to equity + debt
    sigma_V0 = sigma_E * E_scaled / (E_scaled + D_scaled)            # initial guess for asset volatility, we scale down equity volatility by the proportion of equity to total assets


    try:
        solution = fsolve(
            merton_equations,
            x0=[V0, sigma_V0],
            args=(E_scaled, sigma_E, D_scaled, r, T),
            full_output=True
        )

        V_sol, sigma_V_sol = solution[0]
        ier = solution[2]
        
        # Check if solution converged, ier == 1 means fsolve found a solution
        if ier != 1 or V_sol <= 0 or sigma_V_sol <= 0:
            return None
        
        return {
            'asset_value': V_sol,
            'asset_volatility': sigma_V_sol,
        }
    
    except Exception as e:
        print(f"exception: {e}")
        return None
    

def compute_dd_pd(V, sigma_V, D, r=RISK_FREE_RATE, T=1.0):
    """
    Compute Distance to Default and Probability of Default.
    """
    d1, d2 = compute_d1_d2(V, sigma_V, D, r, T)
    
    DD = d2
    PD = norm.cdf(-d2)
    
    return {
        "distance_to_default": DD,
        "probability_of_default": PD
    }


def run_merton(fundamentals: pd.DataFrame, volatility: pd.DataFrame) -> pd.DataFrame:
    """
    Run Merton model for all companies.
    Returns one row per company with DD and PD.
    """
    results = []

    for ticker, row in fundamentals.iterrows():
        try:
            # Get inputs
            E = row["market_cap"]
            D = row["total_debt"]

            # Get latest volatility for this ticker
            if ticker in volatility.columns:
                sigma_E = (volatility[ticker].dropna().iloc[-1])
            else:
                sigma_E = None

            # Skip if missing critical inputs
            if pd.isna(E) or pd.isna(D) or sigma_E is None or pd.isna(sigma_E):
                print(f"  X {ticker} — missing inputs")
                results.append({
                    "ticker": ticker,
                    "asset_value": None,
                    "asset_volatility": None,
                    "distance_to_default": None,
                    "probability_of_default": None
                })
                continue

            # Solve Merton
            solution = solve_merton(E, sigma_E, D)

            if solution is None:
                print(f"  X {ticker} — solver failed")
                results.append({
                    "ticker": ticker,
                    "asset_value": None,
                    "asset_volatility": None,
                    "distance_to_default": None,
                    "probability_of_default": None
                })
                continue
            

            # Compute DD and PD
            scale = 1e7
            dd_pd = compute_dd_pd(
                solution["asset_value"],
                solution["asset_volatility"],
                D / scale
            )

            results.append({
                "ticker": ticker,
                "asset_value": solution["asset_value"],
                "asset_volatility": solution["asset_volatility"],
                "distance_to_default": dd_pd["distance_to_default"],
                "probability_of_default": dd_pd["probability_of_default"]
            })
            print(f"   {ticker} — DD: {dd_pd['distance_to_default']:.2f}, PD: {dd_pd['probability_of_default']:.2%}")

        except Exception as e:
            print(f"  X {ticker} — {e}")
            continue

    df = pd.DataFrame(results).set_index("ticker")
    return df


if __name__ == "__main__":
    from data_ingestion import run_ingestion
    from db import write_merton

    print("\n=== Running Merton Model ===")
    data = run_ingestion()
    
    merton_results = run_merton(data["fundamentals"], data["volatility"])

    write_merton(merton_results)
    
    print("\n Merton results pushed to Postgres.")

