"""MyAnimeList fetcher.

Two paths:
  * Default (no key): the free **Jikan v4** API. Jikan v4 removed the full
    list endpoints, so we use `/users/{u}/statistics` + `/users/{u}/favorites`
    and look up genres/popularity for each favorite. That's plenty for a critique.
  * Optional (MAL_CLIENT_ID set): the official MAL API, which returns the full
    anime list with genres and the user's own scores. Best-effort; falls back
    to Jikan on any error.
"""

from __future__ import annotations

import math
import time

from ..config import settings
from ..models import MediaItem, TasteProfile
from .base import BaseFetcher, FetchError

JIKAN = "https://api.jikan.moe/v4"
MAL_API = "https://api.myanimelist.net/v2"

# How many favorites to enrich with genre/popularity lookups (bounds latency;
# Jikan is ~3 req/s so we sleep a touch between calls).
_MAX_ANIME_FAVS = 4
_MAX_MANGA_FAVS = 2
_POLITE_DELAY = 0.1


def _mainstream_from_members(members: int | None) -> float | None:
    """Map a title's MAL member count to a 0-100 mainstream-ness score.

    ~10k members -> 0 (obscure); ~3.16M members -> 100 (mainstream). Log scale.
    """
    if not members or members <= 0:
        return None
    val = (math.log10(members) - 4.0) / (6.5 - 4.0) * 100
    return round(max(0.0, min(100.0, val)), 1)


class MyAnimeListFetcher(BaseFetcher):
    name = "myanimelist"

    def fetch(self, username: str, **auth) -> TasteProfile:
        username = (username or "").strip()
        if not username:
            raise FetchError("Please enter a MyAnimeList username.")

        if settings.MAL_CLIENT_ID:
            try:
                return self._fetch_official(username)
            except Exception:
                # Any problem with the official API → fall back to Jikan.
                pass
        return self._fetch_jikan(username)

    # -- Jikan (no key) ------------------------------------------------------
    def _fetch_jikan(self, username: str) -> TasteProfile:
        prof = TasteProfile(platform=self.name, username=username, display_name=username)

        # Statistics (also our "does this user exist?" check — 404s propagate).
        stats = self.get_json(f"{JIKAN}/users/{username}/statistics").get("data", {})
        anime = stats.get("anime", {})
        manga = stats.get("manga", {})
        if anime.get("mean_score"):
            prof.stats["Anime mean score"] = anime.get("mean_score")
        if anime.get("completed") is not None:
            prof.stats["Anime completed"] = anime.get("completed")
        if anime.get("days_watched"):
            prof.stats["Days watched"] = anime.get("days_watched")
        if manga.get("completed"):
            prof.stats["Manga completed"] = manga.get("completed")
            if manga.get("mean_score"):
                prof.stats["Manga mean score"] = manga.get("mean_score")

        # Favorites → titles + genres + popularity.
        favs = self.get_json(f"{JIKAN}/users/{username}/favorites").get("data", {})
        for fav in (favs.get("anime") or [])[:_MAX_ANIME_FAVS]:
            prof.top_items.append(self._enrich(fav, "anime"))
        for fav in (favs.get("manga") or [])[:_MAX_MANGA_FAVS]:
            prof.top_items.append(self._enrich(fav, "manga"))

        if not prof.top_items and not prof.stats:
            raise FetchError(
                f"No public MyAnimeList data for '{username}'. "
                "The profile may be private or empty."
            )
        return prof

    def _enrich(self, fav: dict, kind: str) -> MediaItem:
        """Turn a favorite into a MediaItem, adding genres + popularity if we can."""
        item = MediaItem(title=fav.get("title", ""), kind=kind, url=fav.get("url"))
        mal_id = fav.get("mal_id")
        if not mal_id:
            return item
        try:
            time.sleep(_POLITE_DELAY)
            data = self.get_json(f"{JIKAN}/{kind}/{mal_id}/full").get("data", {})
            item.genres = [g.get("name") for g in data.get("genres", []) if g.get("name")]
            item.popularity = _mainstream_from_members(data.get("members"))
        except Exception:
            pass  # genre lookup is best-effort; keep the bare title
        return item

    # -- Official MAL API (needs a Client ID) --------------------------------
    def _fetch_official(self, username: str) -> TasteProfile:
        headers = {"X-MAL-CLIENT-ID": settings.MAL_CLIENT_ID}
        params = {"fields": "list_status,genres", "limit": 100, "sort": "list_score"}
        data = self.get_json(
            f"{MAL_API}/users/{username}/animelist", params=params, headers=headers
        ).get("data", [])

        prof = TasteProfile(platform=self.name, username=username, display_name=username)
        scores: list[float] = []
        for entry in data:
            node = entry.get("node", {})
            ls = entry.get("list_status", {})
            score = ls.get("score") or None
            if score:
                scores.append(score)
            prof.top_items.append(MediaItem(
                title=node.get("title", ""),
                kind="anime",
                genres=[g.get("name") for g in node.get("genres", []) if g.get("name")],
                score=score,
                url=f"https://myanimelist.net/anime/{node.get('id')}",
            ))
        if scores:
            prof.stats["Mean score"] = round(sum(scores) / len(scores), 2)
        prof.stats["List size"] = len(data)
        if not prof.top_items:
            raise FetchError(f"No anime list data for '{username}'.")
        # keep only the top 25 by score for the summary
        prof.top_items.sort(key=lambda i: i.score or 0, reverse=True)
        prof.top_items = prof.top_items[:25]
        return prof
