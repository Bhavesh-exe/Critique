# 🌊 Project Architecture & Execution Flow (`flow.md`)

This document details the complete end-to-end flow of data, state, and logic through **Critique**.

---

## 1. High-Level Pipeline

Data moves strictly from left to right through isolated stages:

```
 ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
 │   1. User    │ ──> │  2. Platform │ ──> │ 3. Taste     │ ──> │ 4. Analysis  │ ──> │ 5. LLM Layer │ ──> │  6. Verdict  │
 │  Selection   │     │   Fetcher    │     │  Contract    │     │  & Summary   │     │ (AgentRouter)│     │     Card     │
 └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
  • Platform           • MyAnimeList        • TasteProfile       • Top Genres         • System Prompt      • Roast / Critic
  • Username/OAuth     • Last.fm            • MediaItems         • Shannon Entropy    • User Summary       • Stats Pills
  • Tone Persona       • Spotify            • Common Schema      • Obscurity (0-100)  • claude-opus-5      • Copy Button
                       • GitHub             • MediaItems         • Shannon Entropy    • User Summary       • Copy Button
                       • Chess.com          • Common Schema      • Obscurity (0-100)  • gpt-5.6-sol
                       • Letterboxd                              • Stats Dictionary
                       • Spotify
                       • MyAnimeList
                       • Last.fm
```

---

## 2. Step-by-Step Execution Lifecycle

### Step 1: User Selection (`critique_ui/` Reflex UI or `app.py` Streamlit)
1. User opens the modern Critique web app.
2. Selects a media/activity platform (`GitHub`, `Chess.com`, `Letterboxd`, `Spotify`, `MyAnimeList`, `Last.fm`).
3. Inputs authentication / identifier:
   - **For GitHub / Chess.com / Letterboxd / MAL / Last.fm**: Types in their public username.
   - **For Spotify**: Connects via OAuth authorization.
4. Selects an AI tone persona (`Roast`, `Formal`, `Supportive`, `Philosophical`, `Recommend`).
5. Clicks **"Analyze My Taste"**.
6. Reflex `State.analyze_taste()` triggers reactive asynchronous execution while logging data payloads and prompts to the terminal.

---

### Step 2: Platform Data Fetching (`critique/fetchers/`)
The app delegates the request to the registered `BaseFetcher` subclass:

#### A. MyAnimeList (`myanimelist.py`)
```
Username ──> Jikan v4 API (/users/{u}/statistics) ──> Fetch user mean score, completed counts, days watched
         ──> Jikan v4 API (/users/{u}/favorites)  ──> Fetch favorite anime & manga titles
         ──> Jikan v4 API (/anime/{id}/full)      ──> Enrich favorites with genres & member counts
         ──> Log-scale popularity formula        ──> Compute 0-100 mainstream score
```

#### B. Last.fm (`lastfm.py`)
```
Username ──> AudioScrobbler API (user.getinfo)       ──> Fetch total scrobble count & user name
         ──> AudioScrobbler API (user.gettopartists) ──> Fetch top 15 artists & individual playcounts
         ──> AudioScrobbler API (artist.getinfo)     ──> Enrich top 8 artists with tags & global listener counts
         ──> AudioScrobbler API (user.gettoptracks)  ──> Fetch top 8 favorite tracks
```

#### C. Spotify (`spotify.py`)
```
OAuth Code ──> Exchange for access token via spotipy.SpotifyOAuth ──> Cache in st.session_state
            ──> Spotify Web API (/me)                             ──> Fetch display name & follower count
            ──> Spotify Web API (/me/top/artists)                 ──> Fetch top artists, artist genres & popularity (0-100)
            ──> Spotify Web API (/me/top/tracks)                  ──> Fetch top tracks & track popularity (0-100)
```

