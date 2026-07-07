-- Upsert staged CAMS rows into aqi_cams on (station_id, ts). Idempotent.
MERGE `{project}.{dataset}.aqi_cams` T
USING `{project}.{dataset}._staging_aqi_cams` S
ON T.station_id = S.station_id AND T.ts = S.ts
WHEN MATCHED THEN UPDATE SET
  city_id = S.city_id, latitude = S.latitude, longitude = S.longitude,
  pm2_5 = S.pm2_5, pm10 = S.pm10,
  nitrogen_dioxide = S.nitrogen_dioxide, sulphur_dioxide = S.sulphur_dioxide,
  ozone = S.ozone, carbon_monoxide = S.carbon_monoxide,
  source = S.source, ingested_at = S.ingested_at
WHEN NOT MATCHED THEN INSERT ROW;
