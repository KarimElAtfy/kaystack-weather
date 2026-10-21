import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from meteo import contract
from meteo.contract import Forecast, Metar, Now, Radar, RadarAtTown, Status, View

SCHEMA = Path(__file__).resolve().parents[2] / "schema"

FORECAST = {
    "schema": "forecast/1",
    "license": "CC BY-SA 4.0",
    "attribution": "Weather data by Open-Meteo.com (CC BY 4.0)",
    "generated_at": "2026-10-20T06:41:07Z",
    "town": "pedrengo",
    "issued_at": "2026-10-20T06:00:00Z",
    "method": "mean60-v1",
    "models": [
        {"model": "icon_d2", "run_init": "2026-10-20T03:00:00Z"},
        {"model": "ecmwf_ifs", "run_init": "2026-10-20T00:00:00Z"},
    ],
    "stale_after_min": 180,
    "expired_after_min": 1440,
    "hourly": {
        "time": ["2026-10-20T06:00:00Z", "2026-10-20T07:00:00Z", "2026-10-20T08:00:00Z"],
        "temperature_c": {
            "corrected": True,
            "mean": [9.4, 10.1, None],
            "low": [8.9, 9.6, None],
            "high": [9.9, 10.5, None],
            "m_models": [2, 2, 0],
            "lead_band": [0, 0, 0],
        },
        "dew_point_c": {"corrected": False, "mean": [8.2, 8.6, 8.9]},
        "wind_kmh": {"corrected": False, "mean": [4.3, 5.0, 6.8]},
        "wind_dir_deg": {"corrected": False, "mean": [40.0, 55.0, 70.0]},
        "gust_kmh": {"corrected": False, "mean": [9.0, 11.2, 14.4]},
        "cloud_pct": {"corrected": False, "mean": [100.0, 96.0, 88.0]},
        "precipitation_mm": {"corrected": False, "mean": [0.3, 0.1, 0.0]},
        "rain": {"threshold_mm": 0.2, "n_models": [2, 1, 0], "m_models": [2, 2, 2]},
    },
    "daily": {
        "day": ["2026-10-21", "2026-10-28"],
        "tmax_c": {
            "corrected": True,
            "mean": [17.2, 15.0],
            "low": [16.1, 13.8],
            "high": [18.0, 15.9],
            "m_models": [2, 1],
            "lead_band": [1, 7],
        },
        "tmin_c": {
            "corrected": True,
            "mean": [7.8, 6.1],
            "low": [7.0, 6.1],
            "high": [8.4, 6.1],
            "m_models": [2, 1],
            "lead_band": [1, 7],
        },
        "rain": {"threshold_mm": 1.0, "n_models": [0, 1], "m_models": [2, 1]},
        "cloud_pct": {"corrected": False, "mean": [62.0, 40.5]},
        "precipitation_mm": {"corrected": False, "mean": [0.4, 3.1]},
        "wind_max_kmh": {"corrected": False, "mean": [14.0, 22.3]},
        "gust_max_kmh": {"corrected": False, "mean": [31.5, None]},
    },
}

RADAR = {
    "schema": "radar/1",
    "license": "CC BY-SA 4.0",
    "attribution": "Radar-DPC",
    "generated_at": "2026-10-20T06:47:31Z",
    "town": "pedrengo",
    "encoding": "class-grey9/1",
    "sprite": "radar-20261020T0640Z.webp",
    "frame_width_px": 120,
    "frame_height_px": 120,
    "columns": 4,
    "frames": [
        {"time": "2026-10-20T06:30:00Z", "missing": False},
        {"time": "2026-10-20T06:35:00Z", "missing": True},
        {"time": "2026-10-20T06:40:00Z", "missing": False},
    ],
    "view": {"west": -275000, "east": -155000, "south": 354000, "north": 474000},
    "km_per_px": 1.0,
    "town_px": {"x": 60, "y": 60},
    "scale": [
        {"index": 1, "from_mm_h": 0.2, "to_mm_h": 1.0},
        {"index": 2, "from_mm_h": 1.0, "to_mm_h": 2.0},
        {"index": 3, "from_mm_h": 2.0, "to_mm_h": 6.0},
        {"index": 4, "from_mm_h": 6.0, "to_mm_h": 15.0},
        {"index": 5, "from_mm_h": 15.0, "to_mm_h": 40.0},
        {"index": 6, "from_mm_h": 40.0, "to_mm_h": None},
    ],
}


def forecast_with(path: str, value) -> dict:
    data = copy.deepcopy(FORECAST)
    *parents, last = path.split(".")
    node = data
    for key in parents:
        node = node[key]
    node[last] = value
    return data


def test_committed_schemas_match_the_models():
    committed = {p.name: p.read_text(encoding="utf-8") for p in SCHEMA.glob("*.json")}
    assert committed == contract.schemas(), "regenerate: uv run python -m meteo.contract ../schema"


def test_a_forecast_reads_back_as_written():
    body = Forecast.model_validate(FORECAST).model_dump_json()
    assert json.loads(body) == FORECAST


def test_a_radar_file_reads_back_as_written():
    assert json.loads(Radar.model_validate(RADAR).model_dump_json()) == RADAR


def test_the_radar_view_has_the_town_files_bounds(all_towns):
    for town in all_towns:
        assert View(**town.radar_view).model_dump() == town.radar_view


def test_a_frame_that_does_not_cover_the_view_is_refused():
    with pytest.raises(ValidationError, match=r"the view is 80\.0 x 80\.0 px at 1\.5 km"):
        Radar.model_validate({**RADAR, "km_per_px": 1.5})


