-- Upsert staged weather into raw_weather on (city_id, ts).
-- Archive backfill and live/forecast pulls converge here; a later real
-- observation overwrites an earlier forecast for the same hour.
MERGE `{project}.{dataset}.raw_weather` T
USING `{project}.{dataset}._staging_raw_weather` S
ON T.city_id = S.city_id AND T.ts = S.ts
WHEN MATCHED THEN UPDATE SET
  latitude = S.latitude, longitude = S.longitude,
  temperature_2m = S.temperature_2m,
  relative_humidity_2m = S.relative_humidity_2m,
  wind_speed_10m = S.wind_speed_10m,
  wind_direction_10m = S.wind_direction_10m,
  precipitation = S.precipitation,
  surface_pressure = S.surface_pressure,
  is_forecast = S.is_forecast,
  source = S.source, ingested_at = S.ingested_at
WHEN NOT MATCHED THEN INSERT ROW;
