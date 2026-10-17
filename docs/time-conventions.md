# Time conventions

Every time the pipeline stores is UTC: ISO 8601 with a `Z`, or a Parquet timestamp with time zone UTC. Local time, Europe/Rome, is used in two places only: the local-day windows below and the site's display.

A value that covers an interval is stored at the end of that interval. The rules have numbers, T1 to T14, and `pipeline/tests/test_times.py` has a test for each one under the same number. T2 is covered by the tests of T3 and T4, and T14 by the schedule test in `test_function_app.py`.

## ARPA Lombardia

T1. The `data` field of the ARPA datasets is a label in local standard time, UTC+1 all year, with no summer shift ("ora solare" in the live dataset's description). It marks the end of the interval the value covers. The UTC end is the label minus one hour: `2026-07-01T14:10:00.000` ends at 13:10 UTC, and so does `2026-01-15T14:10:00.000` in winter. The history datasets do not state it; compared with the airport METARs over 2025, they follow the same rule (best offset 40 to 50 minutes). Labels therefore never repeat or skip when the clocks change.

T2. A 10-minute value with UTC end E covers (E - 10 min, E]. Operator 1 is the mean over that interval, operator 3 the maximum (the gust, for wind speed) and operator 4 the total (rain). For wind direction, operator 3 is taken to be the direction that goes with the gust; ARPA does not document it.

T3. The rain of the hour ending at H (UTC) is the sum of the six operator-4 values with UTC ends H - 50 min to H, which carry the labels H + 10 min to H + 60 min. The hour counts only if all six are there and none carries MISSING, SOURCE_INVALID, RANGE or SPIKE. Those four flags also keep a value out of the hourly and daily tables; the other flags are information only.

T4. The temperature at H, the value to set against a model's instant at H, is the operator-1 value with UTC end H, which carries the label H + 1 h.

## Open-Meteo

T5. Requests ask for `timezone=GMT`, so `utc_offset_seconds` is 0 and every `time` is UTC. Temperature, dew point, cloud cover, wind speed and direction and sea-level pressure are instants at T. Precipitation and snowfall are totals over (T - 1 h, T], gusts the maximum and shortwave radiation the mean over the same hour, as the hourly variables table at https://open-meteo.com/en/docs says.

T6. A forecast response also carries older runs before the start of the current one. Only valid times from `run_init` on are kept, `run_init` being the `last_run_initialisation_time` read from `meta.json` just before the fetch. The lead in hours is valid time minus `run_init`. best_match has no run: its leads count from the hour it was fetched in.

## METAR

T7. In the JSON of the Aviation Weather Center, `obsTime` is the observation time in epoch seconds, UTC, and the `DDHHMMZ` group of the report says the same. `reportTime` is rounded and is not the observation time. Temperature and dew point are whole degrees Celsius, wind and gusts are knots. `visib` is in statute miles and can be the string `6+`, so visibility in metres is read from the report itself, where `9999` and `CAVOK` mean 10 km or more.

## DWD MOSMIX

T8. `IssueTime` and every forecast step are UTC. Temperatures come in kelvin (degrees Celsius = K - 273.15) and pressure in pascal. `RR1c` is the total over (T - 1 h, T] in kg/m2, which equals millimetres. `TX` is the maximum of 06-18 UTC and has a value on 18:00 steps only; `TN` is the minimum of 18-06 UTC, on 06:00 steps only. `R610` is the probability of more than 1.0 mm in the 6 hours ending at 00, 06, 12 or 18 UTC, `Rd10` the same over the 24 hours ending at the step, on 00:00 and 06:00 steps only. A `-` is a missing value. The element definitions are at https://opendata.dwd.de/weather/lib/MetElementDefinition.xml.

## MET Norway (Yr)

T9. `time` is UTC and `instant` values are at `time`. The precipitation in `next_1_hours` covers [time, time + 1 h) and is stored as the hour ending at time + 1 h, which lines it up with T5; `next_6_hours` is treated the same way, ending at time + 6 h. `properties.meta.updated_at` is the issue time.

## DPC radar

T10. The `time` of a product is its nominal frame time in epoch milliseconds, UTC. The S3 key names the same instant in UTC: 1792095000000 is `SRI/15-10-2026-20-10.tif`. Values are a rain rate in mm/h at that time, and -9999 means no data. DPC does not say whether a frame is one scan or a mean over five minutes.

## Windows and days

T11. Rain over 1 hour is (H - 1 h, H]. Six-hour blocks are UTC blocks ending at 00, 06, 12 and 18, the same as MOSMIX. Local day D takes every interval whose end falls in (D 00:00, D+1 00:00] Europe/Rome. The comparison with MOSMIX also uses the 24 hours ending 00:00 UTC.

T12. The daily extremes of local day D come from the instants or interval ends t with D 00:00 < t <= D+1 00:00 local time. A model gives 24 hourly values, but 23 on 2026-03-29 and 25 on 2026-10-25, when summer time starts and ends at 01:00 UTC. ARPA gives 144 ten-minute values, 138 and 150 on those days. The comparison with MOSMIX uses its own TX over 06-18 UTC and TN over 18-06 UTC. ARPA's daily extremes are taken over 10-minute means and a model's over hourly instants, so both fall a little short of a thermometer's own maximum and minimum, by different amounts. That is one reason the daily maximum and minimum get their own correction.

T13. Rain thresholds include the threshold itself: 0.2 mm for an hour, 1.0 mm for 6 hours and for a day, 10 mm for a day. MOSMIX states its probabilities as more than 1.0 mm, so at exactly 1.0 mm the two differ. ARPA gauges count in steps of 0.2 mm and do reach 1.0 mm exactly; this is noted, not corrected.

T14. Timer schedules are UTC. Flex Consumption supports neither `WEBSITE_TIME_ZONE` nor `TZ` (https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-timer).
