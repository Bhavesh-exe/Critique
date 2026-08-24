"""Spotify fetcher — OAuth 2.0 via Spotipy.

Fetches the logged-in user's top artists, top tracks, genres, and artist
popularity (0-100) using the `user-top-read` OAuth scope.
"""

from __future__ import annotations

from typing import Any
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from ..config import settings
from ..models import MediaItem, TasteProfile
from .base import BaseFetcher, FetchError

SPOTIFY_SCOPE = "user-top-read"


def get_spotify_oauth() -> SpotifyOAuth:
    """Instantiate a SpotifyOAuth handler using app settings."""
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        raise FetchError(
            "Spotify credentials missing. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET "
            "in your .env or Streamlit secrets."
        )
    return SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope=SPOTIFY_SCOPE,
        open_browser=False,
    )


def get_authorize_url() -> str:
    """Return the URL for the user to log in and authorize Spotify."""
    sp_oauth = get_spotify_oauth()
    return sp_oauth.get_authorize_url()


def exchange_code_for_token(code: str) -> dict:
    """Exchange an OAuth redirect code for an access token dict."""
    sp_oauth = get_spotify_oauth()
    token_info = sp_oauth.get_access_token(code, as_dict=True, check_cache=False)
    if not token_info or "access_token" not in token_info:
        raise FetchError("Failed to authenticate with Spotify. Please try connecting again.")
    return token_info


class SpotifyFetcher(BaseFetcher):
    name = "spotify"

    def fetch(self, username: str = "", **auth: Any) -> TasteProfile:
        token = auth.get("token")
        if not token:
            raise FetchError(
                "Spotify requires authentication. Please click 'Connect Spotify' first."
            )

        if isinstance(token, dict):
            access_token = token.get("access_token")
        else:
            access_token = str(token)

        try:
            sp = spotipy.Spotify(auth=access_token)
            me = sp.me()
        except Exception as e:
            raise FetchError(f"Spotify authentication failed: {e}")

        user_id = me.get("id", "spotify_user")
        display_name = me.get("display_name") or user_id

        prof = TasteProfile(
            platform=self.name,
            username=user_id,
            display_name=display_name,
        )

        followers = me.get("followers", {}).get("total")
        if followers is not None:
            prof.stats["Followers"] = f"{followers:,}"

        # 1. Top Artists (medium term: ~last 6 months)
        try:
            top_artists_res = sp.current_user_top_artists(limit=15, time_range="medium_term")
            artists = top_artists_res.get("items", [])
        except Exception as e:
            raise FetchError(f"Failed to fetch top Spotify artists: {e}")

        for rank, a in enumerate(artists, start=1):
            artist_name = a.get("name", "")
            if not artist_name:
                continue

            genres = [g.title() for g in a.get("genres", [])]
            pop = a.get("popularity")  # 0-100
            spotify_url = a.get("external_urls", {}).get("spotify")

            prof.top_items.append(
                MediaItem(
                    title=artist_name,
                    kind="artist",
                    genres=genres,
                    popularity=float(pop) if pop is not None else None,
                    count=rank,  # rank in top artists
                    url=spotify_url,
                )
            )

        # 2. Top Tracks (medium term)
        try:
            top_tracks_res = sp.current_user_top_tracks(limit=10, time_range="medium_term")
            tracks = top_tracks_res.get("items", [])
        except Exception:
            tracks = []

        for rank, t in enumerate(tracks, start=1):
            track_name = t.get("name", "")
            artist_names = ", ".join(art.get("name", "") for art in t.get("artists", []))
            title = f"{artist_names} – {track_name}" if artist_names else track_name
            if not title:
                continue

            pop = t.get("popularity")
            spotify_url = t.get("external_urls", {}).get("spotify")

            prof.top_items.append(
                MediaItem(
                    title=title,
                    kind="track",
                    popularity=float(pop) if pop is not None else None,
                    count=rank,
                    url=spotify_url,
                )
            )

        if prof.is_empty():
            raise FetchError(
                f"No listening history found on Spotify for {display_name}. "
                "Account may be new or without top artists."
            )

        prof.stats["Top artists fetched"] = len(artists)
        prof.stats["Top tracks fetched"] = len(tracks)

        return prof
