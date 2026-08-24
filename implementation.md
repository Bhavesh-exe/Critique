# Critique — Detailed Implementation Plan

> A build guide you can read top-to-bottom to understand **what** we're making and **how** each
> piece works. Written to be followed milestone-by-milestone; every milestone leaves you with a
> runnable app.

---

## 1. The mental model (read this first)

Critique is a **pipeline**. Data flows left→right; each stage has one job:

```
 ┌──────────┐   ┌───────────┐   ┌────────────┐   ┌──────────┐   ┌──────────┐
 │   UI     │→ │  Fetcher   │→ │  Analysis   │→ │  Prompt   │→ │   LLM    │→ critique text → UI
 │ (choose) │   │ (get data) │   │ (summarize) │   │ (frame)  │   │(AgentRtr)│
 └──────────┘   └───────────┘   └────────────┘   └──────────┘   └──────────┘
```

- **UI** — user picks a *platform*, a *username* (or logs into Spotify), and a *tone*.
- **Fetcher** — talks to that platform's API/pages, returns a **normalized `TasteProfile`**.
- **Analysis** — turns raw items into stats (top genres, obscurity, diversity) + a compact text block.
- **Prompt** — wraps that text in a tone-specific system prompt.
- **LLM** — AgentRouter (OpenAI-compatible) writes the critique.
- **UI** — shows the critique + a copy/share button.

**The one idea that makes this clean:** every platform, no matter how different, is squeezed into the
**same `TasteProfile` shape**. So analysis, prompting, and UI never care *which* platform it came from.
Adding a new platform later = writing one new fetcher. Nothing else changes.

---

## 2. Tech stack & why

| Concern | Choice | Why |
|---|---|---|
| UI / app | **Streamlit** | Pure Python, one file to start, free 1-click deploy. |
| LLM access | **`openai` SDK → AgentRouter** | AgentRouter speaks the OpenAI "chat/completions" format. Using the official SDK means base-URL/key/model are just config → swappable to Groq/Gemini/OpenRouter with **zero code change**. |
| HTTP | **`requests`** | Simple, battle-tested, for MAL/Last.fm/Letterboxd. |
| Spotify auth | **`spotipy`** | Handles the OAuth 2.0 dance so we don't hand-roll it. |
| Scraping | **`beautifulsoup4` + `feedparser`** | Parse Letterboxd RSS + HTML. |
| Config | **`python-dotenv`** + `st.secrets` | Local `.env` for dev, Streamlit secrets for prod. |

`requirements.txt`:
```
streamlit
openai
requests
spotipy
beautifulsoup4
feedparser
python-dotenv
```

---

## 3. Setup & repo decisions

- **New, standalone git repo** inside `critique/` (a fresh `git init` here). We will **not** commit to the
  home-directory `python-projects` repo. `git add` is never run from the home folder.
- **Virtual env:** `.venv/` in the project (already created on Python 3.14).
- **⚠️ Python 3.14 gate (do this before writing feature code):** 3.14 is brand-new; `pyarrow` (a Streamlit
  dependency) may not ship 3.14 wheels yet. **Test:** `pip install streamlit` then `streamlit hello`.
  - ✅ works → proceed on 3.14.
  - ❌ fails → install Python 3.12 or 3.13, recreate `.venv` with it. **No project code changes needed.**
- **Secrets never committed:** `.gitignore` covers `.venv/`, `.env`, `.streamlit/secrets.toml`, `__pycache__/`.

---

## 4. The core data contract (`critique/models.py`)

Everything depends on these two small classes. Get them right and the rest slots in.

```python
from dataclasses import dataclass, field

@dataclass
class MediaItem:
    title: str                      # "Cowboy Bebop", "Radiohead", "Parasite"
    kind: str = ""                  # "anime" | "artist" | "track" | "film" | ...
    genres: list[str] = field(default_factory=list)
    score: float | None = None      # user's rating if any (0-10, 0-5, ...)
    count: int | None = None        # playcount / episodes / times watched
    popularity: float | None = None # 0-100 mainstream-ness if the API gives it
    url: str | None = None

@dataclass
class TasteProfile:
    platform: str                   # "myanimelist" | "lastfm" | "spotify" | "letterboxd"
    username: str
    top_items: list[MediaItem] = field(default_factory=list)
    stats: dict = field(default_factory=dict)   # computed numbers (see §8)
    text_summary: str = ""          # the final human-readable block fed to the LLM
```

