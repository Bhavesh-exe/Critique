# CLAUDE.md — Critique project context

> **Purpose:** everything Claude needs to know to pick this project up cold in a new chat.
> Claude Code loads this file automatically in any session started in this folder.
> **Last updated:** 2026-08-23

---

## 1. What we're building

**Critique** — a web app that judges a user's **media taste** from their *real* activity data
and tells them how to improve it.

Flow: user picks a **platform** → enters a **username** (or logs in, for Spotify) → picks a
**tone** → gets an **AI-generated critique** of their taste.

**Why this project exists:** it's Bhavesh's portfolio piece targeting **ML/SWE internships**.
It deliberately touches NLP + API integration + LLM prompt engineering + **LLM evaluation** +
full-stack deployment, and it's *shareable*, which gives it organic reach. Being memorable in
interviews is an explicit goal.

**The strongest asset for that goal is `evals/`** — a hallucination-detection metric that is
itself validated against a hand-labeled set. Lead with it in any resume/README/interview
framing; the six platform integrations are supporting breadth, not the headline. Most student
LLM projects call an API; very few evaluate one.

---

## 2. Locked decisions — do not re-litigate these

| Decision | Choice | Notes |
|---|---|---|
| **LLM access** | **OpenAI-compatible `chat/completions`** via the `openai` SDK | Base URL / key / model are **config only**, so any compatible provider is a drop-in swap with zero code change. |
| **Platforms** | **Six, all implemented** | MyAnimeList, Last.fm, Spotify, Letterboxd, GitHub, Chess.com. |
| **Letterboxd scope** | **RSS-first** | Uses the stable `/{u}/rss/` feed; deeper HTML scraping is an optional later enhancement. |
| **Tones** | 5: `roast`, `formal`, `supportive`, `philosophical`, `recommend` | `recommend` is the "suggest how to improve" mode. |
| **Fixtures** | **Frozen, never live fetches** | So score movement is attributable to the prompt/model, not upstream data drift. Don't "improve" this by making evals hit real APIs. |

### Superseded (was locked, then changed — don't be confused by older notes)
- **Frontend was "Streamlit only."** It is now **three frontends** sharing one pipeline:
  Reflex (`critique_ui/`, the primary UI), FastAPI + SSE (`api.py`), and the original
  Streamlit (`app.py`). All three call the identical pipeline.
- **Provider was "AgentRouter."** Treat the provider as unspecified/config — see §8.

### ⚠️ 2a. THE GIT RULE (most important thing in this file)

**Critique must live in its OWN brand-new git repo.** The user's git repo is currently rooted
at their **home directory** (`C:\Users\BHAVESH SONI`) and tracks a **`python-projects`** remote.

- **NEVER** commit Critique to that `python-projects` repo.
- **NEVER** run `git add` / `git commit` from the home directory (it would stage the entire
  home folder).
- When the time comes: a fresh `git init` **inside** `critique/`.
- `git init` has **still not been run.** Nothing is on GitHub. This is the highest-value
  remaining task — the work is strong and currently invisible.

---

## 3. Environment (verified, not assumed)

- **OS:** Windows 11 Home Single Language, shell is **git bash** (POSIX sh — use `/dev/null`,
  forward slashes).
- **Project dir:** `C:\Users\BHAVESH SONI\OneDrive\Desktop\critique`
- **Python 3.14.0** — venv at `.venv/`. Invoke as `.venv/Scripts/python.exe`.
- Node v24.12.0, npm 11.6.2 — **now actually used**, because Reflex compiles a React
  frontend into `.web/`.

### ✅ The Python 3.14 gate — PASSED, don't re-check
Installed and import-verified: `streamlit 1.62.0`, `pyarrow 25.0.1`, `openai 3.3.1`,
`spotipy 2.26.0`, `beautifulsoup4 4.15.0`, `feedparser 6.0.14`, `python-dotenv 1.2.3`,
`pydantic 2.13.4`, plus `fastapi`, `uvicorn`, `reflex`. **No Python downgrade needed.**

`rxconfig.py` contains a real workaround: it clears `rx_constants.PackageJson.OVERRIDES` to
dodge a strict `EOVERRIDE` conflict between npm 11 / Node 24 and Reflex 0.9.8. Don't remove it.

---

## 4. Architecture — the one idea that matters

```
UI (platform + username + tone)
  → Fetcher    (per-platform API/scrape)  → returns a normalized TasteProfile
  → Analysis   (stats + text_summary)
  → Prompt     (tone-specific system prompt)
  → LLM        (OpenAI-compatible)
  → UI         (verdict card + stats pills + copy-to-share)
```

*Every* platform, however different its API, is squeezed into the **same `TasteProfile`
shape**. Analysis, prompting, and the UI therefore never know which platform the data came
from. **Adding a platform = one new fetcher + one registry line. Nothing else changes.**

