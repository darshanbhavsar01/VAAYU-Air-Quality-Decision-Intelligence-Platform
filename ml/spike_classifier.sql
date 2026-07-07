-- Primary model (§6.2): 24h "breach safe limits" classifier. Target = `breach`
-- = PM2.5 max exceeds India's NAAQS 24h standard (60 µg/m³) within 24h — the
-- actionable event the pitch promises. Chosen over §6.1's Poor=90 (all-zero for
-- clean southern cities incl. Bengaluru) and the §6.1 union label (~60% of hours,
-- too common). Data-driven justification in docs/EVALUATION.md — not tuned to
-- flatter (a commoner target makes the persistence baseline HARDER to beat).
--
-- Global model across all cities (city_id/station_id as features so it learns
-- Delhi's chronic-severe vs Bengaluru's clean baselines). Class imbalance handled
-- by AUTO_CLASS_WEIGHTS. Temporal integrity: fit TRAIN, early-stop VAL, TEST held
-- out (CUSTOM split on is_eval).
CREATE OR REPLACE MODEL `{project}.{dataset}.spike_classifier`
OPTIONS(
  MODEL_TYPE = 'BOOSTED_TREE_CLASSIFIER',
  INPUT_LABEL_COLS = ['breach'],
  AUTO_CLASS_WEIGHTS = TRUE,
  DATA_SPLIT_METHOD = 'CUSTOM',
  DATA_SPLIT_COL = 'is_eval',
  MAX_ITERATIONS = 50,
  EARLY_STOP = TRUE,
  LEARN_RATE = 0.1,
  SUBSAMPLE = 0.85
) AS
SELECT
  * EXCEPT(ts, future_max_pm25, future_cat, spike, breach_poor, onset, split),
  (split = 'VAL') AS is_eval
FROM `{project}.{dataset}.features`
WHERE split IN ('TRAIN', 'VAL');
