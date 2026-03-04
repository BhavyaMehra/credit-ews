# Credit EWS — Model Findings & Tuning Log

## Universe

33 tickers across Banks, Telecom, Media, NBFC, Aviation, Energy, Conglomerates, Metals, Pharma, IT, Chemicals, Infrastructure and Realty. Deliberately mixed — healthy blue-chips (TCS, Infosys, Cipla) alongside known stressed names (RCOM, IDEA, JPASSOCIAT) to test model discrimination.


## Iteration 1 — Initial Run (35 tickers, large-cap heavy)

**Observation:** Merton PD was flat for almost all companies. The 75th percentile PD was 0.000 — three quarters of the universe had near-zero default probability.

Root cause was the universe being dominated by large, healthy companies. Merton's structural model works best when firms are near distress. For Maruti or Infosys, asset value is so far above debt that Distance to Default exceeds 30 standard deviations, making N(-DD) effectively zero. Financial and market signals were doing all the work while Merton's 40% weight contributed almost nothing.

**Decision:** Expanded universe with genuinely stressed companies — RCOM, JPASSOCIAT, GTLINFRA, RAYMOND. Removed clean banks (HDFC, SBI, RBL, IDFC). Removed most NBFCs, kept Bajaj Finance as a healthy anchor and added IIFL following the RBI gold loan ban in March 2024.


## Iteration 2 — Percentile Ranking on Merton PD

**Observation:** Even after adding distressed companies, raw PD values clustered near zero. Absolute differences like 0.001 vs 0.016 were real but mathematically invisible at 30% weight in the composite score.

**Decision:** Replaced raw PD with percentile rank using `rank(pct=True)` in scorer.py. This spreads the Merton signal across 0 to 1 based on relative risk within the universe. The company with the highest PD gets 1.0 and the lowest gets 0.0 regardless of absolute values. The trade-off is that the score loses its absolute probability interpretation and gains discriminatory power instead.

Weight adjustment: Merton 0.40 to 0.30, Financials 0.35 to 0.40, Market 0.25 to 0.30. Financials showed the best natural spread (std 0.32, full 0 to 1 range) and deserved more weight.

**Results:** EWS Top 5 — RCOM, JPASSOCIAT, GTLINFRA, IDEA, GMRAIRPORT. All genuinely distressed or high-leverage names. Model discriminating correctly. Market score still capped at 0.67 — flagged for redesign.


## Iteration 3 — Market Signal Redesign

**Problem:** Market stress score was capped at 0.67. Drawdown was the culprit — 75th percentile drawdown score was 0.0, meaning three quarters of companies were scoring zero. The root cause was using 3-year max drawdown, which captures historical worst case rather than current stress. A company could have had a 50% drawdown two years ago and fully recovered but still score 1.0 today.

**Changes made:**

Replaced max drawdown with 6-month drawdown from recent peak. This measures how far the stock is from its 6-month high right now, capturing current equity stress rather than historical worst case.

Added 6-month relative return vs Nifty 50 to isolate firm-specific underperformance from broad market moves. A stock falling with the market is different from a stock falling while the market rises. This required fetching `^NSEI` alongside universe tickers in data_ingestion.py.

Removed beta adjustment from drawdown. Beta reflects market volatility, not financial distress. Since Merton already incorporates equity volatility (sigma_E) as an input, using beta in the market module was double-counting market sensitivity.

The composite now averages four signals equally — momentum, vol regime, 6-month drawdown and relative return.

**Results:** Market score now reaches 1.0 (GTLINFRA). EWS range improved from 0.07–0.79 to 0.07–0.88. All top 10 companies show meaningful market signal contribution.


## Company Observations

**GTLINFRA.NS** — Rank 1. Market score 1.0 with all three components above 0.8. Broad-based stress across structural, financial and market signals. Highest conviction flag in the universe.

**IDEA.NS** — Rank 4. Market score only 0.25 despite being chronically distressed. Price collapsed years ago and has flatlined — recent 6-month drawdown and relative return look stable because there is nothing left to fall. Merton (0.94) and Financial (1.0) correctly flag it. This confirmed the market signal blind spot for chronic vs acute stress.

**RAYMOND.NS** — Rank 10. Merton score 1.0 (highest raw PD in the universe) but financial score only 0.20. Structurally the riskiest per Merton but balance sheet ratios do not show full operational stress. Demerger complexity may be distorting reported financials. Interesting divergence worth monitoring.

**INDIGO.NS** — Rank 9. Market score 0.875 but financial and Merton are moderate. Being flagged primarily by market signals — drawdown and relative underperformance vs Nifty. Balance sheet not yet reflecting the market's concern.

**GMRAIRPORT.NS** — Rank 7. Financial score 1.0 but market only 0.375. Infrastructure leverage is structural and long-dated — the market may be pricing in asset backing rather than near-term default risk. Merton partially accounts for this via asset value.

**BAJFINANCE.NS** — Sitting mid-table as expected. Healthy NBFC anchor performing as intended contrast to IIFL.

**POLYCAB.NS, CIPLA.NS, INFY.NS** — Correctly at the bottom. Clean balance sheets, positive momentum, low drawdown.


## Known Model Limitations

**Merton and banks:** Bank leverage includes customer deposits in total debt, artificially inflating D and distorting PD. Kept only YESBANK and PNB as stress-specific cases with documented distress events.

**Chronic distress blind spot:** The market module is designed to catch acute and recent stress. IDEA scores near-zero on market signals despite fundamental insolvency risk because the price has already fully repriced over several years.

**Percentile rank trade-off:** Merton score reflects relative rank within the universe rather than absolute probability of default. Universe composition affects all scores — adding or removing tickers shifts rankings across the board.

**Financial ratio step-function scoring:** Scores are bucketed into discrete values (0, 0.4, 0.5, 0.6, 1.0) which limits granularity. Many companies share identical scores. A continuous scoring approach would improve discrimination between similar firms.

**Infrastructure leverage:** High debt is structural for infra companies like GMRAIRPORT and JPASSOCIAT. The Merton and financial models treat all debt equally — sector-specific adjustments could improve accuracy for capital-intensive sectors.


## Future Tuning Ideas

Continuous scoring for financial ratios instead of step-function buckets would improve discrimination between companies with similar but not identical balance sheets.

Sector-specific thresholds for infrastructure and banks would account for structural leverage patterns that the current model treats as distress signals.

A time-series view tracking EWS score changes week-over-week would add an early deterioration signal on top of the current point-in-time ranking.