`github` and `chessdotcom` are proof of this: neither is a media platform, and nothing
downstream needed modification.

Prompt separation: **system message = personality/tone**, **user message = the real data
summary**.

---

## 5. Files that exist right now

```
critique/
├── app.py                  # original Streamlit UI
├── api.py                  # FastAPI: /api/critique, /api/critique/stream (SSE),
│                           #   /api/spotify/authorize + /callback, /api/meta, /api/health
├── rxconfig.py             # Reflex config (dark, ruby accent) + npm-override workaround
├── README.md               # leads with the evaluation story
├── Dockerfile
├── requirements.txt        # ⚠ unpinned, and its header still calls this a Streamlit project
├── .env                    # REAL keys present (LLM + Last.fm + Spotify)
├── .env.example
├── .gitignore
├── .streamlit/             # config.toml + secrets.toml.example
├── critique/               # the core package
│   ├── models.py           # MediaItem, TasteProfile  ← THE DATA CONTRACT
│   ├── config.py           # Settings; @property accessors, st.secrets first then .env
│   ├── prompts.py          # BASE_RULES + TONES + TONE_ORDER + build(tone, data=None)
│   ├── llm.py              # is_configured(), generate_critique(), stream_critique()
│   ├── analysis.py         # summarize(): Shannon-entropy diversity, obscurity, _render()
│   └── fetchers/
│       ├── __init__.py     # _REGISTRY — all six registered
│       ├── base.py         # BaseFetcher ABC, FetchError, get_json() w/ retry+backoff
│       ├── myanimelist.py  lastfm.py  spotify.py  letterboxd.py  github.py  chessdotcom.py
├── critique_ui/            # Reflex frontend
│   ├── critique_ui.py  state.py  styles.py
│   └── components/         # header, platform_input, tone_selector, verdict_card,
│                           #   stats_display, raw_accordion
├── evals/                  # ★ the evaluation harness — the resume centrepiece
│   ├── run.py              # selftest | run [--dry] | report
│   ├── scoring.py          # reference precision + LABELED set + selftest()
│   ├── fixtures.py         # 5 frozen TasteProfiles (PROFILES dict)
│   ├── README.md           # excellent write-up of the metric and its limits
│   └── results/            # ⚠ only --dry stub runs so far
└── brag-output/            # resume bullets + shareable brag card (generated 2026-08-23)
```

Also present: `ai.ts`, `GEMINI.md`, `flow.md`, `implementation.md`, `wid.md`, `assets/`,
`package.json`, `.web/` (Reflex build output — gitignore it), `.states/` (Reflex state pickles
— gitignore these too).

**Still does not exist:** any git repo; a deployment.

### Notable implementation details
- `base.py::get_json()` retries **3×** with 0.8/1.6/2.4s backoff on 429 + 5xx + network
  errors. 404 → "double-check the username"; 401/403 → "private or invalid key". Never
  retries those.
- `config.py` uses **@property** accessors (not class constants) so values are read lazily.
- `llm.py` calls `chat.completions.create(temperature=0.9, max_tokens=700)` and has a
  streaming twin used by the SSE endpoint.
- `myanimelist.py::_mainstream_from_members()` maps MAL member count to a 0-100 mainstream
  score on a **log scale**. Jikan is polite-delayed 0.4s between enrichment calls.
- `evals/scoring.py` is **stdlib-only** and `critique.llm` is imported **lazily**, so
  `selftest` / `report` / `--dry` all work with no keys and no `openai` installed.

---

## 6. Status: what's done vs. pending

### ✅ Done and verified
- **All six fetchers written and registered.**
- **Core pipeline (models → analysis → prompts) validated end-to-end.**
- **Three frontends** (Reflex, FastAPI+SSE, Streamlit) over one pipeline.
- **Eval harness built, and `selftest` passes** — re-verified 2026-08-23, all 5 labeled cases
  reproduce (precision 1.00 / 0.80 / 0.40 / 0.33 / 0.00).

### 🐛 Bugs found and fixed (don't reintroduce)
`diversity` was `unique_genres / num_items`, which returned **2.0** for a supposed 0-1 metric
(items have multiple genres each). Replaced with **normalized Shannon entropy** of the genre
distribution: `entropy / log(n_genres)`. Verified: one-note → `0.0`, eclectic → `0.97`.

### 🔴 Open bug — PROMPT/EVAL CONTRACT DRIFT (fix before any live eval)
`prompts.py` was rewritten and no longer makes the promises `evals/` measures. Verified by
grep against `prompts.py` on 2026-08-23:

| `evals/` measures | `prompts.py` now |
|---|---|
| "Reference SPECIFIC titles… Name them" | **absent** (0 matches) |
| "NEVER invent items that aren't in the data" | **absent** (0 matches) |
| 150–250 words (`WORD_MIN`/`WORD_MAX`) | contradicted — "about 5-6 sentences" |
| `recommend` emits 5 list lines (`rec_five_rate`) | contradicted — "no bullet points or enumerations" |

Running the live eval as-is collapses `length_ok_rate` and `rec_five_rate` toward 0 and makes
`reference_precision` measure grounding the model was never asked for. **Realign first.**

Also latent: `build(tone)` is called **without** a `data` argument at **five** call sites —
`evals/run.py:71`, `api.py:221`, `api.py:254`, `app.py:161`, `critique_ui/state.py:279` — so
the system prompt's CONTEXT block renders the
literal placeholder `"the user-submitted media activity and profile data"` while the real
summary arrives as the user message. The `{data}` slot is dead in every code path — either
wire it up or remove it from `BASE_RULES`.

### ⏳ Pending
1. Fix the drift above → re-run `selftest` → **then** `python -m evals.run run` for a real
   score. No published number exists yet.
2. Remove the spoofed client headers from `llm.py` (§8) and repoint at a first-party key.
3. `git init` (inside `critique/`!), then push.
4. Pin `requirements.txt` and fix its stale Streamlit-only header.
5. Deploy. Note Streamlit Cloud only serves `app.py`; Reflex/FastAPI need a container
   (a `Dockerfile` already exists) on Railway/Render/Fly.

---

## 7. Known external issue: Jikan flakiness

The MyAnimeList fetcher goes through Jikan, which was broadly degraded on 2026-08-21
(`/v4/users/{u}/statistics` → 504 across 5 usernames; also 429s above ~3 req/sec). The
retry/backoff in `base.py` exists to ride out the intermittent case. **This is external, not
our bug** — but MAL has still never been confirmed live, so re-test before assuming.

---

## 8. ⚠️ The LLM provider situation — read before touching `llm.py`

`llm.py` defines `DEFAULT_CLIENT_HEADERS` that identify the app as `claude-cli/0.2.29` with
`anthropic-beta: claude-code-20250219`. That is impersonating a different client to reach a
third-party reseller endpoint (`agentrouter.org`).

**As of 2026-08-23 the key returns `401 unauthorized client detected` on both
`/chat/completions` and `/models`** — the provider appears to have started detecting it. So
this path is now blocked in practice as well as being a problem in principle.

Do not help extend or work around this. Two concrete harms: it likely breaches the upstream
terms, and an interviewer opening `llm.py` on a portfolio project sees header spoofing.

**The fix is config-only, by the project's own design:** point `LLM_BASE_URL` /
`LLM_API_KEY` / `LLM_MODEL` at a first-party provider (Anthropic, OpenAI, Groq, or Gemini's
compat endpoint — several have free tiers) and delete the header block. Zero code change, and
the provider-agnostic architecture becomes a talking point instead of a liability.

Keys the user has supplied: `LLM_*`, `LASTFM_API_KEY`, `SPOTIFY_CLIENT_ID`/`_SECRET`/
`_REDIRECT_URI`. Not set: `MAL_CLIENT_ID` (optional — unlocks the full anime list).

---

## 9. How to run

```bash
reflex run                                                  # Reflex UI (primary)
.venv/Scripts/python.exe -m uvicorn api:app --reload        # FastAPI -> :8000/docs
.venv/Scripts/python.exe -m streamlit run app.py            # Streamlit -> :8501
```

Check the eval harness with no keys and no network:
```bash
.venv/Scripts/python.exe -m evals.run selftest
```

Quick pipeline check without keys or network:
```bash
.venv/Scripts/python.exe -c "from critique.models import *; from critique.analysis import summarize; p=TasteProfile(platform='x',username='u'); p.top_items=[MediaItem('A','anime',['Action','Sci-Fi'],popularity=50)]; summarize(p); print(p.text_summary)"
```

---

## 10. Working preferences observed

- The user wants to **understand the plan** before code lands — explain the *how*, not just
  the *what*.
- **Verify against reality rather than assuming.** The 3.14 gate, the diversity bug, the
  Jikan outage, and the prompt/eval drift were all caught by actually running things. Keep
  doing that. Corollary: **this file has been wrong before** — check the filesystem rather
  than trusting it.
- Prefers being told directly when something is blocked or when an approach is a bad idea,
  rather than getting a plausible-looking artifact built on a broken foundation.
- Full plan document lives at
  `C:\Users\BHAVESH SONI\.claude\plans\expressive-crunching-cookie.md`.
- Note: `WebSearch`/`WebFetch` have been unreliable here, and sandboxed sessions may have
  PyPI/npm blocked (403 proxy) — so don't count on installing packages or live doc lookups.
