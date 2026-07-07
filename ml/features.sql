-- VAAYU feature table for the 24h spike-forecast models (CLAUDE.md §6).
-- Source history: aqi_cams (CAMS-modelled pollutants at station locations) +
-- raw_weather (per-city hourly). CPCB has no history, so training runs on CAMS
-- (labelled; cross-validated on live CPCB later — docs/LIMITATIONS.md).
--
-- Contiguity assumption: CAMS/ERA5 are gap-free hourly, so "N rows" == "N hours"
-- for LAG / rolling / forward windows. Rows without a complete 24h future window
-- or full lag history are dropped so labels/features are never partial.
--
-- Spike label (§6.1): within next 24h, station PM2.5 max (a) enters Poor+ (>90)
-- OR (b) rises >=1 full CPCB sub-index category from the current hour.
CREATE OR REPLACE TABLE `{project}.{dataset}.features`
PARTITION BY DATE(ts)
CLUSTER BY city_id, station_id AS
WITH base AS (
  SELECT
    c.city_id, c.station_id, c.ts,
    c.pm2_5, c.pm10, c.nitrogen_dioxide, c.sulphur_dioxide, c.ozone, c.carbon_monoxide,
    w.temperature_2m, w.relative_humidity_2m, w.wind_speed_10m,
    w.wind_direction_10m, w.precipitation, w.surface_pressure
  FROM `{project}.{dataset}.aqi_cams` c
  LEFT JOIN `{project}.{dataset}.raw_weather` w
    ON w.city_id = c.city_id AND w.ts = c.ts
),
windowed AS (
  SELECT
    city_id, station_id, ts,
    pm2_5, pm10, nitrogen_dioxide, sulphur_dioxide, ozone, carbon_monoxide,
    temperature_2m, relative_humidity_2m, wind_speed_10m,
    wind_direction_10m, precipitation, surface_pressure,

    -- CPCB PM2.5 sub-index category of the current hour (0=Good .. 5=Severe)
    CASE WHEN pm2_5 <= 30 THEN 0 WHEN pm2_5 <= 60 THEN 1 WHEN pm2_5 <= 90 THEN 2
         WHEN pm2_5 <= 120 THEN 3 WHEN pm2_5 <= 250 THEN 4 ELSE 5 END AS current_cat,

    -- lag features (hours)
    LAG(pm2_5, 1)  OVER w AS pm25_lag_1,
    LAG(pm2_5, 3)  OVER w AS pm25_lag_3,
    LAG(pm2_5, 6)  OVER w AS pm25_lag_6,
    LAG(pm2_5, 12) OVER w AS pm25_lag_12,
    LAG(pm2_5, 24) OVER w AS pm25_lag_24,

    -- rolling stats over trailing 6h / 24h
    AVG(pm2_5) OVER (w ROWS BETWEEN 5  PRECEDING AND CURRENT ROW) AS pm25_roll_mean_6,
    MAX(pm2_5) OVER (w ROWS BETWEEN 5  PRECEDING AND CURRENT ROW) AS pm25_roll_max_6,
    AVG(pm2_5) OVER (w ROWS BETWEEN 23 PRECEDING AND CURRENT ROW) AS pm25_roll_mean_24,
    MAX(pm2_5) OVER (w ROWS BETWEEN 23 PRECEDING AND CURRENT ROW) AS pm25_roll_max_24,

    -- temporal
    EXTRACT(HOUR      FROM ts) AS hour,
    EXTRACT(DAYOFWEEK FROM ts) AS dow,
    EXTRACT(MONTH     FROM ts) AS month,

    -- forward WEATHER aggregates over next 24h (legit: weather forecast is
    -- available at prediction time; future pollutants are NOT used as features)
    MIN(wind_speed_10m)       OVER (w ROWS BETWEEN 1 FOLLOWING AND 24 FOLLOWING) AS fwd24_wind_min,
    AVG(wind_speed_10m)       OVER (w ROWS BETWEEN 1 FOLLOWING AND 24 FOLLOWING) AS fwd24_wind_mean,
    AVG(relative_humidity_2m) OVER (w ROWS BETWEEN 1 FOLLOWING AND 24 FOLLOWING) AS fwd24_rh_mean,
    SUM(precipitation)        OVER (w ROWS BETWEEN 1 FOLLOWING AND 24 FOLLOWING) AS fwd24_precip_sum,
    AVG(temperature_2m)       OVER (w ROWS BETWEEN 1 FOLLOWING AND 24 FOLLOWING) AS fwd24_temp_mean,

    -- LABEL inputs: max PM2.5 over the next 24h, and completeness guards
    MAX(pm2_5) OVER (w ROWS BETWEEN 1 FOLLOWING AND 24 FOLLOWING) AS future_max_pm25,
    COUNT(pm2_5) OVER (w ROWS BETWEEN 1 FOLLOWING AND 24 FOLLOWING) AS future_n,
    COUNT(pm2_5) OVER (w ROWS BETWEEN 24 PRECEDING AND CURRENT ROW) AS trailing_n
  FROM base
  WINDOW w AS (PARTITION BY station_id ORDER BY UNIX_SECONDS(ts))
),
labelled AS (
  SELECT
    *,
    CASE WHEN future_max_pm25 <= 30 THEN 0 WHEN future_max_pm25 <= 60 THEN 1
         WHEN future_max_pm25 <= 90 THEN 2 WHEN future_max_pm25 <= 120 THEN 3
         WHEN future_max_pm25 <= 250 THEN 4 ELSE 5 END AS future_cat
  FROM windowed
  WHERE future_n = 24 AND trailing_n = 25   -- full 24h ahead + 24h history
)
SELECT
  l.* EXCEPT(future_n, trailing_n),
  -- Targets (choice justified in docs/EVALUATION.md):
  --  breach      = PRIMARY. PM2.5 max exceeds India's NAAQS 24h safe limit
  --                (60 µg/m³) within 24h. Legally-grounded, matches the pitch
  --                phrase "breach safe limits tomorrow", non-degenerate for
  --                every city incl. Bengaluru (§6.1's Poor=90 was all-zero for
  --                clean southern cities — genuinely, not a bug).
  --  breach_poor = reference: reaches CPCB Poor+ (>90) — Delhi-severity events.
  --  onset       = newly crosses the safe limit (currently <60, breaches >=60).
  --  spike       = §6.1 literal union (enters Poor+ OR rises >=1 category); kept
  --                for reference — fires ~60% of hours, too common to be actionable.
  CAST(future_max_pm25 >= 60 AS INT64) AS breach,
  CAST(future_max_pm25 >= 90 AS INT64) AS breach_poor,
  CAST(pm2_5 < 60 AND future_max_pm25 >= 60 AS INT64) AS onset,
  CAST((future_cat >= 3 OR future_cat >= current_cat + 1) AS INT64) AS spike,
  -- temporal split (§6.3): proportional 70/15/15 by calendar day, never random
  CASE
    WHEN DATE_DIFF(DATE(ts), d.min_d, DAY) < CAST(0.70 * d.span AS INT64) THEN 'TRAIN'
    WHEN DATE_DIFF(DATE(ts), d.min_d, DAY) < CAST(0.85 * d.span AS INT64) THEN 'VAL'
    ELSE 'TEST'
  END AS split
FROM labelled l
CROSS JOIN (
  SELECT MIN(DATE(ts)) AS min_d, DATE_DIFF(MAX(DATE(ts)), MIN(DATE(ts)), DAY) AS span
  FROM labelled
) d;
