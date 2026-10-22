from meteo import web


def test_waits_grow_then_stop_at_two_minutes():
    waits = [web._Retry(history=(None,) * n).get_backoff_time() for n in range(7)]
    assert waits == [0.0, 5.0, 15.0, 45.0, 120.0, 120.0, 120.0]


def test_a_session_retries_as_often_as_asked():
    http = web.session("weather.kaystack.dev", retries=6)
    assert http.get_adapter("https://example.org").max_retries.total == 6