Each **fetcher** fills `platform`, `username`, `top_items`, and a few `stats`. Then **analysis** enriches
`stats` and writes `text_summary`.

---

## 5. Config (`critique/config.py`)

One `Settings` object, read once. Looks in `st.secrets` first (prod), then `.env` (local dev).

```python
import os
from dotenv import load_dotenv
load_dotenv()

def _get(key, default=None):
    # st.secrets wins on Streamlit Cloud; os.environ for local .env
    try:
        import streamlit as st
        if key in st.secrets: return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)

class Settings:
    LLM_BASE_URL = _get("LLM_BASE_URL", "https://agentrouter.org/v1")  # confirm from your dashboard
    LLM_API_KEY  = _get("LLM_API_KEY")
    LLM_MODEL    = _get("LLM_MODEL", "gpt-4o-mini")                    # pick a model AgentRouter offers
    LASTFM_API_KEY = _get("LASTFM_API_KEY")
    SPOTIFY_CLIENT_ID = _get("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = _get("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = _get("SPOTIFY_REDIRECT_URI", "http://localhost:8501")
    MAL_CLIENT_ID = _get("MAL_CLIENT_ID")   # optional: unlocks full anime list

settings = Settings()
```

`.env.example` will list every one of these with comments so you know what to fill in.

---

## 6. The LLM layer (`critique/llm.py`) — AgentRouter

AgentRouter is OpenAI-compatible, so this is tiny and swappable:

```python
from openai import OpenAI
from .config import settings

def _client():
    return OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)

def generate_critique(system_prompt: str, user_block: str) -> str:
    resp = _client().chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_block},
        ],
        temperature=0.9,          # a bit spicy for roast/creative tones
        max_tokens=700,
    )
    return resp.choices[0].message.content.strip()
```

Swap providers later by only changing `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` in your `.env`.

---

## 7. Prompt engineering (`critique/prompts.py`) — the 5 tones

This is the part interviewers care about. Each tone is a **distinct system prompt** with the same rules:
*use the real data*, *name specific titles*, *don't be generic*.

```python
BASE_RULES = (
    "You are Critique, an AI that analyzes someone's media taste from real data. "
    "Rules: reference SPECIFIC titles/artists from the data; never invent items; "
    "be concrete, not generic; 150-250 words; end with one punchy line."
)

TONES = {
    "roast":        "Be a witty, savage-but-clever roast comedian. Mock their taste, stay clever not cruel.",
    "formal":       "Be a formal cultural critic. Measured, analytical, essayistic.",
    "supportive":   "Be a warm, encouraging friend who celebrates what their taste says about them.",
    "philosophical":"Be a reflective philosopher; connect their taste to identity, meaning, and psychology.",
    "recommend":    "Diagnose gaps and blind spots, then recommend 5 concrete new items + a growth direction.",
}

def build(tone: str) -> str:
    return f"{BASE_RULES}\n\nTONE: {TONES[tone]}"
```

The **user message** is the profile's `text_summary` (built in §8). Clean separation: system = personality,
user = data.

---

## 8. Analysis (`critique/analysis.py`)

Turns `top_items` into shareable numbers and the `text_summary`.

- **Top genres** — count genres across items, take top N.
- **Diversity** — `unique_genres / total_items` (0-1). High = eclectic, low = one-note.
- **Obscurity score (0-100)** — the headline "mainstream ↔ hipster" metric people screenshot.
  Derived from popularity signals the API gives us:
  - Spotify: artist `popularity` (0-100) → obscurity = `100 - mean(popularity)`.
  - Last.fm: from a track/artist's global `listeners` (fewer = more obscure).
  - MAL: from a favorite's `members` count.
  - Letterboxd: from a film's rating count / watch count.
- **Per-platform extras** — MAL mean score & completion rate; Last.fm scrobble recency; Letterboxd rating spread.

