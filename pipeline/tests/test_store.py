from datetime import UTC, datetime

from meteo.store import day_prefix, name_time, raw_name


def test_raw_names_follow_the_lake_layout():
    when = datetime(2026, 10, 16, 9, 5, 7, tzinfo=UTC)
    name = raw_name("open-meteo", when, "ens-icon_d2_eps", "json.gz")
    assert name == "open-meteo/2026/10/16/20261016T090507Z-ens-icon_d2_eps.json.gz"
    assert name.startswith(day_prefix("open-meteo", when.date()))
    assert name_time(name) == when


def test_a_raw_object_is_written_once(lake):
    assert lake.put_new("raw", "metar/x.json.gz", b"first", "application/gzip", {"a": "1"})
    assert not lake.put_new("raw", "metar/x.json.gz", b"second", "application/gzip")
    assert lake.read("raw", "metar/x.json.gz") == (b"first", {"a": "1"})


def test_names_list_one_container_without_the_metadata(lake):
    lake.put_new("raw", "yr/2026/10/16/b.json.gz", b"", "application/gzip", {"updated_at": "x"})
    lake.put_new("raw", "yr/2026/10/16/a.json.gz", b"", "application/gzip")
    lake.put_new("raw", "yr/2026/10/17/c.json.gz", b"", "application/gzip")
    assert lake.names("raw", "yr/2026/10/16/") == [
        "yr/2026/10/16/a.json.gz",
        "yr/2026/10/16/b.json.gz",
    ]


def test_swap_refuses_a_stale_version(lake):
    assert lake.swap("public", "status.json", b"1", None, "application/json", "")
    _, etag = lake.read_versioned("public", "status.json")
    assert not lake.swap("public", "status.json", b"2", None, "application/json", "")
    assert lake.swap("public", "status.json", b"3", etag, "application/json", "")
    assert not lake.swap("public", "status.json", b"4", etag, "application/json", "")
    assert lake.read_versioned("public", "status.json")[0] == b"3"


def test_a_download_lands_in_the_file(lake, tmp_path):
    lake.put("curated", "nwp_hourly/2026/10/2026-10-20.parquet", b"PAR1", "")
    lake.download("curated", "nwp_hourly/2026/10/2026-10-20.parquet", tmp_path / "a.parquet")
    assert (tmp_path / "a.parquet").read_bytes() == b"PAR1"
