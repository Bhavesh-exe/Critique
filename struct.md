# 📁 Critique — Repository Structure & File Directory (`struct.md`)

This document provides a comprehensive, file-by-file blueprint of the entire **Critique** repository, detailing the architecture, responsibilities, and components across all tiers.

---

## 🌳 High-Level Tree View

```
critique/
├── 📄 app.py                             # Streamlit UI application entry point
├── 📄 api.py                             # Standalone FastAPI backend with streaming endpoint
├── 📄 rxconfig.py                        # Reflex web application configuration
├── 📄 Dockerfile                         # Multi-stage production container build definition
├── 📄 requirements.txt                   # Production Python package dependencies
├── 📄 package.json                       # Node/npm dependency lock & overrides
├── 📄 .env.example                       # Environment variable blueprint template
├── 📄 .gitignore                         # Git file exclusion rules
├── 📄 struct.md                          # Repository structure and file directory (this file)
├── 📄 flow.md                            # Execution lifecycle and data pipeline flow
├── 📄 wid.md                             # Chronological project development history
├── 📄 CLAUDE.md                          # Developer guidance and system documentation
├── 📄 GEMINI.md                          # Antigravity assistant guidelines & protocols
├── 📄 README.md                          # Public product overview and setup instructions
│
├── 📂 critique_ui/                       # Modern Reflex Web Application Frontend
│   ├── 📄 __init__.py                    # Module export definitions
│   ├── 📄 critique_ui.py                 # Root application page layout & theme controller
│   ├── 📄 state.py                       # Reactive State, async event loops & Claude loading ticker
│   ├── 📄 styles.py                      # Design tokens, palette constants & platform tile meta
│   └── 📂 components/                    # Modular Reflex UI Components
│       ├── 📄 header.py                  # Masthead kicker, animated wordmark & Dark/Light mode toggle
│       ├── 📄 platform_input.py          # Platform selector grid (3×2) and username field
│       ├── 📄 tone_selector.py           # 5-Persona voice selection grid with individual accents
│       ├── 📄 verdict_card.py            # Result card with Didone styling & one-click clipboard copy
│       ├── 📄 stats_display.py           # Obscurity & Diversity meters, stat rows, genre tags
│       └── 📄 raw_accordion.py           # Raw LLM context inspection accordion
│
├── 📂 critique/                          # Core Domain Logic & Platform Adapters
│   ├── 📄 __init__.py                    # Root domain exports
│   ├── 📄 models.py                      # Core domain dataclasses (TasteProfile, MediaItem)
│   ├── 📄 config.py                      # Lazy property-based environment & secrets reader
│   ├── 📄 analysis.py                    # Genre counter, Shannon Entropy diversity & summary renderer
│   ├── 📄 prompts.py                     # Persona prompts, grounding rules & single-paragraph constraints
│   ├── 📄 llm.py                         # OpenAI-compatible API client directed to AgentRouter
│   └── 📂 fetchers/                      # Platform Data Fetchers (Adapters)
│       ├── 📄 __init__.py                # Fetcher registry (_REGISTRY) & available_platforms()
│       ├── 📄 base.py                    # Abstract BaseFetcher with exponential backoff retry session
│       ├── 📄 github.py                  # GitHub REST API adapter (repos, stars, topics)
│       ├── 📄 chessdotcom.py             # Chess.com PubAPI adapter (ratings, openings, ECO parser)
│       ├── 📄 imdb.py                    # IMDb adapter (ratings, era span, suggestions API)
│       ├── 📄 spotify.py                 # Spotify OAuth 2.0 & Web API adapter
│       ├── 📄 myanimelist.py             # MAL adapter (Jikan v4 API / official MAL API)
│       ├── 📄 lastfm.py                  # Last.fm AudioScrobbler 2.0 API adapter
│       └── 📄 letterboxd.py              # Letterboxd public RSS feed XML parser
│
├── 📂 assets/                            # Static Design System & CSS Styling
│   └── 📄 critique.css                   # Custom CSS styling (typography, themes, animations, layouts)
│
├── 📂 evals/                             # Prompt Evaluation & Quality Benchmarking Suite
│   ├── 📄 __init__.py                    # Evaluation package init
│   ├── 📄 fixtures.py                    # Deterministic offline mock profiles across all 6 platforms
│   ├── 📄 scoring.py                     # 8 automated rubric metric scoring functions
│   ├── 📄 run.py                         # Automated evaluation CLI runner with markdown report export
│   └── 📄 README.md                      # Benchmarking suite documentation & methodology
│
└── 📂 .streamlit/                        # Streamlit Configuration
    ├── 📄 config.toml                    # Streamlit custom dark theme tokens & server config
    └── 📄 secrets.toml.example           # Streamlit Community Cloud secrets template
```

---

## 🔍 Detailed Component Directory

### 1. Web Application Layer (`critique_ui/`)
Reflex-based reactive web application built with Python and compiled into a React/Vite SPA.

