-- Portfolio risk segmentation using NTILE window function
-- Flags firms in the top risk decile (highest EWS scores)
-- Useful for watchlist generation and credit monitoring

SELECT *
FROM (
  SELECT ticker,
         ews_score,
         NTILE(10) OVER (ORDER BY ews_score DESC) AS risk_decile
  FROM ews_scores
  WHERE run_date = (SELECT MAX(run_date) FROM ews_scores)
) t
WHERE risk_decile = 1;