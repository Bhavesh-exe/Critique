"""Chess.com fetcher.

Fetches player statistics, ratings, and recent games using the free public
Chess.com PubAPI (https://www.chess.com/news/view/published-data-api).

Extracts:
  - Rating metrics across time controls (Rapid, Blitz, Bullet, Daily, Puzzles).
  - Win/Loss/Draw records and overall win percentage.
  - Favorite openings derived from recent game archives.
  - Playstyle and format items normalized into MediaItems.
"""

from __future__ import annotations

import re
import urllib.parse
from collections import Counter

from ..models import MediaItem, TasteProfile
from .base import BaseFetcher, FetchError

CHESS_API = "https://api.chess.com/pub"

# Common opening popularity weights (0-100 scale)
_OPENING_POPULARITY: dict[str, float] = {
    "sicilian defense": 90.0,
    "italian game": 88.0,
    "queens gambit": 85.0,
    "queen's gambit": 85.0,
    "caro-kann defense": 82.0,
    "caro kann defense": 82.0,
    "french defense": 80.0,
    "ruy lopez": 80.0,
    "kings indian defense": 75.0,
    "king's indian defense": 75.0,
    "london system": 78.0,
    "scandinavian defense": 72.0,
    "english opening": 70.0,
    "kings pawn opening": 85.0,
    "king's pawn opening": 85.0,
    "queens pawn opening": 75.0,
    "queen's pawn opening": 75.0,
    "modern defense": 55.0,
    "vienna game": 60.0,
    "nimzo-indian defense": 65.0,
    "grunfeld defense": 60.0,
    "dutch defense": 45.0,
    "alehkine defense": 45.0,
    "benoni defense": 40.0,
    "scotish game": 65.0,
    "scotch game": 65.0,
    "bongcloud": 15.0,
    "grob opening": 10.0,
}


def _clean_opening_name(raw_url_or_name: str) -> str:
    """Extract a human-friendly opening name from an ECOUrl or PGN string."""
    if not raw_url_or_name:
        return ""

    if "chess.com/openings/" in raw_url_or_name:
        # e.g. https://www.chess.com/openings/Sicilian-Defense-Najdorf-Variation...
        slug = raw_url_or_name.split("/openings/")[-1]
        slug = slug.split("?")[0].split("#")[0]
        # Remove trailing move numbers like -1...e5 or -2.Nf3
        slug = re.sub(r"-\d+\.{1,3}[a-zA-Z0-9]+", "", slug)
        # Replace hyphens with spaces and unquote
        parts = [p.strip() for p in slug.split("-") if p.strip()]
        name = " ".join(parts)
        # Clean up double dots or extra move indicators
        name = re.sub(r"\s+\d+\.\.\..*$", "", name).strip()
        return name

    # If already a plain string, clean up
    cleaned = raw_url_or_name.replace("-", " ").strip()
    return re.sub(r"\s+\d+\.\.\..*$", "", cleaned).strip()


def _rating_to_popularity(rating: int | None) -> float:
    """Map a Chess.com rating to a 0-100 scale (1000 -> 30, 1800 -> 70, 2600+ -> 98)."""
    if rating is None or rating <= 0:
        return 40.0
    val = (rating - 600) / 2000.0 * 100.0
    return round(max(5.0, min(99.0, val)), 1)


