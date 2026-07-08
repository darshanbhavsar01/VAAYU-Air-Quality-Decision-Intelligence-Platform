-- city_grid_surface: Tier A grid (CLAUDE.md §6.4). IDW-interpolate the station
-- forecast onto a ~1km lat/lon grid clipped to each city bbox, and carry a
-- distance-to-nearest-station confidence on every cell (honesty clause — IDW
-- from a handful of stations is an approximation, not measurement).
--
-- Ward mode (Tier B) aggregates this grid to polygons where a validated ward
-- GeoJSON exists; none do yet, so every city ships grid mode (honest default).
CREATE OR REPLACE TABLE `{project}.{dataset}.city_grid_surface`
CLUSTER BY city_id AS
WITH grid AS (
  SELECT c.city_id, lat AS cell_lat, lon AS cell_lon,
         ST_GEOGPOINT(lon, lat) AS cell
  FROM `{project}.{dataset}.cities` c,
    UNNEST(GENERATE_ARRAY(c.lat_min, c.lat_max, 0.01)) AS lat,
    UNNEST(GENERATE_ARRAY(c.lon_min, c.lon_max, 0.01)) AS lon
),
pairs AS (
  SELECT
    g.city_id, g.cell_lat, g.cell_lon,
    sf.current_pm25, sf.pred_max_pm25_24h, sf.breach_prob,
    ST_DISTANCE(g.cell, ST_GEOGPOINT(sf.longitude, sf.latitude)) / 1000.0 AS dist_km
  FROM grid g
  JOIN `{project}.{dataset}.station_forecast` sf USING (city_id)
),
idw AS (
  SELECT
    city_id, cell_lat, cell_lon,
    -- inverse-distance-squared weighting (eps avoids blow-up at a station)
    SAFE_DIVIDE(SUM(current_pm25       / (dist_km*dist_km + 0.01)),
                SUM(1.0 / (dist_km*dist_km + 0.01))) AS current_pm25,
    SAFE_DIVIDE(SUM(pred_max_pm25_24h  / (dist_km*dist_km + 0.01)),
                SUM(1.0 / (dist_km*dist_km + 0.01))) AS pred_max_pm25_24h,
    SAFE_DIVIDE(SUM(breach_prob        / (dist_km*dist_km + 0.01)),
                SUM(1.0 / (dist_km*dist_km + 0.01))) AS breach_prob,
    MIN(dist_km) AS dist_nearest_km
  FROM pairs
  GROUP BY city_id, cell_lat, cell_lon
)
SELECT
  *,
  CASE WHEN pred_max_pm25_24h <= 30 THEN 'Good'
       WHEN pred_max_pm25_24h <= 60 THEN 'Satisfactory'
       WHEN pred_max_pm25_24h <= 90 THEN 'Moderate'
       WHEN pred_max_pm25_24h <= 120 THEN 'Poor'
       WHEN pred_max_pm25_24h <= 250 THEN 'Very Poor' ELSE 'Severe' END AS pred_category,
  -- confidence tiers by distance to nearest station (say it on the map)
  CASE WHEN dist_nearest_km <= 3 THEN 'high'
       WHEN dist_nearest_km <= 7 THEN 'medium' ELSE 'low' END AS confidence,
  CURRENT_TIMESTAMP() AS generated_at
FROM idw;
