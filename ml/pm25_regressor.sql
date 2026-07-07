-- Secondary model (§6.2): next-24h MAX PM2.5 regressor — drives the map's
-- forecast layer. Global model across all cities (city_id/station_id as
-- features). Temporal integrity: fit on TRAIN, early-stop on VAL, TEST fully
-- held out for our own evaluation (DATA_SPLIT_METHOD=CUSTOM on is_eval).
CREATE OR REPLACE MODEL `{project}.{dataset}.pm25_regressor`
OPTIONS(
  MODEL_TYPE = 'BOOSTED_TREE_REGRESSOR',
  INPUT_LABEL_COLS = ['future_max_pm25'],
  DATA_SPLIT_METHOD = 'CUSTOM',
  DATA_SPLIT_COL = 'is_eval',
  MAX_ITERATIONS = 50,
  EARLY_STOP = TRUE,
  LEARN_RATE = 0.1,
  SUBSAMPLE = 0.85
) AS
SELECT
  * EXCEPT(ts, future_cat, spike, breach, breach_poor, onset, split),
  (split = 'VAL') AS is_eval
FROM `{project}.{dataset}.features`
WHERE split IN ('TRAIN', 'VAL');
