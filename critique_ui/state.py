"""Reactive State for the Critique Reflex application."""

from __future__ import annotations

import asyncio
from typing import Any

import reflex as rx

from critique.analysis import summarize
from critique.fetchers import FetchError, available_platforms, get_fetcher
from critique.llm import LLMAuthError, LLMConfigError, generate_critique, is_configured
from critique.prompts import TONE_ORDER, TONES, build
from critique_ui.styles import DEFAULT_ACCENT, TONE_ACCENTS


import random

CLAUDE_VERBS: list[str] = [
    "Accomplishing", "Actioning", "Actualizing", "Architecting", "Baking", "Beaming", "Beboppin'",
    "Befuddling", "Billowing", "Blanching", "Bloviating", "Boogieing", "Boondoggling", "Booping",
    "Bootstrapping", "Brewing", "Burrowing", "Calculating", "Canoodling", "Caramelizing", "Cascading",
    "Catapulting", "Cerebrating", "Channeling", "Channelling", "Choreographing", "Churning", "Clauding",
    "Coalescing", "Cogitating", "Combobulating", "Composing", "Computing", "Concocting", "Considering",
    "Contemplating", "Cooking", "Crafting", "Creating", "Crunching", "Crystallizing", "Cultivating",
    "Deciphering", "Deliberating", "Determining", "Dilly-dallying", "Discombobulating", "Doing",
    "Doodling", "Drizzling", "Ebbing", "Effecting", "Elucidating", "Embellishing", "Enchanting",
    "Envisioning", "Evaporating", "Fermenting", "Fiddle-faddling", "Finagling", "Flambeing",
    "Flibbertigibbeting", "Flowing", "Flummoxing", "Fluttering", "Forging", "Forming", "Frolicking",
    "Frosting", "Gallivanting", "Galloping", "Garnishing", "Generating", "Germinating", "Gitifying",
    "Grooving", "Gusting", "Harmonizing", "Hashing", "Hatching", "Herding", "Honking", "Hullaballooing",
    "Hyperspacing", "Ideating", "Imagining", "Improvising", "Incubating", "Inferring", "Infusing",
    "Ionizing", "Jitterbugging", "Julienning", "Kneading", "Leavening", "Levitating", "Lollygagging",
    "Manifesting", "Marinating", "Meandering", "Metamorphosing", "Misting", "Moonwalking", "Moseying",
    "Mulling", "Mustering", "Musing", "Nebulizing", "Nesting", "Newspapering", "Noodling", "Nucleating",
    "Orbiting", "Orchestrating", "Osmosing", "Perambulating", "Percolating", "Perusing",
    "Philosophising", "Photosynthesizing", "Pollinating", "Pondering", "Pontificating", "Pouncing",
    "Precipitating", "Prestidigitating", "Processing", "Proofing", "Propagating", "Puttering",
    "Puzzling", "Quantumizing", "Razzle-dazzling", "Razzmatazzing", "Recombobulating", "Reticulating",
    "Roosting", "Ruminating", "Sauteing", "Scampering", "Schlepping", "Scurrying", "Seasoning",
    "Shenaniganing", "Shimmying", "Simmering", "Skedaddling", "Sketching", "Slithering", "Smooshing",
    "Sock-hopping", "Spelunking", "Spinning", "Sprouting", "Stewing", "Sublimating", "Swirling",
    "Swooping", "Symbioting", "Synthesizing", "Tempering", "Thinking", "Thundering", "Tinkering",
    "Tomfoolering", "Topsy-turvying", "Transfiguring", "Transmuting", "Twisting", "Undulating",
    "Unfurling", "Unravelling", "Vibing", "Waddling", "Wandering", "Warping", "Whatchamacalliting",
    "Whirlpooling", "Whirring", "Whisking", "Wibbling", "Working", "Wrangling", "Zesting", "Zigzagging"
]


