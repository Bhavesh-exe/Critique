"""Fetcher registry: maps a platform to its fetcher.

The UI shows only platforms present in `_REGISTRY`, so we light up each platform
as its milestone lands. Adding a platform = implement a BaseFetcher and register
it here; nothing else in the app changes.
"""

from __future__ import annotations

from .base import BaseFetcher, FetchError
from .chessdotcom import ChessDotComFetcher
from .github import GitHubFetcher
from .imdb import ImdbFetcher
from .lastfm import LastFmFetcher
from .letterboxd import LetterboxdFetcher
from .myanimelist import MyAnimeListFetcher
from .spotify import SpotifyFetcher

# platform key -> fetcher class
_REGISTRY: dict[str, type[BaseFetcher]] = {
    "github": GitHubFetcher,
    "chessdotcom": ChessDotComFetcher,
    "imdb": ImdbFetcher,
    "spotify": SpotifyFetcher,
    "myanimelist": MyAnimeListFetcher,
    "lastfm": LastFmFetcher,
    "letterboxd": LetterboxdFetcher,
}

# pretty UI label -> internal key
DISPLAY_TO_KEY: dict[str, str] = {
    "GitHub": "github",
    "Chess.com": "chessdotcom",
    "IMDb": "imdb",
    "Spotify": "spotify",
    "MyAnimeList": "myanimelist",
    "Last.fm": "lastfm",
    "Letterboxd": "letterboxd",
}
KEY_TO_DISPLAY = {v: k for k, v in DISPLAY_TO_KEY.items()}


def get_fetcher(name: str) -> BaseFetcher:
    key = DISPLAY_TO_KEY.get(name, name).lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise FetchError(f"Platform '{name}' isn't available yet.")
    return cls()


def available_platforms() -> list[str]:
    """Display labels for platforms that are actually implemented, in order."""
    order = ["GitHub", "Chess.com", "Letterboxd", "Spotify", "MyAnimeList", "Last.fm"]
    return [d for d in order if DISPLAY_TO_KEY[d] in _REGISTRY]


__all__ = ["get_fetcher", "available_platforms", "FetchError", "BaseFetcher",
           "DISPLAY_TO_KEY", "KEY_TO_DISPLAY"]

