-- stations: dimension table of monitoring stations discovered from CPCB.
-- Upserted every ingest (last_seen + coords refreshed). Drives interpolation
-- (station point set per city) and station-health (sentinel agent). Key: station_id.
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.stations` (
  station_id   STRING   NOT NULL,
  station      STRING   NOT NULL,
  city_id      STRING   NOT NULL,
  state        STRING,
  latitude     FLOAT64,
  longitude    FLOAT64,
  first_seen   TIMESTAMP NOT NULL,
  last_seen    TIMESTAMP NOT NULL
)
CLUSTER BY city_id, station_id
OPTIONS (description = 'Station registry discovered from CPCB feed; one row per station');

CREATE TABLE IF NOT EXISTS `{project}.{dataset}._staging_stations`
LIKE `{project}.{dataset}.stations`;
