import psycopg2
import pandas as pd
from dotenv import dotenv_values
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
env = dotenv_values(ROOT / ".env")

def get_connection():
    """Create and return a Postgres connection."""
    conn = psycopg2.connect(
        host=env["DB_HOST"],
        port=env["DB_PORT"],
        dbname=env["DB_NAME"],
        user=env["DB_USER"],
        password=env["DB_PASSWORD"]
    )
    return conn


def create_tables():
    """Create tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS price_data (
            date DATE,
            ticker VARCHAR(20),
            close_price FLOAT,
            volatility FLOAT,
            PRIMARY KEY (date, ticker)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fundamentals (
            ticker VARCHAR(20) PRIMARY KEY,
            market_cap FLOAT,
            total_debt FLOAT,
            current_assets FLOAT,
            current_liabilities FLOAT,
            total_assets FLOAT,
            total_equity FLOAT,
            ebit FLOAT,
            interest_expense FLOAT,
            revenue FLOAT,
            net_income FLOAT,
            beta FLOAT,
            sector VARCHAR(50),
            last_updated TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Tables created successfully")


def write_prices(prices: pd.DataFrame, volatility: pd.DataFrame):
    """Write price and volatility data to Postgres."""
    conn = get_connection()
    cur = conn.cursor()

    rows_written = 0

    for ticker in prices.columns:
        for date, price in prices[ticker].dropna().items():
            vol = volatility.loc[date, ticker] if (ticker in volatility.columns and date in volatility.index) else None

            cur.execute("""
                INSERT INTO price_data (date, ticker, close_price, volatility)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (date, ticker) DO UPDATE
                SET close_price = EXCLUDED.close_price, 
                    volatility = EXCLUDED.volatility;
            """, (date.date(), ticker, float(price), float(vol) if pd.notna(vol) else None))

            rows_written += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"[DB] Written {rows_written} price rows")


def write_fundamentals(fundamentals: pd.DataFrame):
    """Write fundamentals data to Postgres."""
    conn = get_connection()
    cur = conn.cursor()

    rows_written = 0

    for ticker, row in fundamentals.iterrows():
        cur.execute("""
            INSERT INTO fundamentals (
                    ticker, market_cap, total_debt, current_assets,
                    current_liabilities, total_assets, total_equity,
                    ebit, interest_expense, revenue, net_income, 
                    beta, sector
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker) DO UPDATE SET
                    market_cap = EXCLUDED.market_cap,
                    total_debt = EXCLUDED.total_debt,
                    current_assets = EXCLUDED.current_assets,
                    current_liabilities = EXCLUDED.current_liabilities,
                    total_assets = EXCLUDED.total_assets,
                    total_equity = EXCLUDED.total_equity,
                    ebit = EXCLUDED.ebit,
                    interest_expense = EXCLUDED.interest_expense,
                    revenue = EXCLUDED.revenue,
                    net_income = EXCLUDED.net_income,
                    beta = EXCLUDED.beta,
                    sector = EXCLUDED.sector,
                    last_updated = NOW();
                """, (
                    ticker,
                    float(row['market_cap']) if pd.notna(row['market_cap']) else None,
                    float(row['total_debt']) if pd.notna(row['total_debt']) else None,
                    float(row['current_assets']) if pd.notna(row['current_assets']) else None,
                    float(row['current_liabilities']) if pd.notna(row['current_liabilities']) else None,
                    float(row['total_assets']) if pd.notna(row['total_assets']) else None,
                    float(row['total_equity']) if pd.notna(row['total_equity']) else None,
                    float(row['ebit']) if pd.notna(row['ebit']) else None,
                    float(row['interest_expense']) if pd.notna(row['interest_expense']) else None,
                    float(row['revenue']) if pd.notna(row['revenue']) else None,
                    float(row['net_income']) if pd.notna(row['net_income']) else None,
                    float(row['beta']) if pd.notna(row['beta']) else None,
                    str(row['sector']) if pd.notna(row['sector']) else None,
                ))
        
        rows_written += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"[DB] Written {rows_written} fundamental rows")


def write_merton(merton_results: pd.DataFrame):
    """Write Merton model results to Postgres."""

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS merton_scores(
                ticker VARCHAR(20),
                run_date DATE,
                asset_value FLOAT,
                asset_volatility FLOAT,
                distance_to_default FLOAT,
                probability_of_default FLOAT,
                PRIMARY KEY (ticker, run_date)
                );
""")
    
    rows_written = 0
    run_date = pd.Timestamp.today().date()

    for ticker, row in merton_results.iterrows():
        cur.execute("""
            INSERT INTO merton_scores (
                    ticker, run_date, asset_value, asset_volatility,
                    distance_to_default, probability_of_default
                    )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, run_date) DO UPDATE SET
                    asset_value = EXCLUDED.asset_value,
                    asset_volatility = EXCLUDED.asset_volatility,
                    distance_to_default = EXCLUDED.distance_to_default,
                    probability_of_default = EXCLUDED.probability_of_default;
    """, (
        ticker,
        run_date,
        float(row['asset_value']) if pd.notna(row['asset_value']) else None,
        float(row["asset_volatility"]) if pd.notna(row["asset_volatility"]) else None,
        float(row["distance_to_default"]) if pd.notna(row["distance_to_default"]) else None,
        float(row["probability_of_default"]) if pd.notna(row["probability_of_default"]) else None,
        ))

        rows_written += 1
    
    conn.commit()
    cur.close()
    conn.close()
    print(f" [DB] Written {rows_written} Merton rows.")


