import gzip
import json
from datetime import UTC, datetime

import pytest
from conftest import fixture

from meteo import now, radar
from meteo.contract import Now
from meteo.store import raw_name

PULLED = datetime(2026, 10, 16, 12, 7, tzinfo=UTC)
FRAME = datetime(2026, 10, 15, 17, 0, tzinfo=UTC)
REFERENCE = fixture("radar/SRI_15-10-2026-17-00.crop.u16.zlib")


def town(all_towns, slug):
    return next(t for t in all_towns if t.slug == slug)


def read_now(lake, slug) -> dict:
    return json.loads(lake.read_versioned("public", f"v1/{slug}/now.json")[0])


def store_pull(lake):
    body = gzip.compress(fixture("metar/awc-metar-sample.json"))
    lake.put_new("raw", raw_name("metar", PULLED, "awc", "json.gz"), body, "application/gzip")


@pytest.mark.parametrize(
    ("slug", "reference", "airport"),
    [("pedrengo", 3.4, 4.3), ("sesto-calende", 9.1, 12.5)],
)
def test_distances_are_haversine_from_the_town_centre(all_towns, slug, reference, airport):
    t = town(all_towns, slug)
    assert now.distance_km(t.lat, t.lon, t.reference.lat, t.reference.lon) == reference
    assert now.distance_km(t.lat, t.lon, t.airport.lat, t.airport.lon) == airport


@pytest.mark.parametrize(
    ("report", "cover"),
    [
        ("METAR LIMC 161150Z 22005KT 190V270 5000 BR BKN020 19/13 Q1021 NOSIG", "BKN"),
        ("METAR LIME 161150Z VRB03KT 6000 NSC 20/14 Q1021 NOSIG", "NSC"),
        ("METAR LIME 170550Z 00000KT 0300 FG VV001 08/08 Q1025", "VV"),
        ("METAR LIMC 171020Z 36004KT CAVOK 15/06 Q1027 NOSIG", "CAVOK"),
        ("METAR LIMC 171050Z 18008KT 9999 FEW015 SCT030CB BKN080 16/11 Q1012", "BKN"),
        ("METAR LIME 171120Z 09005KT 9999 SCT045 15/10 Q1015 TEMPO BKN010", "SCT"),
        ("METAR LIME 171150Z AUTO 09005KT 9999 BKN/// 15/10 Q1015", "BKN"),
        ("METAR LIME 171220Z 09005KT 9999 15/10 Q1015", None),
    ],
)
def test_the_cloud_cover_is_the_most_covered_layer_of_the_sky_now(report, cover):
    assert now.cloud_cover(report) == cover


def test_the_metar_block_reads_the_newest_report_of_the_airport(lake, all_towns):
    store_pull(lake)
    now.publish_metar(lake, lake, all_towns, PULLED)

    metar = read_now(lake, "sesto-calende")["metar"]
    assert metar["icao"] == "LIMC"
    assert metar["observed_at"] == "2026-10-16T11:50:00Z"
    assert (metar["wind_kmh"], metar["wind_dir_deg"]) == (9.3, 220)
    assert (metar["weather"], metar["cloud_cover"], metar["visibility_m"]) == ("BR", "BKN", 5000)
    assert metar["raw"].startswith("METAR LIMC 161150Z")

    lime = read_now(lake, "pedrengo")["metar"]
    assert (lime["wind_kmh"], lime["wind_dir_deg"], lime["gust_kmh"]) == (5.6, None, None)


def test_the_same_report_is_not_written_again(lake, all_towns):
    store_pull(lake)
    now.publish_metar(lake, lake, all_towns, PULLED)
    first = read_now(lake, "pedrengo")["generated_at"]
    now.publish_metar(lake, lake, all_towns, PULLED)
    assert read_now(lake, "pedrengo")["generated_at"] == first


def test_the_radar_block_reads_the_town_cell_and_its_surroundings(all_towns):
    grid = radar.decode(REFERENCE)
    block = now.radar_block(town(all_towns, "pedrengo"), grid, FRAME)
    row, col = radar.grid_cell(45.6959, 9.7392)
    assert block.rate_mm_h == int(grid[row - radar.ROW0, col - radar.COL0]) / 10
    assert block.rate_mm_h <= block.max_5km_mm_h <= block.max_10km_mm_h
    assert block.max_10km_mm_h > 0
    assert not block.no_data


def test_a_frame_with_no_data_near_the_town_says_so(all_towns):
    grid = radar.decode(REFERENCE).copy()
    grid[:] = radar.NODATA
    block = now.radar_block(town(all_towns, "sesto-calende"), grid, FRAME)
    assert (block.rate_mm_h, block.max_10km_mm_h, block.no_data) == (None, None, True)


def test_each_job_keeps_the_other_ones_block(lake, all_towns):
    store_pull(lake)
    lake.put_new("raw", raw_name("radar", FRAME, "sri", "u16.zlib"), REFERENCE, "")
    now.publish_radar(lake, lake, all_towns, FRAME)
    now.publish_metar(lake, lake, all_towns, PULLED)

    for t in all_towns:
        file = Now.model_validate(read_now(lake, t.slug))
        assert file.radar is not None and file.radar.frame_time == FRAME
        assert file.metar is not None and file.metar.icao == t.airport.icao
        assert file.reference.name == t.reference.name
