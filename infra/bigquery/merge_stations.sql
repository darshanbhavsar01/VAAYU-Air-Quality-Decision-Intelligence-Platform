-- Upsert discovered stations. Keeps the earliest first_seen, refreshes
-- last_seen and coordinates each ingest.
MERGE `{project}.{dataset}.stations` T
USING `{project}.{dataset}._staging_stations` S
ON T.station_id = S.station_id
WHEN MATCHED THEN UPDATE SET
  station = S.station, city_id = S.city_id, state = S.state,
  latitude = COALESCE(S.latitude, T.latitude),
  longitude = COALESCE(S.longitude, T.longitude),
  last_seen = GREATEST(T.last_seen, S.last_seen)
WHEN NOT MATCHED THEN INSERT ROW;
