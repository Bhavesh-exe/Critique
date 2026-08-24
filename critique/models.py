"""Core data contract shared by every layer of the app.

Every platform fetcher, no matter how different its API, returns the *same*
`TasteProfile` shape. That single normalization is what keeps analysis,
prompting, and the UI completely platform-agnostic — adding a new platform is
just one new fetcher, nothing else changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MediaItem:
    """One thing the user consumed: an anime, artist, track, film, etc."""

    title: str
    kind: str = ""                       # "anime" | "artist" | "track" | "film" | "album" | ...
    genres: list[str] = field(default_factory=list)
    score: float | None = None           # the user's own rating, if the platform has one
    count: int | None = None             # playcount / episodes / times watched
    popularity: float | None = None      # 0-100 mainstream-ness, if the API exposes it
    url: str | None = None

    def label(self) -> str:
        """Human label used inside the LLM summary, e.g. 'Radiohead (1204 plays)'."""
        if self.count is not None:
            return f"{self.title} ({self.count})"
        if self.score is not None:
            return f"{self.title} ({self.score})"
        return self.title


@dataclass
class TasteProfile:
    """Normalized snapshot of one user's taste on one platform."""

    platform: str                        # "myanimelist" | "lastfm" | "spotify" | "letterboxd"
    username: str
    display_name: str = ""               # nicer name if the API gives one
    top_items: list[MediaItem] = field(default_factory=list)
    stats: dict = field(default_factory=dict)   # computed numbers (see analysis.py)
    text_summary: str = ""               # the compact block fed to the LLM as the user message

    def is_empty(self) -> bool:
        return not self.top_items and not self.stats
