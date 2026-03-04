-- Credit Risk EWS Monitoring Query
-- Purpose: Identify firms whose structural risk diverges from market signals

SELECT ticker,
merton_score,
market_score,
ABS(merton_score - market_score) AS divergence
FROM ews_scores
WHERE run_date = (SELECT MAX(run_date) FROM ews_scores)
ORDER BY divergence DESC;