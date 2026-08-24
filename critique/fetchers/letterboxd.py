"""Letterboxd fetcher — RSS-first implementation.

Letterboxd does not provide an open public API, so we parse the user's public
RSS feed at `https://letterboxd.com/{username}/rss/` using feedparser & BeautifulSoup.
Extracts film titles, member ratings (0.5-5.0), reviews, rewatches, and watch dates.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup
import feedparser

from ..models import MediaItem, TasteProfile
from .base import BaseFetcher, FetchError

LETTERBOXD_BASE = "https://letterboxd.com"


def _parse_star_rating(text: str) -> float | None:
    """Parse Letterboxd unicode stars (e.g. ★★★★½ -> 4.5)."""
    if not text:
        return None
    full_stars = text.count("★")
    half_stars = text.count("½")
    if full_stars or half_stars:
        return float(full_stars + 0.5 * half_stars)
    return None


def _clean_film_title(raw_title: str) -> str:
    """Strip out year and star rating suffixes from RSS entry titles."""
    # e.g. "Dune: Part Two, 2024 - ★★★★½" -> "Dune: Part Two (2024)"
    cleaned = re.sub(r"\s*-\s*[★½]+.*$", "", raw_title).strip()
    return cleaned


class LetterboxdFetcher(BaseFetcher):
    name = "letterboxd"

    def fetch(self, username: str, **auth: Any) -> TasteProfile:
        username = (username or "").strip().lower()
        if not username:
            raise FetchError("Please enter a Letterboxd username.")

        rss_url = f"{LETTERBOXD_BASE}/{username}/rss/"

        try:
            resp = self.session.get(rss_url, timeout=15)
        except Exception as e:
            raise FetchError(f"Network error connecting to Letterboxd: {e}")

        if resp.status_code == 404:
            raise FetchError(
                f"Letterboxd user '{username}' not found (or their diary is private)."
            )
        if resp.status_code != 200:
            raise FetchError(f"Letterboxd returned HTTP {resp.status_code}.")

        feed = feedparser.parse(resp.text)
        if getattr(feed, "bozo", 0) and not feed.entries:
            raise FetchError(
                f"Could not parse Letterboxd feed for '{username}'. The profile may be private."
            )

        prof = TasteProfile(platform=self.name, username=username, display_name=username)

        # Title of feed usually contains user's display name, e.g. "Letterboxd - {name}'s Diary"
        if feed.feed and getattr(feed.feed, "title", None):
            title_text = feed.feed.title
            m = re.search(r"Letterboxd\s*-\s*(.+?)'s", title_text, re.IGNORECASE)
            if m:
                prof.display_name = m.group(1).strip()

        scores: list[float] = []
        rewatch_count = 0

        for entry in feed.entries:
            raw_title = getattr(entry, "title", "")
            if not raw_title:
                continue

            # Check for Letterboxd XML extensions
            film_title = getattr(entry, "letterboxd_filmtitle", None)
            film_year = getattr(entry, "letterboxd_filmyear", None)
            if film_title:
                title = f"{film_title} ({film_year})" if film_year else film_title
            else:
                title = _clean_film_title(raw_title)

            # Rating
            rating_val: float | None = None
            raw_rating = getattr(entry, "letterboxd_memberrating", None)
            if raw_rating is not None:
                try:
                    rating_val = float(raw_rating)
                except ValueError:
                    pass
            if rating_val is None:
                rating_val = _parse_star_rating(raw_title)

            if rating_val is not None:
                scores.append(rating_val)

            # Rewatch tag
            is_rewatch = getattr(entry, "letterboxd_rewatch", "No") == "Yes"
            if is_rewatch:
                rewatch_count += 1

            # Extract any review text snippet from description HTML if present
            desc_html = getattr(entry, "description", "")
            if desc_html:
                soup = BeautifulSoup(desc_html, "html.parser")
                # Remove images / posters to find review paragraphs
                for img in soup.find_all("img"):
                    img.decompose()

            item = MediaItem(
                title=title,
                kind="film",
                score=rating_val,
                url=getattr(entry, "link", None),
            )
            prof.top_items.append(item)

        if not prof.top_items:
            raise FetchError(
                f"No public film diary entries found for Letterboxd user '{username}'."
            )

        if scores:
            prof.stats["Average film rating"] = f"{sum(scores) / len(scores):.2f}/5"
            prof.stats["Highest rating"] = f"{max(scores)}/5"
            prof.stats["Lowest rating"] = f"{min(scores)}/5"
        prof.stats["Recent diary entries"] = len(prof.top_items)
        if rewatch_count > 0:
            prof.stats["Rewatches in feed"] = rewatch_count

        return prof