def write_financials(financial_results: pd.DataFrame):
    """Write financial ratio scores to Postgres."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS financial_scores (
            ticker VARCHAR(20),
            run_date DATE,
            interest_coverage FLOAT,
            debt_to_equity FLOAT,
            current_ratio FLOAT,
            roa FLOAT,
            debt_to_assets FLOAT,
            icr_score FLOAT,
            de_score FLOAT,
            cr_score FLOAT,
            roa_score FLOAT,
            da_score FLOAT,
            financial_stress_score FLOAT,
            PRIMARY KEY (ticker, run_date)
        );
    """)

    rows_written = 0
    run_date = pd.Timestamp.today().date()

    for ticker, row in financial_results.iterrows():
        cur.execute("""
            INSERT INTO financial_scores (
                ticker, run_date,
                interest_coverage, debt_to_equity, current_ratio,
                roa, debt_to_assets,
                icr_score, de_score, cr_score, roa_score, da_score,
                financial_stress_score
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, run_date) DO UPDATE SET
                interest_coverage = EXCLUDED.interest_coverage,
                debt_to_equity = EXCLUDED.debt_to_equity,
                current_ratio = EXCLUDED.current_ratio,
                roa = EXCLUDED.roa,
                debt_to_assets = EXCLUDED.debt_to_assets,
                icr_score = EXCLUDED.icr_score,
                de_score = EXCLUDED.de_score,
                cr_score = EXCLUDED.cr_score,
                roa_score = EXCLUDED.roa_score,
                da_score = EXCLUDED.da_score,
                financial_stress_score = EXCLUDED.financial_stress_score;
        """, (
            ticker,
            run_date,
            float(row["interest_coverage"]) if pd.notna(row["interest_coverage"]) else None,
            float(row["debt_to_equity"]) if pd.notna(row["debt_to_equity"]) else None,
            float(row["current_ratio"]) if pd.notna(row["current_ratio"]) else None,
            float(row["roa"]) if pd.notna(row["roa"]) else None,
            float(row["debt_to_assets"]) if pd.notna(row["debt_to_assets"]) else None,
            float(row["icr_score"]) if pd.notna(row["icr_score"]) else None,
            float(row["de_score"]) if pd.notna(row["de_score"]) else None,
            float(row["cr_score"]) if pd.notna(row["cr_score"]) else None,
            float(row["roa_score"]) if pd.notna(row["roa_score"]) else None,
            float(row["da_score"]) if pd.notna(row["da_score"]) else None,
            float(row["financial_stress_score"]) if pd.notna(row["financial_stress_score"]) else None,
        ))
        rows_written += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"[DB] Written {rows_written} financial score rows")

def write_market(market_results: pd.DataFrame):
    """Write market signal scores to Postgres."""

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS market_scores (
                ticker VARCHAR(20),
                run_date DATE,
                momentum_3m FLOAT,
                vol_regime FLOAT,
                drawdown_6m FLOAT,
                relative_return_6m FLOAT,
                momentum_score FLOAT,
                vol_score FLOAT,
                drawdown_score FLOAT,
                relative_score FLOAT,
                market_stress_score FLOAT,
                PRIMARY KEY (ticker, run_date)
            );
