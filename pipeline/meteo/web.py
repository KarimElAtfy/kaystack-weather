import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


class _Retry(Retry):
    # Waits 5, 15 and 45 s, then 2 minutes at most. urllib3's own backoff retries
    # the first time at once, and Open-Meteo's "service is overloaded" 503 needs a
    # few seconds to clear.
    def get_backoff_time(self) -> float:
        return min(5.0 * 3 ** (len(self.history) - 1), 120.0) if self.history else 0.0


def session(
    user_agent: str, retry_on: tuple[int, ...] = (429, 500, 502, 503, 504), retries: int = 3
) -> requests.Session:
    retry = _Retry(
        total=retries,
        status_forcelist=retry_on,
        # The radar API hands out download links through a POST that is safe to repeat.
        allowed_methods=None,
        # A daily quota answers 429 with a Retry-After of hours, and urllib3 would
        # sleep that long inside the function. The waits above are used instead.
        respect_retry_after_header=False,
        raise_on_status=False,
    )
    http = requests.Session()
    http.headers["User-Agent"] = user_agent
    http.mount("https://", HTTPAdapter(max_retries=retry))
    return http
