# Verification

This file says which forecasts may be scored, and for what, before the first score of the new site's methods exists. A change to it is a commit of its own that says why.

| Valid time | Use |
| --- | --- |
| 2024-01-20 to 2024-12-31 | Tuning: the window, the lead bands, the minimum number of pairs, the form of the regressions and their predictors are chosen here. |
| 2025-01-01 to 2025-12-31 | Validation: the plan's numbers are reproduced here, the candidate methods compared and the margin of a method change set. |
| 2026-01-01 to 2026-10-16 | Test: scored once, by one script, and not before. |
| From 2026-10-17 | Live: scored as it comes and published, never used to choose a method before the test. |

2024-01-20 is about where Open-Meteo Previous Runs starts for most models. A 60-day window has nothing to learn from in its first 60 days, so the scores of 2024 start in March. 2026-10-17 is the first day the Function collected.

Fitting on 2026 is allowed and scoring it is not. The 60-day correction has to learn from the latest weeks, so the coefficients behind the site's forecasts are fitted partly on days of the test period until 2026-12-16, when the window leaves it. What stays closed is any error, skill or reliability figure of a forecast valid from 2026-01-01 to 2026-10-16, whatever the method, until the test.

The test script, the methods it compares, the margin a new method has to beat and the bootstrap settings are merged before it runs, and it runs once. The date of that merge is the pre-registration.

The scores the site and the verification report publish come from 2024, 2025 and live data from 2026-10-17, and they say which. 2024 and 2025 are out of sample by construction, because each day is corrected with coefficients fitted on the 60 days that ended two days before it. Backfilled forecasts are scored by lead day and never pooled with the forecasts the site issued: Previous Runs day k is timed from the start of the run, not from when the run became available, so it is a few hours fresher than any forecast a live issue can use. A replay of the method from 2026-10-17, made only from the runs and the observations that existed before each issue time, is published as a replay and apart from the issued forecasts, each with its own n.

The nowcast has a split of its own. Its method is chosen on rain events of 2021-2025 from the radar-only SRI archive. It is calibrated on the gauge-adjusted SRI_adj of 2026-05-11 to 2026-08-31 and tested on SRI_adj from 2026-09-01 on, live frames included.