class ChessDotComFetcher(BaseFetcher):
    name = "chessdotcom"

    def fetch(self, username: str, **auth) -> TasteProfile:
        username = (username or "").strip().lower()
        if not username:
            raise FetchError("Please enter a Chess.com username.")

        # 1. Fetch user profile
        user_url = f"{CHESS_API}/player/{username}"
        user_data = self.get_json(user_url)

        display_name = user_data.get("name") or user_data.get("username") or username
        title = user_data.get("title")  # GM, IM, FM, etc.
        if title:
            display_name = f"[{title}] {display_name}"

        prof = TasteProfile(
            platform=self.name,
            username=username,
            display_name=display_name,
        )

        # 2. Fetch stats
        stats_url = f"{CHESS_API}/player/{username}/stats"
        stats_data = {}
        try:
            stats_data = self.get_json(stats_url)
        except Exception:
            pass

        total_wins = 0
        total_losses = 0
        total_draws = 0

        # Process time controls & ratings
        time_controls = [
            ("Rapid", "chess_rapid"),
            ("Blitz", "chess_blitz"),
            ("Bullet", "chess_bullet"),
            ("Daily", "chess_daily"),
        ]

        for label, key in time_controls:
            tc_data = stats_data.get(key)
            if not isinstance(tc_data, dict):
                continue
            last = tc_data.get("last", {})
            rating = last.get("rating")
            best = tc_data.get("best", {}).get("rating")
            record = tc_data.get("record", {})
            w = record.get("win", 0) or 0
            l = record.get("loss", 0) or 0
            d = record.get("draw", 0) or 0
            games = w + l + d

            total_wins += w
            total_losses += l
            total_draws += d

            if rating:
                prof.stats[f"{label} rating"] = f"{rating}" + (f" (Best: {best})" if best else "")
                prof.top_items.append(
                    MediaItem(
                        title=f"{label} Chess",
                        kind="time_control",
                        genres=[label, "Time Control"],
                        score=float(rating),
                        count=games,
                        popularity=_rating_to_popularity(rating),
                    )
                )

        # Tactics & Puzzle Rush
        tactics = stats_data.get("tactics", {})
        if isinstance(tactics, dict) and "highest" in tactics:
            tactics_high = tactics["highest"].get("rating")
            if tactics_high:
                prof.stats["Tactics rating"] = tactics_high
                prof.top_items.append(
                    MediaItem(
                        title="Puzzles & Tactics",
                        kind="puzzles",
                        genres=["Tactics", "Puzzles"],
                        score=float(tactics_high),
                        popularity=_rating_to_popularity(tactics_high),
                    )
                )

        # 3. Overall Win/Loss/Draw summary
        total_games = total_wins + total_losses + total_draws
        if total_games > 0:
            win_rate = round((total_wins / total_games) * 100, 1)
            prof.stats["Record (W/L/D)"] = f"{total_wins}W / {total_losses}L / {total_draws}D ({win_rate}% win rate)"

        # 4. Fetch recent monthly game archives to extract favorite openings
        openings_counter: Counter[str] = Counter()
        try:
            archives_url = f"{CHESS_API}/player/{username}/games/archives"
            arch_data = self.get_json(archives_url)
            archives = arch_data.get("archives", [])
            if archives:
                # Check the most recent 2 monthly archives
                for arch_url in archives[-2:]:
                    month_data = self.get_json(arch_url)
                    games_list = month_data.get("games", [])
                    for g in games_list:
                        eco_url = g.get("eco")
                        if not eco_url and "pgn" in g:
                            # Fallback: check PGN for ECOUrl header
                            m = re.search(r'\[ECOUrl "(.*?)"\]', g["pgn"])
                            if m:
                                eco_url = m.group(1)
                        if eco_url:
                            op_name = _clean_opening_name(eco_url)
                            if op_name and len(op_name) > 3:
                                openings_counter[op_name] += 1
        except Exception:
            pass

        # Add top openings to items and stats
        if openings_counter:
            top_opening_tuple = openings_counter.most_common(1)[0]
            prof.stats["Favorite opening"] = f"{top_opening_tuple[0]} ({top_opening_tuple[1]} games)"

            for op_name, count in openings_counter.most_common(8):
                # Classify opening style genre
                lower_op = op_name.lower()
                genres = ["Opening", "Chess"]
                if "sicilian" in lower_op or "gambit" in lower_op or "attack" in lower_op:
                    genres.insert(0, "Aggressive")
                elif "french" in lower_op or "caro" in lower_op or "london" in lower_op or "berlin" in lower_op:
                    genres.insert(0, "Solid")
                elif "indian" in lower_op or "grunfeld" in lower_op or "modern" in lower_op:
                    genres.insert(0, "Hypermodern")
                else:
                    genres.insert(0, "Classical")

                # Popularity score based on opening database
                pop = 60.0
                for known, score in _OPENING_POPULARITY.items():
                    if known in lower_op:
                        pop = score
                        break

                prof.top_items.append(
                    MediaItem(
                        title=f"Opening: {op_name}",
                        kind="opening",
                        genres=genres,
                        count=count,
                        popularity=pop,
                    )
                )

        if title:
            prof.stats["FIDE/Chess Title"] = title

        return prof
