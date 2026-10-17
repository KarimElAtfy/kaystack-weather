from collections.abc import Callable
from pathlib import Path

import pytest
import requests
from requests.adapters import BaseAdapter

from meteo import towns, web
from meteo.store import FolderStore

FIXTURES = Path(__file__).parent / "fixtures"
TOWNS = Path(__file__).resolve().parents[2] / "towns"

type Answer = tuple[int, bytes, dict[str, str]]


def fixture(path: str) -> bytes:
    return (FIXTURES / path).read_bytes()


class Replay(BaseAdapter):
    """Answers each request with a recorded response, chosen by method and URL
    without the query string. Every request is kept in `sent`."""

    def __init__(self, routes: dict[tuple[str, str], Answer | Callable[..., Answer]]) -> None:
        super().__init__()
        self.routes = routes
        self.sent: list[requests.PreparedRequest] = []

    def send(self, request, **kwargs):
        self.sent.append(request)
        answer = self.routes[(request.method, request.url.split("?", 1)[0])]
        status, body, headers = answer(request) if callable(answer) else answer
        response = requests.Response()
        response.status_code = status
        response._content = body
        response.headers.update(headers)
        response.url = request.url
        response.request = request
        return response

    def close(self) -> None:
        pass


@pytest.fixture
def lake(tmp_path: Path) -> FolderStore:
    return FolderStore(tmp_path / "lake")


@pytest.fixture
def all_towns() -> list[towns.Town]:
    return towns.load(TOWNS)


def replaying(routes) -> tuple[requests.Session, Replay]:
    http = web.session("weather.kaystack.dev github.com/KarimElAtfy/kaystack-weather")
    replay = Replay(routes)
    http.mount("https://", replay)
    return http, replay