```python
def summarize(profile) -> None:
    items = profile.top_items
    genres = Counter(g for it in items for g in it.genres)
    profile.stats["top_genres"] = genres.most_common(8)
    profile.stats["diversity"] = round(len(genres) / max(len(items),1), 2)
    # ... obscurity per platform ...
    profile.text_summary = _render(profile)   # a compact, LLM-friendly text block
```

`_render` produces something like:
```
Platform: Last.fm  |  User: bhavesh
Top artists: Radiohead (1204 plays), Aphex Twin (980), ...
Top genres: alternative, electronic, ambient, ...
Obscurity: 72/100 (leans underground).  Diversity: 0.41.
```

---

## 9. Fetchers (`critique/fetchers/`)

`base.py` defines the interface; `__init__.py` maps a platform name → fetcher; each file implements one platform.

```python
# base.py
class BaseFetcher:
    name: str
    def fetch(self, username: str, **auth) -> TasteProfile: ...
```

### 9a. MyAnimeList (`myanimelist.py`) — no key needed
- **Source:** Jikan v4 (`https://api.jikan.moe/v4`), unofficial MAL API, free, rate-limited (~3 req/s).
- **Endpoints:** `/users/{u}/statistics` (mean score, counts, completion), `/users/{u}/favorites`
  (favorite anime/manga). Genres per favorite via `/anime/{id}/full`.
- **Note:** Jikan v4 removed the *full list* endpoints. Default = statistics + favorites (plenty for a critique).
- **Optional upgrade:** if `MAL_CLIENT_ID` is set, call the official API
  `https://api.myanimelist.net/v2/users/{u}/animelist?fields=list_status,node(genres)&limit=1000`
  with header `X-MAL-CLIENT-ID` for the **full list with genres**.

### 9b. Last.fm (`lastfm.py`) — free API key
- **Source:** `https://ws.audioscrobbler.com/2.0/`, `?method=...&user=...&api_key=...&format=json`.
- **Methods:** `user.getInfo`, `user.getTopArtists`, `user.getTopTracks`, `user.getTopTags`, `user.getRecentTracks`.
- Rich, clean data: artists + playcounts + genre-ish tags. Easiest quality result.

### 9c. Spotify (`spotify.py`) — OAuth 2.0 (the hard one)
- **Source:** Web API via `spotipy`. Scopes: `user-top-read`.
- **Endpoints:** `/me`, `/me/top/artists`, `/me/top/tracks`. Genres come from artist objects; `popularity` 0-100.
- **The Streamlit challenge:** Streamlit reruns the whole script on every click, so the OAuth redirect
  (`?code=...`) must be captured from `st.query_params` and exchanged once, caching the token in
  `st.session_state`. Flow: click **Connect Spotify** → redirect to Spotify → back to app with `?code=` →
  exchange → fetch. Redirect URI must be registered in the Spotify dashboard (localhost for dev, app URL for prod).
- **Isolation:** all this weirdness lives in this file; other platforms stay simple.

### 9d. Letterboxd (`letterboxd.py`) — scraping, best-effort
- **No official API.** Prefer the **RSS feed** `https://letterboxd.com/{u}/rss/` (recent films, ratings,
  mini-reviews) — most stable. Optionally scrape `/{u}/films/by/rating/` (paginated) for more.
- Polite: set a real `User-Agent`, add delays, wrap in try/except, show a "best-effort, may break" UI note.
- **ToS caveat** surfaced in the UI; positioned as optional.

**Future adds (same interface, easy):** AniList (GraphQL, no auth, clean genres), Trakt (Client-ID header,
films/TV), Steam (web API + SteamID, games).

---

## 10. UI (`app.py`)

```python
import streamlit as st
from critique.fetchers import get_fetcher
from critique.analysis import summarize
from critique.prompts import build
from critique.llm import generate_critique

st.set_page_config(page_title="Critique", page_icon="🎭", layout="centered")
platform = st.selectbox("Platform", ["MyAnimeList","Last.fm","Spotify","Letterboxd"])
tone     = st.radio("Tone", ["roast","formal","supportive","philosophical","recommend"], horizontal=True)

if platform == "Spotify":
    ...  # Connect-Spotify OAuth button flow
else:
    username = st.text_input("Username")

if st.button("Analyze me", type="primary"):
    with st.spinner("Reading your taste..."):
        profile = get_fetcher(platform).fetch(username)   # → TasteProfile
        summarize(profile)                                # fills stats + text_summary
        critique = generate_critique(build(tone), profile.text_summary)
    st.markdown(f"### Your verdict\n{critique}")
    render_stats_panel(profile.stats)   # genres, obscurity, diversity
    render_share_button(critique)       # copy-to-clipboard via components.html
```

