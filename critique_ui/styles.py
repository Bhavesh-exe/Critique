"""Design tokens for Critique - The Critic's Desk.

All component styling lives in assets/critique.css via CSS class names.
This module holds only the values Python needs to reason about: the per-persona
accent palette (drives --accent CSS custom property interpolation) and a
handful of structural constants.
"""

from __future__ import annotations

# --- Surfaces ---------------------------------------------------------------
INK = "#0a0908"           # page - warm near-black, reads as printed matter
INK_PANEL = "#100e0c"     # panels
INK_RAISED = "#17140f"    # selected / raised
INK_SUNK = "#070605"      # inputs, wells

# --- Paper (never pure white) ----------------------------------------------
PAPER = "#f4efe6"
PAPER_DIM = "#a9a094"
PAPER_FAINT = "#6d665c"

RULE = "rgba(244, 239, 230, 0.13)"

# --- Typography -------------------------------------------------------------
SERIF = "'Bodoni Moda', 'Times New Roman', serif"
SANS = "'Familjen Grotesk', 'Helvetica Neue', sans-serif"
MONO = "'IBM Plex Mono', ui-monospace, monospace"

# --- Per-persona accents ----------------------------------------------------
# Selecting a persona re-themes the whole page: every rule, meter, glow,
# drop cap and button interpolates to this hue via the registered --accent
# CSS custom property.
TONE_ACCENTS: dict[str, str] = {
    "roast":         "#ff5b2e",  # ember
    "formal":        "#d8b163",  # brass
    "supportive":    "#ff8fa8",  # rose
    "philosophical": "#9d8bf5",  # iris
    "recommend":     "#3fcf9a",  # jade
}
DEFAULT_ACCENT = TONE_ACCENTS["roast"]

# One-line editorial description per persona, shown on the voice cards.
TONE_BLURBS: dict[str, str] = {
    "roast":         "No mercy, all wit",
    "formal":        "Measured and essayistic",
    "supportive":    "Warm and generous",
    "philosophical": "Meaning and identity",
    "recommend":     "Blind spots and cures",
}

# --- Platform tiles ---------------------------------------------------------
# (display name, lucide icon slug, small corner tag)
PLATFORM_TILES: list[tuple[str, str, str]] = [
    ("GitHub",      "git_branch", "code"),
    ("Chess.com",   "crown",      "chess"),
    ("Letterboxd",  "film",       "film"),
    ("Spotify",     "music",      "oauth"),
    ("MyAnimeList", "tv",         "anime"),
    ("Last.fm",     "radio",      "music"),
]

# --- Body style (applied to the page root) ---------------------------------
BASE_STYLE: dict = {
    "background":  "var(--ink)",
    "color":       "var(--paper)",
    "font_family": SANS,
    "min_height":  "100vh",
    "position":    "relative",
    "overflow_x":  "hidden",
    "transition":  "background-color 300ms ease, color 300ms ease",
}
