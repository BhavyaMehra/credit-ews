# Credit EWS — Model Findings & Tuning Log

## Universe
33 tickers across Banks, Telecom, Media, NBFC, Aviation, Energy, Conglomerates, Metals, Pharma, IT, Chemicals, Infrastructure, Realty.
Deliberately mixed — healthy blue-chips (TCS, Infosys, Cipla) alongside known stressed names (RCOM, IDEA, JPASSOCIAT) to test model discrimination.

---

## Iteration 1 — Initial Run (35 tickers, large-cap heavy)

**Observation:** Merton PD was flat for almost all companies.
- 75th percentile PD = 0.000. Three quarters of the universe had near-zero default probability.
- Root cause: universe was dominated by large, healthy companies. Merton's structural model works best near distress — for Maruti or Infosys, asset value is so far above debt that DD is 30-40 standard deviations, making N(-DD) effectively zero.
- Financial and market signals were doing all the work. Merton's 40% weight was dead weight.

**Decision:** Expand universe with genuinely stressed companies — RCOM, JPASSOCIAT, GTLINFRA, RAYMOND. Remove clean banks (HDFC, SBI, RBL, IDFC). Remove most NBFCs, keep Bajaj Finance (healthy anchor) and add IIFL (RBI gold loan ban 2024).

---

## Iteration 2 — Percentile Ranking on Merton PD

**Observation:** Even with stressed companies added, raw PD values clustered near zero. Absolute PD differences (0.001 vs 0.016) were real but visually and mathematically invisible at 30% weight.

**Decision:** Replace raw PD with percentile rank (`rank(pct=True)`) in scorer.py.
- This spreads Merton signal across 0–1 based on relative risk within the universe.
- A company with the highest PD gets 1.0, lowest gets 0.0 — regardless of absolute values.
- Trade-off: loses absolute probability meaning, gains discriminatory power.

**Weight adjustment:** Merton 0.40 → 0.30, Financials 0.35 → 0.40, Market 0.25 → 0.30.
Rationale: Financials showed the best natural spread (std 0.32, full 0–1 range) and deserved more weight.

---

## Iteration 2 — Results

**EWS Top 5:** RCOM, JPASSOCIAT, GTLINFRA, IDEA, GMRAIRPORT. All are genuinely distressed or high-leverage names. Model is discriminating correctly.

**Score distribution after tuning:**
- Merton: now spread across 0–1 via percentile rank
- Financial: std 0.32, range 0–1. Best natural signal.
- Market: std 0.18, max 0.67. Thresholds may be too conservative — revisit.
- EWS: range 0.07–0.79. 9 companies above 0.5 stress threshold.

---

## Specific Company Observations

**IDEA.NS** — Market score = 0.0 despite being a well-known distressed stock.
Price has been crushed for so long that 3M momentum and vol regime appear "stable."
Model sees calm where there is flatline distress. Merton and financials correctly flag it (scores 0.94 and 1.0). Market signal blind spot for chronic distress vs acute stress.

**RAYMOND.NS** — Highest raw Merton PD (~0.10) in the universe but sits mid-table in EWS.
Financial and market scores are moderate, pulling composite down.
Structurally risky per Merton but not in acute operational stress. Interesting divergence case.

**GMRAIRPORT.NS** — High financial stress (1.0) and moderate market stress but lower Merton.
Driven by infrastructure-style leverage — large debt is part of the business model, not necessarily default risk. Merton partially accounts for this via asset value backing.

**BAJFINANCE.NS** — Sitting mid-table as expected. Healthy NBFC anchor performing as intended contrast to IIFL.

**POLYCAB.NS, CIPLA.NS, INFY.NS** — Correctly at the bottom. Clean balance sheets, positive momentum, low drawdown.

---

## Known Model Limitations

1. **Merton + Banks:** Bank leverage includes deposits in total debt, artificially inflating D and distorting PD. Kept only YESBANK and PNB as stress-specific cases.
2. **Market signal blind spot:** Chronic distress (IDEA) scores low on market signals because price has already collapsed and stabilised. Market module is better at catching acute/recent stress.
3. **Percentile rank trade-off:** Merton score now reflects relative rank within universe, not absolute default probability. Universe composition affects scores — adding/removing tickers shifts rankings.
4. **Financial ratio scoring is step-function based** (0, 0.4/0.5/0.6, 1.0 buckets). This limits granularity — many companies share the same score. A continuous scoring approach could improve discrimination.

