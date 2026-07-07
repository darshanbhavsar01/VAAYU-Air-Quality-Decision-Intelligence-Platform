-- raw_aqi: one row per station × pollutant × hour, from CPCB (data.gov.in).
-- Natural key for idempotency: (city_id, station_id, pollutant, ts).
-- ts stored in UTC (CPCB last_update is IST; the ingest layer converts).
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.raw_aqi` (
  city_id      STRING   NOT NULL,
  station_id   STRING   NOT NULL,  -- stable slug of station name
  station      STRING   NOT NULL,  -- full CPCB station name
  state        STRING,
  latitude     FLOAT64,
  longitude    FLOAT64,
  pollutant    STRING   NOT NULL,  -- PM2.5, PM10, NO2, SO2, CO, OZONE, NH3
  ts           TIMESTAMP NOT NULL, -- reading time (UTC)
  min_value    FLOAT64,
  max_value    FLOAT64,
  avg_value    FLOAT64,
  source       STRING,             -- e.g. 'cpcb_datagovin'
  ingested_at  TIMESTAMP NOT NULL
)
PARTITION BY DATE(ts)
CLUSTER BY city_id, station_id, pollutant
OPTIONS (description = 'Raw CPCB station pollutant readings, hourly, nationwide (city_id partitioned by ingest)');

-- Staging table for the load->MERGE idempotency pattern (truncated each job).
CREATE TABLE IF NOT EXISTS `{project}.{dataset}._staging_raw_aqi`
LIKE `{project}.{dataset}.raw_aqi`;
