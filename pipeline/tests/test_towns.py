from meteo import towns


def test_both_towns_load(all_towns):
    assert [t.slug for t in all_towns] == ["pedrengo", "sesto-calende"]


def test_forecasts_go_to_the_stations_and_the_hidden_airport(all_towns):
    points = towns.forecast_points(all_towns)
    assert [p.id for p in points] == ["torre-boldone", "lime", "ispra-jrc", "varano-borghi"]
    # api.met.no answers 403 to 5 decimals or more.
    assert all(len(f"{p.lat}".split(".")[1]) <= 4 for p in points)


def test_arpa_sensors_are_the_stations_and_their_buddies(all_towns):
    sensors = {s.id: s for s in towns.arpa_sensors(all_towns)}
    assert sorted(sensors) == [5857, 5864, 8145, 8161, 8167, 14528, 32353, 32354, 32355]
    assert sensors[5864].station is None
    assert sensors[5864].buddy_of == 8145
    assert sensors[14528].station == 1375
    assert towns.reference_sensors(all_towns) == [8145, 8161, 32353, 32354, 32355]


def test_airports_carry_icao_and_wmo(all_towns):
    assert [(a.icao, a.wmo) for a in towns.airports(all_towns)] == [
        ("LIME", 16076),
        ("LIMC", 16066),
    ]
