"""Last.fm fetcher.

Uses the free Last.fm AudioScrobbler 2.0 API (requires LASTFM_API_KEY).
Retrieves user stats (play count, registered date), top artists with play counts,
listener counts (for obscurity metrics), tags (genres), and top tracks.
"""

from __future__ import annotations

import math
from typing import Any

from ..config import settings
from ..models import MediaItem, TasteProfile
from .base import BaseFetcher, FetchError

LASTFM_API = "https://ws.audioscrobbler.com/2.0/"
_MAX_ENRICH_ARTISTS = 8


def _mainstream_from_listeners(listeners: int | None) -> float | None:
    """Map an artist's global Last.fm listener count to 0-100 mainstream-ness.

    ~30k listeners -> 0 (underground); ~5M listeners -> 100 (mainstream). Log scale.
    """
    if not listeners or listeners <= 0:
        return None
    val = (math.log10(listeners) - 4.5) / (6.7 - 4.5) * 100
    return round(max(0.0, min(100.0, val)), 1)


class LastFmFetcher(BaseFetcher):
    name = "lastfm"

    def _call(self, method: str, **params: Any) -> dict:
        """Helper to invoke a Last.fm API method and catch Last.fm-level errors."""
        p = {
            "method": method,
            "api_key": settings.LASTFM_API_KEY,
            "format": "json",
            **params,
        }
        data = self.get_json(LASTFM_API, params=p)
        if isinstance(data, dict) and "error" in data:
            code = data.get("error")
            msg = data.get("message", "Last.fm error")
            if code == 6:
                raise FetchError(f"User not found on Last.fm ({msg}).")
            raise FetchError(f"Last.fm API error: {msg}")
        return data

    def fetch(self, username: str, **auth) -> TasteProfile:
        username = (username or "").strip()
        if not username:
            raise FetchError("Please enter a Last.fm username.")
        if not settings.LASTFM_API_KEY:
            raise FetchError(
                "Last.fm API key is missing. Add LASTFM_API_KEY to your .env or secrets."
            )

        prof = TasteProfile(platform=self.name, username=username, display_name=username)

        # 1. User info (playcount, registered, realname)
        info_data = self._call("user.getinfo", user=username)
        user_info = info_data.get("user", {})
        if not user_info:
            raise FetchError(f"Could not load Last.fm profile for '{username}'.")

        display_name = user_info.get("realname") or user_info.get("name") or username
        prof.display_name = display_name

        try:
            playcount = int(user_info.get("playcount", 0))
            prof.stats["Total scrobbles"] = f"{playcount:,}"
        except (ValueError, TypeError):
            pass

        # 2. Top artists
        artists_data = self._call("user.gettopartists", user=username, limit=15, period="overall")
        artist_entries = artists_data.get("topartists", {}).get("artist", [])
        if isinstance(artist_entries, dict):
            artist_entries = [artist_entries]

        for i, a in enumerate(artist_entries):
            artist_name = a.get("name", "")
            if not artist_name:
                continue

            play_count = None
            try:
                play_count = int(a.get("playcount", 0))
            except (ValueError, TypeError):
                pass

            item = MediaItem(
                title=artist_name,
                kind="artist",
                count=play_count,
                url=a.get("url"),
            )

            # Enrich the top artists with tags and global listener count for obscurity
            if i < _MAX_ENRICH_ARTISTS:
                self._enrich_artist(item, artist_name)

            prof.top_items.append(item)

        # 3. Top tracks
        tracks_data = self._call("user.gettoptracks", user=username, limit=8, period="overall")
        track_entries = tracks_data.get("toptracks", {}).get("track", [])
        if isinstance(track_entries, dict):
            track_entries = [track_entries]

        for t in track_entries:
            t_name = t.get("name", "")
            t_artist = t.get("artist", {}).get("name", "") if isinstance(t.get("artist"), dict) else ""
            title = f"{t_artist} – {t_name}" if t_artist else t_name
            if not title:
                continue

            play_count = None
            try:
                play_count = int(t.get("playcount", 0))
            except (ValueError, TypeError):
                pass

            prof.top_items.append(
                MediaItem(
                    title=title,
                    kind="track",
                    count=play_count,
                    url=t.get("url"),
                )
            )

        if prof.is_empty():
            raise FetchError(
                f"No scrobble activity found for '{username}'. The profile may be new or empty."
            )

        return prof

    def _enrich_artist(self, item: MediaItem, artist_name: str) -> None:
        """Fetch artist tags (genres) and global listener count for popularity scoring."""
        try:
            data = self._call("artist.getinfo", artist=artist_name, autocorrect=1)
            artist_info = data.get("artist", {})

            # listeners
            listeners_str = artist_info.get("stats", {}).get("listeners")
            if listeners_str:
                listeners = int(listeners_str)
                item.popularity = _mainstream_from_listeners(listeners)

            # tags / genres
            tags_raw = artist_info.get("tags", {}).get("tag", [])
            if isinstance(tags_raw, dict):
                tags_raw = [tags_raw]
            item.genres = [
                t.get("name").title()
                for t in tags_raw
                if isinstance(t, dict) and t.get("name")
            ][:4]
        except Exception:
            pass