| File Path | Description & Responsibilities |
| :--- | :--- |
| `critique_ui/critique_ui.py` | Main page coordinator. Integrates the background `.atmos` layer, `.panel` input forms, loading state ticker, verdict card, and dynamic dark/light CSS variables. |
| `critique_ui/state.py` | `State(rx.State)` managing active theme, selected platform, username, selected persona, async execution loop, `CLAUDE_VERBS` ticker, and error states. |
| `critique_ui/styles.py` | Design tokens (`INK`, `PAPER`, `TONE_ACCENTS`, `PLATFORM_TILES`, `BASE_STYLE`) and color variables. |
| `critique_ui/components/header.py` | Hero header with volume metadata, signature settling wordmark animation, and Dark/Light theme toggle button. |
| `critique_ui/components/platform_input.py` | Platform selection button grid and username text field. |
| `critique_ui/components/tone_selector.py` | 5-Persona radio selection cards with individual `--own` accent color variables. |
| `critique_ui/components/verdict_card.py` | Result card displaying the final AI-generated verdict paragraph in `Plus Jakarta Sans` with one-click clipboard copy. |
| `critique_ui/components/stats_display.py` | Secondary analytical display component with meter progress bars, dotted-leader stat rows, and genre chips. |
| `critique_ui/components/raw_accordion.py` | Collapsible `<details>/<summary>` container for inspecting the raw data payload sent to the LLM. |

---

### 2. Core Domain & Business Logic Layer (`critique/`)
Platform-agnostic domain layer handling data normalization, metrics calculation, prompt templating, and LLM communication.

| File Path | Description & Responsibilities |
| :--- | :--- |
| `critique/models.py` | Defines `MediaItem` (title, kind, genres, score, count, popularity, url) and `TasteProfile` (platform, username, top_items, stats, text_summary). |
| `critique/config.py` | Lazy-loaded `Settings` class reading from Streamlit secrets first, then local `.env` variables (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, etc.). |
| `critique/analysis.py` | Aggregates top genres, computes **Normalized Shannon Entropy** diversity and obscurity metrics, and renders the clean `profile.text_summary` payload. |
| `critique/prompts.py` | Builds persona prompts (`Roast`, `Formal`, `Supportive`, `Philosophical`, `Recommend`) with strict grounding rules, cliché prohibition, and single-paragraph output shaping. |
| `critique/llm.py` | OpenAI-compatible access layer configured for AgentRouter (`https://agentrouter.org/v1`), including `generate_critique` and `stream_critique` with client allowlist headers. |

---

### 3. Platform Data Adapters (`critique/fetchers/`)
Pluggable data extraction modules implementing `BaseFetcher` to retrieve public user activity.

| File Path | Platform | Method / API | Extracted Data |
| :--- | :--- | :--- | :--- |
| `critique/fetchers/base.py` | Core Base | `requests.Session` | Shared HTTP helper with automated 3-stage exponential backoff retry. |
| `critique/fetchers/github.py` | GitHub | GitHub Public REST API | Public repositories, programming languages, stargazers, topics. |
| `critique/fetchers/chessdotcom.py` | Chess.com | Chess.com PubAPI | Rapid/Blitz/Bullet ratings, win/loss records, favorite openings from PGN archives. |
| `critique/fetchers/letterboxd.py` | Letterboxd | RSS Feed XML Parser | Watched films, release years, star ratings (0.5–5.0), rewatch flags. |
| `critique/fetchers/spotify.py` | Spotify | Spotipy / OAuth 2.0 | Top artists, top tracks, Spotify popularity scores, music genres. |
| `critique/fetchers/myanimelist.py` | MyAnimeList | Jikan v4 API / MAL API | Anime/manga stats, completed titles, mean scores, favorite media items. |
| `critique/fetchers/lastfm.py` | Last.fm | AudioScrobbler 2.0 API | Scrobbles, top artists, track play counts, genre tags, listener metrics. |
| `critique/fetchers/__init__.py` | Registry | Factory pattern | Central registration mapping platform strings to fetcher class instances. |

---

### 4. Static Design System & CSS (`assets/`)

| File Path | Description |
| :--- | :--- |
| `assets/critique.css` | Comprehensive stylesheet containing `@property --accent` smooth interpolation, typography imports (`Bodoni Moda`, `Familjen Grotesk`, `IBM Plex Mono`, `Plus Jakarta Sans`, `Inter`), dark/light mode palette overrides, layout grids (`.panel`, `.tiles`, `.voices`), and Claude Code terminal spinner animations (`.claude-spinner`). |

---

### 5. Automated Evaluation & Benchmarking Suite (`evals/`)

| File Path | Description |
| :--- | :--- |
| `evals/fixtures.py` | Deterministic offline `TasteProfile` mock datasets covering all 6 platforms for benchmark repeatability without network calls. |
| `evals/scoring.py` | 8 automated rubric scoring functions measuring length compliance, grounding item coverage, hallucination rate, recommendation format, and cliché prevention. |
| `evals/run.py` | Command-line evaluation runner executing matrix evaluations across all models and personas, generating markdown benchmark tables. |
| `evals/README.md` | Complete methodology and scoring formulas guide for LLM evaluation. |

---

### 6. Alternative UIs & Endpoints

| File Path | Description |
| :--- | :--- |
| `app.py` | Legacy lightweight Streamlit web application providing immediate local and Streamlit Cloud deployment support. |
| `api.py` | Standalone FastAPI backend exposing REST endpoints (`POST /api/critique` and streaming `POST /api/critique/stream`). |

---

### 7. Deployment & Environment Configuration

| File Path | Description |
| :--- | :--- |
| `Dockerfile` | Multi-stage Dockerfile bundling Python runtime, Node/npm build stages, and running Reflex on port 3000/8000. |
| `rxconfig.py` | Configuration file for the Reflex application (`critique_ui`). |
| `requirements.txt` | Python runtime dependencies (`reflex`, `openai`, `spotipy`, `beautifulsoup4`, `feedparser`, `python-dotenv`, `streamlit`). |
| `.env.example` | Template documenting all environment keys and secrets required for local development. |
