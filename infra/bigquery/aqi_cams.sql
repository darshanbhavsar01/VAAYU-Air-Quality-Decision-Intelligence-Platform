-- aqi_cams: MODELLED hourly air quality from CAMS (ECMWF), via Open-Meteo, at
-- each CPCB station's real coordinates. This is the training-history backbone
-- for the forecast models (CPCB has no historical API — see docs/LIMITATIONS.md).
--
-- Kept in a SEPARATE table from raw_aqi with an explicit source label so CAMS
-- (model) is NEVER silently conflated with CPCB (ground-truth measurement).
-- As real CPCB history accrues in raw_aqi we cross-validate the two.
-- Units: µg/m³ (pm2_5, pm10, NO2, SO2, O3), CO in µg/m³ as returned by CAMS.
-- Key: (station_id, ts).
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.aqi_cams` (
  city_id           STRING   NOT NULL,
  station_id        STRING   NOT NULL,
  latitude          FLOAT64,
  longitude         FLOAT64,
  ts                TIMESTAMP NOT NULL,  -- UTC
  pm2_5             FLOAT64,
  pm10              FLOAT64,
  nitrogen_dioxide  FLOAT64,
  sulphur_dioxide   FLOAT64,
  ozone             FLOAT64,
  carbon_monoxide   FLOAT64,
  source            STRING,              -- 'cams_openmeteo'
  ingested_at       TIMESTAMP NOT NULL
)
PARTITION BY DATE(ts)
CLUSTER BY city_id, station_id
OPTIONS (description = 'CAMS-modelled hourly pollutants at CPCB station locations (training history; NOT CPCB measurement)');

CREATE TABLE IF NOT EXISTS `{project}.{dataset}._staging_aqi_cams`
LIKE `{project}.{dataset}.aqi_cams`;
