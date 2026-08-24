"""Fetcher base class + shared HTTP helper.

Each platform implements `BaseFetcher.fetch(username) -> TasteProfile`. The
shared `requests.Session` sets a real User-Agent and maps common HTTP failures
to a friendly `FetchError` the UI can show without a stack trace.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

import requests

from ..models import TasteProfile

USER_AGENT = "Critique/0.1 (+https://github.com/ media taste analyzer)"


class FetchError(Exception):
    """A user-facing fetch problem: bad username, private profile, rate limit…"""


class BaseFetcher(ABC):
    name: str = ""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    @abstractmethod
    def fetch(self, username: str, **auth) -> TasteProfile:
        """Return a normalized TasteProfile for the given username."""

    # -- shared helper -------------------------------------------------------
    def get_json(self, url: str, params: dict | None = None,
                 headers: dict | None = None, timeout: int = 15,
                 retries: int = 3) -> dict:
        """GET JSON with retry/backoff on rate-limits, 5xx, and network blips.

        404 is treated as definitive (no retry). Transient failures (429 / 5xx /
        network errors — common with Jikan proxying MyAnimeList) are retried a
        few times before surfacing a friendly FetchError.
        """
        last_error: FetchError | None = None
        for attempt in range(retries + 1):
            try:
                r = self.session.get(url, params=params, headers=headers, timeout=timeout)
            except requests.RequestException as e:
                last_error = FetchError(f"Network error contacting the API: {e}")
            else:
                if r.status_code == 404:
                    raise FetchError("Not found — double-check the username.")
                if r.status_code == 401 or r.status_code == 403:
                    raise FetchError("Access denied — the profile may be private, or a key is invalid.")
                if r.status_code == 429:
                    last_error = FetchError("The API rate-limited us. Try again in a few seconds.")
                elif r.status_code >= 500:
                    last_error = FetchError(
                        "The platform's data provider is temporarily unavailable "
                        "(server error). Please try again shortly."
                    )
                else:
                    try:
                        r.raise_for_status()
                    except requests.HTTPError as e:
                        raise FetchError(f"API error (HTTP {r.status_code}).") from e
                    return r.json()

            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))  # 0.8s, 1.6s, 2.4s backoff

        raise last_error or FetchError("The request failed after several retries.")