def test_rain_classes_must_meet_end_to_end():
    scale = copy.deepcopy(RADAR["scale"])
    scale[1]["from_mm_h"] = 1.5
    with pytest.raises(ValidationError, match=r"class 1 ends at 1\.0, not 1\.5"):
        Radar.model_validate({**RADAR, "scale": scale})


def test_the_site_thresholds_are_written_without_being_passed():
    data = copy.deepcopy(FORECAST)
    del data["stale_after_min"], data["expired_after_min"]
    forecast = Forecast.model_validate(data)
    assert (forecast.stale_after_min, forecast.expired_after_min) == (180, 1440)
    assert Metar.model_fields["stale_after_min"].default == 90
    assert RadarAtTown.model_fields["stale_after_min"].default == 15


def test_times_are_written_in_utc_to_the_second():
    status = Status(
        license="CC BY-SA 4.0",
        attribution="Radar-DPC",
        generated_at="2026-10-20T08:41:07.532+02:00",
        sources={},
    )
    assert json.loads(status.model_dump_json())["generated_at"] == "2026-10-20T06:41:07Z"


def test_a_time_without_a_zone_is_refused():
    with pytest.raises(ValidationError, match="timezone"):
        Forecast.model_validate(forecast_with("issued_at", "2026-10-20T06:00:00"))


def test_a_series_one_step_short_is_refused():
    with pytest.raises(ValidationError, match="mean has 2 values for 3 steps"):
        Forecast.model_validate(forecast_with("hourly.wind_kmh.mean", [4.3, 5.0]))


def test_more_rainy_models_than_models_is_refused():
    with pytest.raises(ValidationError, match="2 rainy models of 1"):
        Forecast.model_validate(forecast_with("daily.rain.n_models", [0, 2]))


def test_a_mean_outside_the_range_between_models_is_refused():
    with pytest.raises(ValidationError, match=r"mean 19.0 outside 16.1 to 18.0"):
        Forecast.model_validate(forecast_with("daily.tmax_c.mean", [19.0, 15.0]))


def test_a_null_step_with_models_behind_it_is_refused():
    with pytest.raises(ValidationError, match="m_models 1 with mean None"):
        Forecast.model_validate(forecast_with("hourly.temperature_c.m_models", [2, 2, 1]))


def test_a_value_with_no_model_behind_it_is_refused():
    with pytest.raises(ValidationError, match=r"mean 15\.0 with m_models 0"):
        Forecast.model_validate(forecast_with("daily.tmax_c.m_models", [2, 0]))


def test_a_daily_lead_band_counts_the_days_after_the_issue():
    with pytest.raises(ValidationError, match="lead band 6 on 2026-10-28, 8 days after"):
        Forecast.model_validate(forecast_with("daily.tmax_c.lead_band", [1, 6]))


def test_a_winter_issue_at_23_45z_counts_from_the_next_local_day():
    late = forecast_with("issued_at", "2026-12-01T23:45:00Z")
    late["daily"]["day"] = ["2026-12-03", "2026-12-10"]
    Forecast.model_validate(late)

    late["daily"]["day"] = ["2026-12-02", "2026-12-09"]
    with pytest.raises(ValidationError, match="2026-12-02 is 0 days after the issue"):
        Forecast.model_validate(late)


def test_a_lead_band_past_day_7_is_refused():
    with pytest.raises(ValidationError, match="less than or equal to 7"):
        Forecast.model_validate(forecast_with("daily.tmin_c.lead_band", [1, 8]))


def test_town_files_sit_under_v1_and_status_stays_at_the_root():
    assert {name: model.path("pedrengo") for name, model in contract.FILES.items()} == {
        "status": "status.json",
        "now": "v1/pedrengo/now.json",
        "radar": "v1/pedrengo/radar.json",
        "forecast": "v1/pedrengo/forecast.json",
    }


NOW = {
    "schema": "now/1",
    "license": "CC BY-SA 4.0",
    "attribution": "NOAA Aviation Weather Center",
    "generated_at": "2026-10-16T12:07:12Z",
    "town": "pedrengo",
    "reference": {"name": "Torre Boldone", "distance_km": 3.4},
    "metar": {
        "icao": "LIME",
        "name": "Bergamo Orio al Serio",
        "distance_km": 3.6,
        "observed_at": "2026-10-16T11:50:00Z",
        "temperature_c": 20.0,
        "dew_point_c": 14.0,
        "wind_kmh": 5.6,
        "wind_dir_deg": None,
        "gust_kmh": None,
        "visibility_m": 6000,
        "weather": None,
        "stale_after_min": 90,
    },
    "radar": None,
}


def test_a_now_file_from_before_the_raw_report_still_reads():
    metar = Now.model_validate(NOW).metar
    assert metar is not None
    assert (metar.raw, metar.cloud_cover) == (None, None)


def test_an_unknown_cloud_code_is_refused():
    with pytest.raises(ValidationError, match="cloud_cover"):
        Metar.model_validate({**NOW["metar"], "cloud_cover": "BROKEN"})


def test_a_field_added_to_v1_is_optional_in_the_schema():
    metar = json.loads(contract.schemas()["now.schema.json"])["$defs"]["Metar"]
    assert {"raw", "cloud_cover"} <= set(metar["properties"])
    assert not {"raw", "cloud_cover"} & set(metar["required"])
    assert "observed_at" in metar["required"]
    daily = json.loads(contract.schemas()["forecast.schema.json"])["$defs"]["Daily"]
    assert daily["required"] == ["day", "tmax_c", "tmin_c", "rain"]


def test_a_daily_amount_one_day_short_is_refused():
    with pytest.raises(ValidationError, match="mean has 1 values for 2 steps"):
        Forecast.model_validate(forecast_with("daily.precipitation_mm.mean", [0.4]))