---

---

## Iteration 3 — Market Signal Redesign

**Problem:** Market stress score was capped at 0.67. Drawdown was the culprit — 75th percentile score was 0.0, meaning three quarters of companies were scoring zero on drawdown. Root cause was using 3-year max drawdown, which captures historical worst case rather than current stress. A company could have had a -50% drawdown 2 years ago and fully recovered but still score 1.0 today.

**Changes made:**

1. **Replaced max drawdown with 6-month drawdown from recent peak.**
   Measures how far the stock is from its 6-month high right now. Captures current equity stress, not historical worst case.

2. **Added 6-month relative return vs Nifty 50.**
   Isolates firm-specific underperformance from broad market moves. A stock falling with the market is different from a stock falling while the market rises.
   Requires fetching `^NSEI` alongside universe tickers in `data_ingestion.py`.

3. **Removed beta adjustment from drawdown.**
   Beta reflects market volatility, not financial distress. Merton already incorporates equity volatility (sigma_E) as an input — using beta in the market module was double-counting market sensitivity.

4. **Composite now averages four signals** — momentum, vol regime, drawdown, relative return — equally weighted.

**Results after redesign:**
- Market score now reaches 1.0 (GTLINFRA)
- EWS range improved from 0.07–0.79 to 0.07–0.88
- Market signal meaningfully contributing to all top 10 companies

---

## Iteration 3 — Results

**EWS Top 5:** GTLINFRA, JPASSOCIAT, RCOM, IDEA, IIFL. Genuinely distressed names dominating as expected.

**Score distribution:**
- Market: now reaching 1.0, mean 0.31, std improved
- EWS: range 0.07–0.88, 10+ companies above 0.5 stress threshold

---

## Specific Company Observations (Updated)

**GTLINFRA.NS** — Rank 1. Market score 1.0, all three components above 0.8. Broad-based stress across structural, financial and market signals. High conviction flag.

**IDEA.NS** — Rank 4. Market score only 0.25 despite being chronically distressed.
Price collapsed years ago and has flatlined — recent 6M drawdown and relative return look stable because there's nothing left to fall. Merton (0.94) and Financial (1.0) correctly flag it. Confirmed market signal blind spot for chronic vs acute stress.

**RAYMOND.NS** — Rank 10. Merton score 1.0 (highest raw PD in universe) but financial score only 0.20.
Structurally the riskiest per Merton but balance sheet ratios don't show full operational stress. Demerger complexity may be distorting reported financials. Interesting divergence — worth monitoring.

**INDIGO.NS** — Rank 9. Market score 0.875 but financial and Merton moderate.
Being flagged primarily by market signals — drawdown and relative underperformance vs Nifty. Balance sheet not yet reflecting the market's concern.

**GMRAIRPORT.NS** — Rank 7. Financial score 1.0 but market only 0.375.
Market has not reacted to balance sheet stress. Infrastructure leverage is structural and long-dated — market may be pricing in asset backing rather than default risk.

---

## Known Model Limitations (Updated)

1. **Merton + Banks:** Bank leverage includes deposits in total debt, artificially inflating D. Kept only YESBANK and PNB as stress-specific cases with known distress events.
2. **Chronic distress blind spot:** Market module is designed for acute/recent stress. IDEA scores near-zero on market signals despite fundamental distress — price has already fully repriced.
3. **Percentile rank trade-off:** Merton score reflects relative rank within universe, not absolute PD. Universe composition affects all scores — adding/removing tickers shifts rankings.
4. **Financial ratio step-function scoring:** Scores are bucketed (0, 0.4/0.5/0.6, 1.0) limiting granularity. Many companies share identical scores. Continuous scoring would improve discrimination.
5. **Infrastructure leverage:** High debt is structural for infra companies (GMRAIRPORT, JPASSOCIAT). Merton and financial models treat all debt equally — sector-specific adjustments could improve accuracy.

---

## Pending Tuning
- [ ] Add log scale to Merton PD chart in notebook
- [ ] Consider continuous scoring for financial ratios instead of step-function buckets
- [ ] Sector-specific threshold adjustments for infrastructure and banks
