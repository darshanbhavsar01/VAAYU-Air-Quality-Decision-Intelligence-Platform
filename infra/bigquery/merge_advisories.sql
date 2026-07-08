-- Upsert advisories on (city_id, lang). Upsert (not truncate) so a partial
-- run — some languages failing on a flaky/rate-limited model — never wipes the
-- advisories that succeeded on earlier runs. Runs accumulate coverage.
MERGE `{project}.{dataset}.advisories` T
USING `{project}.{dataset}._staging_advisories` S
ON T.city_id = S.city_id AND T.lang = S.lang
WHEN MATCHED THEN UPDATE SET
  as_of = S.as_of, category = S.category, headline = S.headline,
  body = S.body, health_actions = S.health_actions,
  model = S.model, generated_at = S.generated_at
WHEN NOT MATCHED THEN INSERT ROW;