class State(rx.State):
    """Application state for Critique."""

    # Theme state
    is_dark_mode: bool = True

    # Input state
    selected_platform: str = "GitHub"
    username: str = ""
    selected_tone: str = "roast"

    # Execution state
    is_loading: bool = False
    loading_stage: str = ""
    has_error: bool = False
    error_message: str = ""
    has_result: bool = False

    # Result state
    verdict: str = ""
    verdict_title: str = ""
    verdict_emoji: str = ""
    stats_pills: list[str] = []
    top_genres: list[str] = []
    obscurity_score: float = 0.0
    diversity_score: float = 0.0
    has_obscurity: bool = False
    has_diversity: bool = False
    raw_summary: str = ""

    # Platform options
    platforms: list[str] = available_platforms()
    tone_keys: list[str] = TONE_ORDER

    @rx.var
    def theme_class(self) -> str:
        return "dark-mode" if self.is_dark_mode else "light-mode"

    @rx.var
    def theme_icon(self) -> str:
        return "sun" if self.is_dark_mode else "moon"

    @rx.var
    def theme_label(self) -> str:
        return "Light" if self.is_dark_mode else "Dark"

    @rx.var
    def username_placeholder(self) -> str:
        placeholders = {
            "GitHub": "torvalds",
            "Chess.com": "hikaru",
            "Letterboxd": "your Letterboxd handle",
            "Spotify": "your Spotify username",
            "MyAnimeList": "your MAL username",
            "Last.fm": "your Last.fm username",
        }
        return placeholders.get(self.selected_platform, "username")

    @rx.var
    def tone_items(self) -> list[dict[str, str]]:
        return [
            {
                "key": k,
                "label": TONES[k]["label"],
                "emoji": TONES[k]["emoji"],
            }
            for k in TONE_ORDER
        ]

    # ------------------------------------------------------------------
    # Presentation-only derived vars ("The Critic's Desk" UI)
    # These shape existing data for display; they add no pipeline logic.
    # ------------------------------------------------------------------

    @rx.var
    def accent(self) -> str:
        """Hex accent for the selected persona. Re-themes the entire page."""
        return TONE_ACCENTS.get(self.selected_tone, DEFAULT_ACCENT)

    @rx.var
    def is_spotify(self) -> bool:
        return self.selected_platform == "Spotify"

    @rx.var
    def obscurity_pct(self) -> str:
        """Obscurity (0-100) as a CSS width for the meter fill."""
        return f"{max(0.0, min(100.0, self.obscurity_score))}%"

    @rx.var
    def diversity_pct(self) -> str:
        """Diversity (0-1) as a CSS width for the meter fill."""
        return f"{max(0.0, min(1.0, self.diversity_score)) * 100}%"

    @rx.var
    def obscurity_verdict(self) -> str:
        """The label analysis.py uses for the obscurity band."""
        if self.obscurity_score >= 55:
            return "underground"
        if self.obscurity_score >= 46:
            return "balanced"
        return "mainstream"

    @rx.var
    def diversity_verdict(self) -> str:
        if self.diversity_score >= 0.7:
            return "eclectic"
        if self.diversity_score >= 0.4:
            return "varied"
        return "one-note"

    @rx.var
    def index_rows(self) -> list[dict[str, str]]:
        """Platform stats split into label/value pairs for the dotted-leader index.

        ``stats_pills`` is the only carrier of the per-platform stats, so parse it
        here rather than widening the pipeline. Obscurity and diversity are
        excluded because they get dedicated meters.
        """
        rows: list[dict[str, str]] = []
        for pill in self.stats_pills:
            if pill.startswith(("Obscurity ", "Diversity ")):
                continue
            key, sep, value = pill.partition(": ")
            if not sep:
                continue
            rows.append({"key": key, "value": str(value)})
        return rows

    @rx.var
    def has_index_rows(self) -> bool:
        return len(self.index_rows) > 0

    @rx.var
    def has_genres(self) -> bool:
        return len(self.top_genres) > 0

    @rx.var
    def has_scorecard(self) -> bool:
        return self.has_obscurity or self.has_diversity or self.has_index_rows

    @rx.var
    def dossier_line(self) -> str:
        """The byline printed at the foot of the verdict."""
        handle = self.username.strip() or "anonymous"
        return f"@{handle} · {self.selected_platform}"

    def toggle_theme(self) -> None:
        self.is_dark_mode = not self.is_dark_mode

    def set_platform(self, platform: str) -> None:
        self.selected_platform = platform
        self.has_error = False
        self.error_message = ""

    def set_username(self, username: str) -> None:
        self.username = username

    def set_tone(self, tone: str) -> None:
        self.selected_tone = tone

    def clear_error(self) -> None:
        self.has_error = False
        self.error_message = ""

    async def analyze_taste(self) -> None:
        """Fetch user data, compute stats, and call LLM for critique."""
        if not self.username.strip():
            self.has_error = True
            self.error_message = f"Please enter your {self.selected_platform} username."
            return

        if not is_configured():
            self.has_error = True
            self.error_message = (
                "AI is not configured. Please set LLM_BASE_URL and LLM_API_KEY in your .env file."
            )
            return

        self.has_error = False
        self.error_message = ""
        self.is_loading = True
        self.has_result = False
        self.loading_stage = f"{random.choice(CLAUDE_VERBS)} {self.selected_platform} profile..."
        yield

        try:
            # 1. Fetch platform profile
            print(f"\n[CRITIQUE PIPELINE] Fetching {self.selected_platform} profile for user '{self.username.strip()}'...", flush=True)
            fetcher = get_fetcher(self.selected_platform)
            # Run blocking network fetch in executor to keep async loop snappy
            loop = asyncio.get_event_loop()
            profile = await loop.run_in_executor(None, fetcher.fetch, self.username.strip())
            print(f"[CRITIQUE PIPELINE] Successfully fetched profile. Items count: {len(profile.top_items)}", flush=True)

            # 2. Summarize & compute profile
            self.loading_stage = f"{random.choice(CLAUDE_VERBS)} taste profile..."
            yield

            summarize(profile)
            self.raw_summary = profile.text_summary

            # Process stats
            stats = profile.stats
            pills = []
            if "obscurity" in stats:
                self.has_obscurity = True
                self.obscurity_score = float(stats["obscurity"])
                pills.append(f"Obscurity {stats['obscurity']}/100")
            else:
                self.has_obscurity = False

            if "diversity" in stats:
                self.has_diversity = True
                self.diversity_score = float(stats["diversity"])
                pills.append(f"Diversity {stats['diversity']}")
            else:
                self.has_diversity = False

            for k, v in stats.items():
                if k in {"top_genres", "obscurity", "diversity"} or v is None:
                    continue
                pills.append(f"{k}: {v}")
            self.stats_pills = pills

            tg = stats.get("top_genres", [])
            self.top_genres = [f"{g}" for g, _ in tg] if tg else []

            # 3. Call LLM
            self.loading_stage = f"{random.choice(CLAUDE_VERBS)} {TONES[self.selected_tone]['label'].lower()} verdict..."
            yield

            system_prompt = build(self.selected_tone)
            critique_text = await loop.run_in_executor(
                None, generate_critique, system_prompt, profile.text_summary
            )

            # 4. Set results
            self.verdict = critique_text
            self.verdict_title = TONES[self.selected_tone]["label"]
            self.verdict_emoji = TONES[self.selected_tone]["emoji"]
            self.has_result = True

        except FetchError as e:
            self.has_error = True
            self.error_message = f"Couldn't fetch profile: {e}"
        except LLMConfigError as e:
            self.has_error = True
            self.error_message = str(e)
        except LLMAuthError as e:
            self.has_error = True
            self.error_message = (
                f"LLM Authentication Failed: {e}. Please check your LLM_API_KEY."
            )
        except Exception as e:  # noqa: BLE001
            self.has_error = True
            self.error_message = f"An unexpected error occurred: {e}"
        finally:
            self.is_loading = False
            self.loading_stage = ""

    async def copy_verdict(self) -> None:
        """Copy verdict text to user's clipboard and trigger toast."""
        share_text = f"My {self.verdict_title} taste verdict from Critique:\n\n{self.verdict}"
        return rx.set_clipboard(share_text)