#### D. Letterboxd (`letterboxd.py`)
```
Username ──> Fetch public RSS Feed (https://letterboxd.com/{u}/rss/)
         ──> Parse XML feed via feedparser & BeautifulSoup
         ──> Extract film titles, release years, rewatch flags
         ──> Parse star ratings (e.g. ★★★★½ -> 4.5/5.0)
         ──> Compute average rating, highest rating, lowest rating, diary entries count
```

#### E. GitHub (`github.py`)
```
Username ──> GitHub REST API (/users/{u})       ──> Fetch bio, followers, public repo count, created_at
         ──> GitHub REST API (/users/{u}/repos) ──> Fetch up to 100 recent repos, languages, stars, topics
         ──> Log-scale star popularity formula  ──> Compute 0-100 repository mainstream score
         ──> Map languages & topics to genres   ──> Compute developer diversity & obscurity
```

#### F. Chess.com (`chessdotcom.py`)
```
Username ──> Chess.com PubAPI (/pub/player/{u})             ──> Fetch name, title (GM/IM), followers
         ──> Chess.com PubAPI (/pub/player/{u}/stats)       ──> Fetch Rapid, Blitz, Bullet, Daily, Tactics & records
         ──> Chess.com PubAPI (/pub/player/{u}/games/archives) ──> Parse monthly game archives
         ──> ECOUrl / PGN Header Parser                    ──> Extract favorite openings (e.g. Sicilian, Queen's Gambit)
         ──> Style Classifier & Theory Popularity          ──> Compute chess diversity & opening obscurity
```

#### G. IMDb (`imdb.py`)
```
Identifier / URL ──> Pattern matcher (URLs, user IDs 'ur.../p...', handles 'madmax-02960', title lists)
                 ──> Query IMDb Suggestions API (v3.sg.media-imdb.com/suggestion/{c}/{slug}.json)
                 ──> Enrich films with release years, starring cast, era span, popularity rank
                 ──> Deduplicate and attach user ratings statistics (e.g. 286 ratings)
```


---

### Step 3: Normalization to Shared Contract (`critique/models.py`)
Regardless of platform differences, raw API responses are mapped into the shared `TasteProfile` dataclass:

```python
TasteProfile(
    platform="lastfm",
    username="bhavesh",
    display_name="Bhavesh Soni",
    top_items=[
        MediaItem(title="Radiohead", kind="artist", count=1204, genres=["Art Rock", "Electronic"], popularity=75.0),
        MediaItem(title="Aphex Twin", kind="artist", count=980, genres=["IDM", "Ambient"], popularity=60.0),
        ...
    ],
    stats={"Total scrobbles": "45,210", ...}
)
```

---

### Step 4: Statistical Analysis & Text Summary (`critique/analysis.py`)
The `summarize(profile)` function computes key metrics:

1. **Genre Counter**: Tallies all genre occurrences across all top media items.
2. **Diversity Score (Normalized Shannon Entropy)**:
   $$\text{Diversity} = \frac{-\sum (p_i \cdot \ln(p_i))}{\ln(K)}$$
   - Evaluates whether user listens to/watches only one style ($0.0$) or an eclectic variety ($1.0$).
3. **Obscurity Score (0–100)**:
   $$\text{Obscurity} = 100 - \frac{1}{N}\sum \text{Popularity}_i$$
   - $0\text{--}45$: Leans mainstream
   - $46\text{--}54$: Balanced
   - $55\text{--}100$: Leans underground / obscure
4. **LLM Text Summary Block**: Formats a human-readable text payload:
    ```text
    Platform: Last.fm
    User: Bhavesh Soni
    Total scrobbles: 45,210
    Top genres: Art Rock (12), IDM (8), Ambient (7), Post-Rock (5)
    Top items:
      - Radiohead (1204) [Art Rock/Electronic]
      - Aphex Twin (980) [IDM/Ambient]
      - Godspeed You! Black Emperor (412) [Post-Rock]
    ```

---

