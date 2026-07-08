-- station_forecast: the model output the map is built from. For each station,
-- take its most recent complete feature row and run BOTH models:
--   pred_max_pm25_24h : regressor's next-24h max PM2.5 (the "tomorrow" value)
--   breach_prob       : classifier P(exceed NAAQS 60 within 24h)
-- plus the current PM2.5 and the "as of" timestamp. Idempotent (CREATE OR REPLACE).
--
-- Uses the latest labelable feature row per station (bounded by CAMS archive lag
-- + forecast reach). As live CAMS/weather forecast ingest advances, "as_of"
-- moves toward now automatically.
CREATE OR REPLACE TABLE `{project}.{dataset}.station_forecast` AS
WITH latest AS (
  SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY station_id ORDER BY ts DESC) AS rn
    FROM `{project}.{dataset}.features`
  ) WHERE rn = 1
),
reg AS (
  SELECT station_id, predicted_future_max_pm25 AS pred_max_pm25_24h
  FROM ML.PREDICT(MODEL `{project}.{dataset}.pm25_regressor`, (SELECT * FROM latest))
),
clf AS (
  SELECT station_id,
    (SELECT prob FROM UNNEST(predicted_breach_probs) WHERE label = 1) AS breach_prob
  FROM ML.PREDICT(MODEL `{project}.{dataset}.spike_classifier`, (SELECT * FROM latest))
)
SELECT
  l.city_id, l.station_id, s.station, s.latitude, s.longitude,
  l.ts AS as_of,
  l.pm2_5 AS current_pm25,
  reg.pred_max_pm25_24h,
  clf.breach_prob,
  -- forecast CPCB sub-index category of the predicted max
  CASE WHEN reg.pred_max_pm25_24h <= 30 THEN 'Good'
       WHEN reg.pred_max_pm25_24h <= 60 THEN 'Satisfactory'
       WHEN reg.pred_max_pm25_24h <= 90 THEN 'Moderate'
       WHEN reg.pred_max_pm25_24h <= 120 THEN 'Poor'
       WHEN reg.pred_max_pm25_24h <= 250 THEN 'Very Poor' ELSE 'Severe' END AS pred_category,
  CAST(reg.pred_max_pm25_24h >= 60 AS BOOL) AS pred_breach_naaqs,
  -- simple weather-driven attribution ("likely drivers"; heuristic, §6.5)
  l.fwd24_wind_mean, l.fwd24_rh_mean, l.hour,
  CURRENT_TIMESTAMP() AS generated_at
FROM latest l
JOIN `{project}.{dataset}.stations` s USING (station_id)
JOIN reg USING (station_id)
JOIN clf USING (station_id);
