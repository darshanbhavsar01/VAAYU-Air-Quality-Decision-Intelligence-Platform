-- raw_weather: one row per city point × hour, from Open-Meteo.
-- Weather is fetched at the city centroid (Phase 1 simplification — all stations
-- in a city share it; documented in docs/LIMITATIONS.md). Key: (city_id, ts).
-- Covers both live/forecast (open_meteo) and 90-day archive backfill (open_meteo_archive).
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.raw_weather` (
  city_id              STRING   NOT NULL,
  latitude             FLOAT64,
  longitude            FLOAT64,
  ts                   TIMESTAMP NOT NULL,  -- UTC
  temperature_2m       FLOAT64,
  relative_humidity_2m FLOAT64,
  wind_speed_10m       FLOAT64,
  wind_direction_10m   FLOAT64,
  precipitation        FLOAT64,
  surface_pressure     FLOAT64,
  is_forecast          BOOL,                -- TRUE for future hours from the forecast API
  source               STRING,              -- 'open_meteo' | 'open_meteo_archive'
  ingested_at          TIMESTAMP NOT NULL
)
PARTITION BY DATE(ts)
CLUSTER BY city_id
OPTIONS (description = 'Raw hourly weather per city centroid (Open-Meteo forecast + archive)');

CREATE TABLE IF NOT EXISTS `{project}.{dataset}._staging_raw_weather`
LIKE `{project}.{dataset}.raw_weather`;
