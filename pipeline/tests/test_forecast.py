import gzip
import json
from datetime import UTC, date, datetime, timedelta

from conftest import fixture

from meteo import forecast, mos, openmeteo
from meteo.contract import Forecast
from meteo.forecast import ModelRun

POINT = "torre-boldone"
ISSUED = datetime(2026, 10, 20, 6, 41, 7, tzinfo=UTC)
INIT = datetime(2026, 10, 20, 3, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)


def model_run(model: str, init: datetime = INIT, hours: int = 288, skip=(), **values) -> ModelRun:
    rows = {}
    for k in range(hours):
        valid = init + k * HOUR
        if valid in skip:
            continue
        row = {v: 0.0 for v in openmeteo.VARIABLES} | {"temperature_2m": 10.0}
        row |= {v: f(valid) if callable(f) else f for v, f in values.items()}
        rows[(POINT, valid)] = row
    return ModelRun(model, init, rows)


def biases(model: str, bias: float, pairs: int = 60) -> dict:
    cells = {(POINT, model, "t2m", b, h): (bias, pairs) for b in range(8) for h in range(24)}
    for variable in ("tmax", "tmin"):
        cells |= {(POINT, model, variable, b, None): (bias + b / 10, pairs) for b in range(8)}
    return cells


def coefficients(*cells: dict) -> mos.Coefficients:
    return mos.Coefficients(ISSUED.date(), {k: v for c in cells for k, v in c.items()})


def issue(runs, coeffs) -> forecast.Issue:
    return forecast.Issue(runs, coeffs, POINT, ISSUED)


def test_each_model_is_corrected_with_its_own_bias_before_the_mean():
    runs = [model_run("icon_d2", temperature_2m=10.0), model_run("ecmwf_ifs", temperature_2m=13.0)]
    t = issue(runs, coefficients(biases("icon_d2", 1.0), biases("ecmwf_ifs", -1.0)))
    temperature = t.hourly().temperature_c
    assert (temperature.mean[0], temperature.low[0], temperature.high[0]) == (11.5, 9.0, 14.0)
    assert temperature.m_models[0] == 2
    assert temperature.corrected


def test_a_model_with_too_few_pairs_stays_out_of_the_temperature_only():
    runs = [model_run("icon_d2", wind_speed_10m=2.0), model_run("ecmwf_ifs", wind_speed_10m=4.0)]
    t = issue(runs, coefficients(biases("icon_d2", 0.0), biases("ecmwf_ifs", 0.0, pairs=44)))
    hourly = t.hourly()
    assert hourly.temperature_c.m_models[0] == 1
    assert hourly.wind_kmh.mean[0] == 10.8


def test_without_coefficients_no_raw_temperature_goes_out_as_corrected():
    hourly = issue([model_run("icon_d2", wind_speed_10m=3.0)], None).hourly()
    assert hourly.temperature_c.corrected
    assert set(hourly.temperature_c.mean) == {None}
    assert hourly.wind_kmh.mean[0] == 10.8


def test_the_lead_band_is_the_highest_among_the_models_in_the_mean():
    older = INIT - timedelta(hours=30)
    runs = [model_run("icon_d2"), model_run("ecmwf_ifs", init=older, hours=320)]
    hourly = issue(runs, coefficients(biases("icon_d2", 0), biases("ecmwf_ifs", 0))).hourly()
    assert hourly.temperature_c.lead_band[0] == 1
    assert hourly.temperature_c.lead_band[-1] == 3


def test_the_hours_start_at_the_first_whole_hour_after_the_issue():
    hourly = issue([model_run("icon_d2")], None).hourly()
    assert len(hourly.time) == 49
    assert (hourly.time[0], hourly.time[-1]) == (
        datetime(2026, 10, 20, 7, tzinfo=UTC),
        datetime(2026, 10, 22, 7, tzinfo=UTC),
    )


def test_the_wind_direction_is_that_of_the_mean_wind():
    runs = [
        model_run("icon_d2", wind_speed_10m=5.0, wind_direction_10m=350.0),
        model_run("ecmwf_ifs", wind_speed_10m=5.0, wind_direction_10m=10.0),
    ]
    assert issue(runs, None).hourly().wind_dir_deg.mean[0] == 0.0


