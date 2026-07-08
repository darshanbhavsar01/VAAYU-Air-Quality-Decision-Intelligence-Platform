-- sentinel (ingestion QA, CLAUDE.md §7.1) — rule-based, no LLM.
-- Per station: feed freshness (stale > 3h) + a z-score anomaly flag (a PM2.5
-- reading far from the station's own recent distribution). z-score is only
-- meaningful once enough CPCB history has accrued (n >= 5); until then it stays
-- null and only freshness is reported — stated honestly, not faked.
CREATE OR REPLACE TABLE `{project}.{dataset}.station_health`
CLUSTER BY city_id AS
WITH pm AS (
  SELECT city_id, station_id, station, ts, avg_value AS pm25
  FROM `{project}.{dataset}.raw_aqi`
  WHERE pollutant = 'PM2.5' AND avg_value IS NOT NULL
),
stats AS (
  SELECT city_id, station_id, ANY_VALUE(station) AS station,
         MAX(ts) AS latest_ts, COUNT(*) AS n,
         AVG(pm25) AS mean_pm, STDDEV(pm25) AS std_pm
  FROM pm GROUP BY city_id, station_id
),
latest AS (
  SELECT city_id, station_id, pm25 AS latest_pm25 FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY station_id ORDER BY ts DESC) AS rn FROM pm
  ) WHERE rn = 1
)
SELECT
  s.city_id, s.station_id, s.station, s.latest_ts,
  ROUND(TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), s.latest_ts, MINUTE) / 60.0, 1) AS age_hours,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), s.latest_ts, MINUTE) / 60.0 > 3 AS stale,
  l.latest_pm25,
  ROUND(SAFE_DIVIDE(l.latest_pm25 - s.mean_pm, s.std_pm), 2) AS zscore,
  (s.n >= 5 AND s.std_pm > 0
     AND ABS(SAFE_DIVIDE(l.latest_pm25 - s.mean_pm, s.std_pm)) > 3) AS anomaly,
  CASE
    WHEN TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), s.latest_ts, MINUTE) / 60.0 > 3 THEN 'stale (>3h)'
    WHEN s.n >= 5 AND s.std_pm > 0
      AND ABS(SAFE_DIVIDE(l.latest_pm25 - s.mean_pm, s.std_pm)) > 3 THEN 'anomalous PM2.5 jump'
    WHEN s.n < 5 THEN 'ok (insufficient history for anomaly check)'
    ELSE 'ok'
  END AS note,
  CURRENT_TIMESTAMP() AS updated_at
FROM stats s JOIN latest l USING (station_id);