### Step 5: LLM Prompt Engineering & Generation (`critique/prompts.py` & `critique/llm.py`)
1. **System Prompt Construction**:
   - Injects base constraints: Concise single-paragraph feedback of 4–6 sentences (70–115 words total, ~6–8 lines), strict tone adherence, no greetings/prefixes, no emojis, no em-dashes, no bullet points/enumerations.
   - Injects persona instructions according to selected tone (e.g. `roast`, `philosophical`, etc.) and context `{data}`.
2. **User Message**: Passes the raw `profile.text_summary`.
3. **API Request**:
   - Calls AgentRouter (`https://agentrouter.org/v1/chat/completions`) using model `gpt-5.6-sol` / `claude-opus-5` with WAF client headers.
   - Returns the generated critique text.

---

### Step 6: UI Presentation & Interaction (`critique_ui/`)

The Reflex UI uses `rx.el.*` native HTML elements with `class_name` props to apply the editorial CSS design system from `assets/critique.css`. All presentation decisions are encoded in CSS classes, not inline Python style dicts.

**Rendering pipeline:**
1. **Root (`critique_ui.py`)**: Applies `State.theme_class` (`dark-mode` or `light-mode`) and sets `--accent: {State.accent}` CSS custom property on the root element. Switching themes transforms the page between ink-black and warm archival parchment. Persona switches cause the entire page (meters, rules, buttons, drop caps, glow) to interpolate to the new color over 700ms.
2. **Atmosphere (`.atmos`)**: Fixed, GPU-isolated background layer (`contain: strict`, `pointer-events: none`) with hardware-accelerated drifting glow divs, static grain, and ghost print grid — strictly behind content and non-interfering with mouse/hit-testing.
3. **Header (`.kicker` & `.wordmark`)**: Header strip includes volume info, title, and the **Dark/Light Mode** toggle button (`.theme-toggle`).
4. **Input Panel (`.panel`)**: Platform selection renders as a `.tiles` grid (3×2 grid of `.tile` buttons with `.tile--on` active state). Username entry renders as `.field` + `.field__sigil` (`@`) + `.field__input`.
5. **Tone Selector (`.voices`)**: 5-column `.voice` button grid. Each card carries `--own: {persona_hex}` so its top hairline and selected state use its own color independently of the global `--accent`.
6. **Analyze Button (`.file-btn`)**: Full-width mono uppercase button with sheen-sweep hover animation.
7. **Working State (`.working`)**: Terminal-style Claude Code loading indicator featuring a rotating asterisk `✻` (`.claude-spinner`), dynamic randomly selected action verbs from a pool of 170+ gerunds (*Clauding, Caramelizing, Boondoggling, Baking, Mulling*, etc.), `.rail` progress bar animation, and `.skel` shimmer skeleton lines.
8. **Verdict Card (`.verdict`)**: Left-edge accent bar draws down (CSS `::before` animation), scan sweep plays once, `.verdict__body` paragraph displays the continuous roast/critique paragraph in distinctive literary typography (`Grenze Regular`), and `.ghost-btn` one-click copy button in footer. Provides a focused, single-paragraph editorial payoff without clutter.

---

## 3. Error Handling Flow

```
User Action ──> Validation Check (missing username / unconfigured API) ──> .slip error notice
            ──> API Request ──> HTTP 404 (User not found)             ──> .slip error notice
                            ──> HTTP 401/403 (Private profile)        ──> .slip error notice
                            ──> HTTP 429 / 5xx (Rate-limited/Down)    ──> Automatic 3-stage backoff retry
            ──> LLM Layer   ──> HTTP 401/403 (Unauthorized/Invalid Key)──> .slip error notice with config steps
                            ──> Fallback / Outage                     ──> .slip error notice (no stack traces)
```

The `.slip` component is a left-bordered rejection slip with a `.slip__label` (mono uppercase "Error") and `.slip__msg` (readable description). It replaces the Radix callout from the earlier implementation.

