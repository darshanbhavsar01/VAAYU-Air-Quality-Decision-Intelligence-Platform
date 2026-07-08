-- Tables the three ADK agents (sentinel, oracle, vaani) read/write.
-- No agent writes to raw_* tables (CLAUDE.md §7); these are their own surfaces.

-- vaani citizen advisories, per city × language. Regenerated as a set
-- (WRITE_TRUNCATE) each run, grounded ONLY in the forecast JSON passed to Gemini.
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.advisories` (
  city_id        STRING NOT NULL,
  lang           STRING NOT NULL,   -- en, hi, kn, mr, ta, bn, te
  as_of          TIMESTAMP,         -- forecast timestamp the advisory is grounded on
  category       STRING,            -- forecast PM2.5 category
  headline       STRING,
  body           STRING,
  health_actions STRING,
  model          STRING,
  generated_at   TIMESTAMP NOT NULL
)
CLUSTER BY city_id
OPTIONS (description = 'vaani citizen advisories per city×language (Gemini Flash, grounded in forecast)');

CREATE TABLE IF NOT EXISTS `{project}.{dataset}._staging_advisories`
LIKE `{project}.{dataset}.advisories`;

-- Audit + call-volume log for every Gemini call (§7 — track free-tier usage).
-- key_name records WHICH AI Studio account served the call (primary/fallback1/
-- fallback2) — lets us see the model+account fallback cascade in action.
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.agent_logs` (
  agent          STRING NOT NULL,   -- sentinel | oracle | vaani
  task           STRING,            -- advisory | ask | report
  model          STRING,
  key_name       STRING,            -- primary | fallback1 | fallback2
  city_id        STRING,
  lang           STRING,
  prompt_chars   INT64,
  response_chars INT64,
  latency_ms     INT64,
  ok             BOOL,
  error          STRING,
  ts             TIMESTAMP NOT NULL
)
PARTITION BY DATE(ts)
OPTIONS (description = 'Audit log of all Gemini/agent calls (grounding + free-tier volume + fallback-chain tracking)');

-- vaani weekly MP hotspot report (Gemini Pro), rendered HTML per city.
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.reports` (
  city_id      STRING NOT NULL,
  generated_at TIMESTAMP NOT NULL,
  html         STRING,
  model        STRING
)
CLUSTER BY city_id
OPTIONS (description = 'vaani weekly MP hotspot reports (HTML, Gemini Pro)');

-- sentinel station-health surface: freshness + simple anomaly flags.
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.station_health` (
  city_id     STRING NOT NULL,
  station_id  STRING NOT NULL,
  station     STRING,
  latest_ts   TIMESTAMP,
  age_hours   FLOAT64,
  stale       BOOL,        -- > 3h since last reading
  latest_pm25 FLOAT64,
  zscore      FLOAT64,     -- vs the station's recent distribution
  anomaly     BOOL,        -- |z| high without an obvious weather cause
  note        STRING,
  updated_at  TIMESTAMP NOT NULL
)
CLUSTER BY city_id
OPTIONS (description = 'sentinel agent: per-station feed freshness + anomaly flags');