- **Error states:** invalid username, private profile, missing API key, rate-limited — each a friendly `st.error`.
- **Theme:** `.streamlit/config.toml` custom colors so it doesn't look like default Streamlit.
- **Share:** a small HTML `navigator.clipboard.writeText(...)` button.

---

## 11. Build order (milestones — each ends runnable)

| # | Milestone | Concrete tasks | "Done" looks like |
|---|---|---|---|
| **M0** | Scaffold + 3.14 gate | venv ✓, `requirements.txt`, package skeleton, `.gitignore`, `.env.example`, `git init` (new repo) | `streamlit hello` runs |
| **M1** | LLM + config + prompts | `config.py`, `llm.py`, `prompts.py`; script that runs all 5 tones on a FAKE profile | AgentRouter returns 5 tone variants |
| **M2** | MyAnimeList | `models.py`, `analysis.py`, `base.py`, `myanimelist.py`; wire into `app.py` | Enter a MAL username → real critique |
| **M3** | Last.fm | `lastfm.py` (+ Last.fm key) | Enter a Last.fm username → real critique |
| **M4** | UI polish | tones, share button, stats panel, theme, error states | Looks/feels like a product |
| **M5** | Spotify OAuth | `spotify.py`, Connect flow, dashboard app | Log in → top-artist critique (local) |
| **M6** | Letterboxd | `letterboxd.py` (RSS first) | Public profile → critique; graceful fail on private |
| **M7** | README + deploy | `README.md`, Streamlit Cloud, secrets, prod Spotify redirect | Live shareable URL |

---

## 12. API keys — how to get each (when we reach that milestone)

- **AgentRouter:** sign in → dashboard → copy **API key**, **base URL** (e.g. `.../v1`), pick a **model id**.
- **Last.fm:** last.fm/api/account/create → instant **API key** (only the key is needed).
- **Spotify:** developer.spotify.com/dashboard → Create app → copy **Client ID/Secret**, add **Redirect URI**
  `http://localhost:8501` (dev) and later your Streamlit Cloud URL (prod).
- **MyAnimeList (optional):** myanimelist.net/apiconfig → Create ID → **Client ID** (unlocks full anime list).

---

## 13. Run locally & deploy

- **Local:** `.venv/Scripts/python -m streamlit run app.py` → opens `http://localhost:8501`.
- **Deploy:** push the new repo to GitHub → share.streamlit.io → point at `app.py` → paste keys into
  **Secrets** (same names as `.env`) → update Spotify redirect URI to the live URL.

---

## 14. Verification / testing

- **M1:** run the fake-profile script; confirm 5 distinct tones come back → AgentRouter wired correctly.
- **M2/M3:** real MAL + Last.fm usernames → critique names real titles/artists; check obscurity/diversity look sane.
- **M5:** full Spotify login round-trip locally; token cached across reruns.
- **M6:** Letterboxd public profile works; private/missing profile fails gracefully with a clear message.
- **Error paths:** bad username, missing key, rate-limit → friendly messages, no stack traces in the UI.
- **Deploy:** app loads on Streamlit Cloud; Spotify redirect works against the prod URL.

---

## Default decision: Letterboxd scope
To keep momentum, Letterboxd (M6) ships **RSS-first**: the stable `/{u}/rss/` feed (recent films, ratings,
mini-reviews) is enough for a solid critique, and deeper page-scraping is an *optional* enhancement added
only if you want richer data. This avoids blocking on the most fragile integration. Say the word if you'd
rather go full-scrape from the start.

## Next step
On approval I start at **M0** (finish the Python-3.14 install gate + scaffold the new repo) and move
straight into **M1** (AgentRouter LLM + prompts, tested on a fake profile). I'll pause for your API keys
exactly when each milestone needs them (AgentRouter first).