""")

    rows_written = 0
    run_date = pd.Timestamp.today().date()

    for ticker, row in market_results.iterrows():
        cur.execute("""
            INSERT INTO market_scores (
                    ticker, run_date, momentum_3m, vol_regime, drawdown_6m, relative_return_6m,
                    momentum_score, vol_score, drawdown_score, relative_score, market_stress_score
                    )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, run_date) DO UPDATE SET
                    momentum_3m = EXCLUDED.momentum_3m,
                    vol_regime = EXCLUDED.vol_regime,
                    drawdown_6m = EXCLUDED.drawdown_6m,
                    relative_return_6m = EXCLUDED.relative_return_6m,
                    momentum_score = EXCLUDED.momentum_score,
                    vol_score = EXCLUDED.vol_score,
                    drawdown_score = EXCLUDED.drawdown_score,
                    relative_score = EXCLUDED.relative_score,
                    market_stress_score = EXCLUDED.market_stress_score;
        """, (
            ticker, run_date,
            float(row['momentum_3m']) if pd.notna(row['momentum_3m']) else None,
            float(row['vol_regime']) if pd.notna(row['vol_regime']) else None,
            float(row['drawdown_6m']) if pd.notna(row['drawdown_6m']) else None,
            float(row['relative_return_6m']) if pd.notna(row['relative_return_6m']) else None,
            float(row['momentum_score']) if pd.notna(row['momentum_score']) else None,
            float(row['vol_score']) if pd.notna(row['vol_score']) else None,
            float(row['drawdown_score']) if pd.notna(row['drawdown_score']) else None,
            float(row['relative_score']) if pd.notna(row['relative_score']) else None,
            float(row['market_stress_score']) if pd.notna(row['market_stress_score']) else None,
        ))
        rows_written += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f'[DB] Written {rows_written} market score rows.')


def write_ews(ews_results: pd.DataFrame):
    """
    Write final EWS scores and rankings to Postgres.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ews_scores (
                ticker VARCHAR(20),
                run_date DATE,
                merton_score FLOAT,
                financial_score FLOAT,
                market_score FLOAT,
                ews_score FLOAT,
                ews_rank INT,
                PRIMARY KEY (ticker, run_date)
                );

    """)

    rows_written = 0
    run_date = pd.Timestamp.today().date()

    for ticker, row in ews_results.iterrows():
        cur.execute("""
            INSERT INTO ews_scores (
                    ticker, run_date, merton_score, financial_score, market_score,
                    ews_score, ews_rank
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, run_date) DO UPDATE SET
                    merton_score = EXCLUDED.merton_score,                                      
                    financial_score = EXCLUDED.financial_score,
                    market_score = EXCLUDED.market_score,
                    ews_score = EXCLUDED.ews_score,
                    ews_rank = EXCLUDED.ews_rank;

        """, (
            ticker, run_date,
            float(row["merton_score"]) if pd.notna(row["merton_score"]) else None,              # Actual values the sql query will send to postgres. 
            float(row["financial_score"]) if pd.notna(row["financial_score"]) else None,        # Doing pd.notna check since postgres cant handle Nan.
            float(row["market_score"]) if pd.notna(row["market_score"]) else None,              # So we're sending None
            float(row["ews_score"]) if pd.notna(row["ews_score"]) else None,
            int(row["ews_rank"]) if pd.notna(row["ews_rank"]) else None,
        ))
        rows_written += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f'[DB] Written {rows_written} EWS rows.')



def run_db_write(data: dict, merton_results=None, financial_results=None, market_results=None, ews_results=None):
    """ Create tables and write all data to Postgres."""
    print("\n--- Writing to Postgres ---")
    create_tables()
    write_prices(data['prices'], data['volatility'])
    write_fundamentals(data['fundamentals'])
    if merton_results is not None:
        write_merton(merton_results)
    if financial_results is not None:
        write_financials(financial_results)
    if market_results is not None:
        write_market(market_results)
    if ews_results is not None:
        write_ews(ews_results)
    print("--- DB Write Complete ---")



        
