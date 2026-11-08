# Phase 1 scorecard

Gate: **OPEN**  
Run: 2026-11-08T01:42:55.023025+00:00

| check | tier | value | threshold | status | note |
|---|---|---|---|---|---|
| 6+ historical seasons loaded | CRITICAL | 7 | >= 6 | PASS | 2019-20,2020-21,2021-22,2022-23,2023-24,2024-25,2025-26 |
| Every scheduled GW present per season (2019/20 remapped) | CRITICAL | 8/8 seasons complete | all seasons | PASS |  |
| Rerun ingest = identical row counts + file hashes | CRITICAL | 34 files, 0 differ, rows_equal=True | 0 differ | PASS |  |
| Raw saved as parquet in data/raw/, rows match manifest | CRITICAL | 33 parquet files ok, bad=0, stray_csv=0 | 0 bad | PASS |  |
| Live API: bootstrap-static, fixtures, element-summary, event live OK | CRITICAL | elements=671 fixtures=380 history=10 live=670 | all 4 endpoints return data | PASS |  |
| Rate limit (>=1 s/host) + disk cache in place | CRITICAL | delay_cfg=1.0s two_calls=1.59s cache_hit=True | >= 1.0 s, cache hit | PASS |  |
| Snapshot current GW matches live FPL site | PASS | snapshot=10 site=10 | equal | PASS |  |
| Per-season player counts in plausible range | PASS | min=666 max=865 | 550-950 | PASS | out_of_range={} outliers(/z/>1.5)=[] |
| xG/xA coverage where source has it | GOOD | 1.0 | >= 0.90 | PASS | 2022-23=1.000 2023-24=1.000 2024-25=1.000 2025-26=1.000 2026-27=1.000 |
| Data source choice justified in DECISIONS.md | GOOD | rows=2 why_len=153 | row present, reason > 40 chars | PASS |  |
