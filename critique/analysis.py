"""Analysis layer — turns a fetched TasteProfile into shareable stats + the
compact text block that gets sent to the LLM.

Deliberately platform-agnostic: it only reads `top_items` and whatever numbers a
fetcher already put in `stats`. Fetchers normalize `MediaItem.popularity` to a
0-100 "mainstream-ness" scale, so obscurity can be computed uniformly here.
"""

from __future__ import annotations

from collections import Counter
from math import log

from .models import TasteProfile

# stats keys that analysis manages / renders specially rather than as plain rows.
_SPECIAL_KEYS = {"top_genres", "diversity", "obscurity"}


def summarize(profile: TasteProfile) -> TasteProfile:
    """Compute derived stats in-place and build `profile.text_summary`."""
    items = profile.top_items

    # --- top genres across all items ---
    genre_counter: Counter[str] = Counter()
    for it in items:
        for g in it.genres:
            if g:
                genre_counter[g] += 1
    if genre_counter:
        profile.stats["top_genres"] = genre_counter.most_common(8)

    # --- diversity: normalized Shannon entropy of the genre mix (0-1) ---
    #   0 = one genre only (one-note); 1 = evenly spread across many genres.
    counts = list(genre_counter.values())
    if len(counts) > 1:
        total = sum(counts)
        probs = [c / total for c in counts]
        entropy = -sum(p * log(p) for p in probs)
        profile.stats["diversity"] = round(entropy / log(len(counts)), 2)
    elif counts:
        profile.stats["diversity"] = 0.0

    # --- obscurity 0-100 (higher = more underground) ---
    pops = [it.popularity for it in items if it.popularity is not None]
    if pops:
        profile.stats["obscurity"] = round(100 - sum(pops) / len(pops), 1)

    profile.text_summary = _render(profile)
    return profile


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _render(profile: TasteProfile) -> str:
    """Compact, LLM-friendly text block. Human keys, one fact per line."""
    lines: list[str] = [
        f"Platform: {profile.platform}",
        f"User: {profile.display_name or profile.username}",
    ]

    # plain scalar stats (skip the specially-handled ones and empty values)
    for key, val in profile.stats.items():
        if key in _SPECIAL_KEYS or val is None or val == "":
            continue
        lines.append(f"{key}: {_fmt(val)}")

    tg = profile.stats.get("top_genres")
    if tg:
        lines.append("Top genres: " + ", ".join(f"{g} ({c})" for g, c in tg))

    if profile.top_items:
        lines.append("Top items:")
        for it in profile.top_items[:25]:
            g = f" [{'/'.join(it.genres[:3])}]" if it.genres else ""
            lines.append(f"  - {it.label()}{g}")

    return "\n".join(lines)
