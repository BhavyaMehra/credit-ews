-- Detect week-over-week deterioration in Early Warning Score
-- Uses window functions (LAG, ROW_NUMBER)
-- Returns latest change per ticker

SELECT ticker, run_date, ews_change
FROM (
  SELECT 
    ticker,
    run_date,
    ews_score - LAG(ews_score) OVER (PARTITION BY ticker ORDER BY run_date) AS ews_change,
    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY run_date DESC) AS rn
  FROM ews_scores
) t
WHERE rn = 1
AND ews_change IS NOT NULL