def test_hourly_rain_counts_the_models_with_at_least_a_fifth_of_a_millimetre():
    runs = [
        model_run("icon_d2", precipitation=0.2),
        model_run("ecmwf_ifs", precipitation=0.1),
        model_run("gfs_global", precipitation=None),
    ]
    rain = issue(runs, None).hourly().rain
    assert (rain.n_models[0], rain.m_models[0]) == (1, 2)


def test_a_model_missing_an_hour_of_a_day_is_left_out_of_that_day():
    gap = forecast.local_hours(date(2026, 10, 21))[5]
    runs = [model_run("icon_d2"), model_run("ecmwf_ifs", skip={gap})]
    daily = issue(runs, coefficients(biases("icon_d2", 0), biases("ecmwf_ifs", 0))).daily()
    assert daily.tmax_c.m_models[:2] == [1, 2]
    assert daily.rain.m_models[:2] == [1, 2]


def test_days_eight_to_ten_take_the_day_seven_bias():
    daily = issue([model_run("gfs_global")], coefficients(biases("gfs_global", 1.0))).daily()
    assert daily.day[0] == date(2026, 10, 21)
    assert daily.tmax_c.lead_band == [1, 2, 3, 4, 5, 6, 7, 7, 7, 7]
    assert daily.tmax_c.mean == [8.9, 8.8, 8.7, 8.6, 8.5, 8.4, 8.3, 8.3, 8.3, 8.3]


def test_a_day_of_tenths_reaches_one_millimetre():
    wet = set(forecast.local_hours(date(2026, 10, 21))[:3])
    amounts = iter([0.3, 0.3, 0.4])
    runs = [model_run("icon_d2", precipitation=lambda t: next(amounts) if t in wet else 0.0)]
    daily = issue(runs, None).daily()
    assert (daily.rain.n_models[0], daily.precipitation_mm.mean[0]) == (1, 1.0)


def test_local_days_have_their_own_number_of_hours():
    days = [date(2026, 3, 29), date(2026, 10, 20), date(2026, 10, 25)]
    assert [len(forecast.local_hours(d)) for d in days] == [23, 24, 25]


def test_the_issue_is_kept_before_it_is_published(lake, all_towns):
    run_init = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)
    metadata = {
        "run_init": run_init.isoformat(),
        "run_available": (run_init + timedelta(hours=2)).isoformat(),
        "fetched_at": (run_init + timedelta(hours=3)).isoformat(),
        "points": "torre-boldone,lime,ispra-jrc,varano-borghi",
    }
    raw = gzip.compress(fixture("open-meteo/forecast-icon_d2-run.json"))
    name = "open-meteo/2026/10/16/20261016T090000Z-icon_d2.json.gz"
    lake.put_new("raw", name, raw, "application/gzip", metadata)
    rows = [
        [p, "icon_d2", "t2m", b, h, 0.5, 60]
        for p in ("torre-boldone", "ispra-jrc")
        for b in range(8)
        for h in range(24)
    ]
    body = {"method": "mean60-v1", "day": "2026-10-16", "window": [], "min_pairs": 45}
    body |= {"columns": mos.COLUMNS, "rows": rows}
    lake.put("curated", mos.name(date(2026, 10, 16)), json.dumps(body).encode(), "")

    now = datetime(2026, 10, 16, 11, 45, 3, tzinfo=UTC)
    forecast.publish(lake, lake, all_towns, now)

    for town in all_towns:
        published, _ = lake.read_versioned("public", f"v1/{town.slug}/forecast.json")
        kept, _ = lake.read(
            "forecasts", f"v1/{town.slug}/2026/10/16/20261016T114503Z-forecast.json"
        )
        assert kept == published
        file = Forecast.model_validate_json(published)
        assert [(r.model, r.run_init) for r in file.models] == [("icon_d2", run_init)]
        raw_t = next(
            r["temperature_2m"]
            for r in openmeteo.hourly_rows(raw, metadata, "icon_d2")
            if r["point"] == town.reference.id and r["valid"] == file.hourly.time[0]
        )
        assert file.hourly.temperature_c.mean[0] == round(raw_t - 0.5, 1)
