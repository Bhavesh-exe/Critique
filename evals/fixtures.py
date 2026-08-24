"""Frozen TasteProfile fixtures for offline evaluation.

Why fixtures instead of live fetches: an eval must be *deterministic*. If the
harness hit Last.fm and Jikan every run, the inputs would drift, rate limits
would throttle it, and a bad score could mean "the prompt got worse" or "the API
returned different data" with no way to tell which. Freezing the inputs means
every change in the numbers is attributable to the prompt or the model.

These go through the real `summarize()`, so `text_summary` is produced by the
actual production code path — not a hand-written approximation of it.
"""

from __future__ import annotations

from critique.analysis import summarize
from critique.models import MediaItem, TasteProfile


def _lastfm_mainstream() -> TasteProfile:
    """A very online indie listener. High popularity across the board."""
    p = TasteProfile(platform="lastfm", username="velvetmoth", display_name="velvetmoth")
    p.stats["scrobbles"] = 48213
    p.top_items = [
        MediaItem("Radiohead", "artist", ["alternative rock", "art rock"], count=1204, popularity=88),
        MediaItem("Tame Impala", "artist", ["psychedelic rock", "indie"], count=880, popularity=85),
        MediaItem("Mac DeMarco", "artist", ["indie rock", "slacker rock"], count=642, popularity=74),
        MediaItem("Beach House", "artist", ["dream pop", "indie"], count=531, popularity=70),
        MediaItem("Phoebe Bridgers", "artist", ["indie folk", "singer-songwriter"], count=498, popularity=79),
        MediaItem("The Strokes", "artist", ["garage rock", "indie rock"], count=455, popularity=83),
        MediaItem("Frank Ocean", "artist", ["r&b", "alternative r&b"], count=390, popularity=90),
        MediaItem("Alvvays", "artist", ["dream pop", "jangle pop"], count=201, popularity=58),
    ]
    return summarize(p)


def _lastfm_obscure() -> TasteProfile:
    """Deliberate contrast case: low popularity, narrow genre spread."""
    p = TasteProfile(platform="lastfm", username="tapehiss", display_name="tapehiss")
    p.stats["scrobbles"] = 12907
    p.top_items = [
        MediaItem("Duster", "artist", ["slowcore", "space rock"], count=812, popularity=31),
        MediaItem("Bedhead", "artist", ["slowcore"], count=604, popularity=19),
        MediaItem("Codeine", "artist", ["slowcore", "sadcore"], count=577, popularity=17),
        MediaItem("Red House Painters", "artist", ["slowcore", "folk rock"], count=430, popularity=28),
        MediaItem("Low", "artist", ["slowcore", "indie rock"], count=388, popularity=35),
        MediaItem("Grouper", "artist", ["ambient", "drone folk"], count=290, popularity=26),
    ]
    return summarize(p)


def _myanimelist() -> TasteProfile:
    """Shonen-heavy, high completion, mainstream picks."""
    p = TasteProfile(platform="myanimelist", username="kenjiro", display_name="Kenjiro")
    p.stats["mean_score"] = 8.4
    p.stats["days_watched"] = 61.2
    p.stats["completed"] = 214
    p.top_items = [
        MediaItem("Fullmetal Alchemist: Brotherhood", "anime", ["Action", "Adventure", "Drama"], score=10, popularity=92),
        MediaItem("Death Note", "anime", ["Mystery", "Psychological", "Thriller"], score=9, popularity=95),
        MediaItem("Attack on Titan", "anime", ["Action", "Drama"], score=9, popularity=96),
        MediaItem("Steins;Gate", "anime", ["Sci-Fi", "Drama", "Thriller"], score=10, popularity=89),
        MediaItem("Hunter x Hunter", "anime", ["Action", "Adventure", "Fantasy"], score=9, popularity=87),
        MediaItem("Cowboy Bebop", "anime", ["Action", "Sci-Fi", "Drama"], score=8, popularity=81),
    ]
    return summarize(p)


def _letterboxd() -> TasteProfile:
    """Arthouse leaning, ratings present, no popularity signal at all.

    Included on purpose: several platforms give no popularity number, so the
    scorer and the UI both have to survive `popularity=None`.
    """
    p = TasteProfile(platform="letterboxd", username="grainfield", display_name="grainfield")
    p.stats["films_logged"] = 487
    p.top_items = [
        MediaItem("In the Mood for Love", "film", ["Romance", "Drama"], score=5.0),
        MediaItem("Stalker", "film", ["Science Fiction", "Drama"], score=4.5),
        MediaItem("Chungking Express", "film", ["Romance", "Comedy"], score=5.0),
        MediaItem("Paris, Texas", "film", ["Drama"], score=4.5),
        MediaItem("Come and See", "film", ["War", "Drama"], score=5.0),
        MediaItem("Perfect Blue", "film", ["Animation", "Thriller"], score=4.0),
    ]
    return summarize(p)


def _github() -> TasteProfile:
    """Non-media platform: proves the pipeline is domain-agnostic."""
    p = TasteProfile(platform="github", username="bsoni-dev", display_name="bsoni-dev")
    p.stats["public_repos"] = 23
    p.stats["total_stars"] = 41
    p.top_items = [
        MediaItem("critique", "repo", ["Python"], count=18),
        MediaItem("dsa-notebook", "repo", ["Python", "Jupyter Notebook"], count=9),
        MediaItem("portfolio-site", "repo", ["JavaScript", "CSS"], count=7),
        MediaItem("lstm-from-scratch", "repo", ["Python"], count=5),
        MediaItem("dotfiles", "repo", ["Shell"], count=2),
    ]
    return summarize(p)


# name -> builder. Keep names short; they become CLI arguments.
PROFILES = {
    "lastfm_mainstream": _lastfm_mainstream,
    "lastfm_obscure": _lastfm_obscure,
    "myanimelist": _myanimelist,
    "letterboxd": _letterboxd,
    "github": _github,
}


def load(name: str) -> TasteProfile:
    if name not in PROFILES:
        raise KeyError(f"No fixture '{name}'. Available: {', '.join(PROFILES)}")
    return PROFILES[name]()


def load_all() -> dict[str, TasteProfile]:
    return {name: build() for name, build in PROFILES.items()}
