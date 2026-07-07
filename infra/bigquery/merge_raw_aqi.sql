-- Upsert staged CPCB readings into raw_aqi on the natural key.
-- Re-running an ingest with the same hour is a no-op update, never a duplicate.
MERGE `{project}.{dataset}.raw_aqi` T
USING `{project}.{dataset}._staging_raw_aqi` S
ON  T.city_id = S.city_id
AND T.station_id = S.station_id
AND T.pollutant = S.pollutant
AND T.ts = S.ts
WHEN MATCHED THEN UPDATE SET
  station = S.station, state = S.state,
  latitude = S.latitude, longitude = S.longitude,
  min_value = S.min_value, max_value = S.max_value, avg_value = S.avg_value,
  source = S.source, ingested_at = S.ingested_at
WHEN NOT MATCHED THEN INSERT ROW;
