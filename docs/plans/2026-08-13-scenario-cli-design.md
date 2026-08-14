# Scenario CLI design

**Date:** 2026-08-13  
**Status:** Approved (user: command, start + ban + compare)  
**Not AT-12.** A what-if runner on the typed Temple tables.

## Command

```
stewardsim scenario --year 2025 --bug ecoli --drug cipro --ban 100
stewardsim scenario --year 2024 --bug ecoli --drug cipro --ban none
```

## Knobs (v1)

| Flag | Meaning |
|------|---------|
| `--year` | 2017, 2024, or 2025 |
| `--bug` | alias or printed organism name |
| `--drug` | alias or printed drug name |
| `--ban` | `none` or start day (integer). Ban lasts to the end of the run. |
| `--s-max` | optional. Default **0.02** so a day-100 ban can still move the line. Printed every time. |

Always run a **no-ban twin** with the same seed, size, and start.

2017 looks up `campus_id=TUH`. 2024/2025 look up `TUH-Main`.

## Output

Folder `output/scenario/<id>/` with `ban/` (or `none/`) and `control/`, plus `compare.txt`.

Print: start cell, starting % resistant, s_max, ban, end % with/without ban, difference, cipro-equivalent dose-days after the ban day.

If resistance is already > 0.99 before the ban day, print a warning.

## Out of scope

Website, AT-12, inventing a Temple restriction date, extra knobs (fidelity, n, years) in v1.
