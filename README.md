# 🎭 Critique — Media Taste Analyzer

Critique judges your media taste from your *real* activity data across six platforms, in
one of five voices — from savage roast to philosophical essay — and tells you how to
improve it.

It is also an exercise in a narrower question: **when an LLM app claims its output is
grounded in your data, how would you actually know?** The evaluation harness below is the
answer, and it is the most interesting part of this repository.

---

## 📐 Evaluation: measuring whether the model keeps its promises

An app like this rests on an unchecked assumption: that when the model names an album or a
film, that item is really in your data. Nothing verifies an instruction like "don't invent
things" by default. The app could hallucinate an album on every single request and no one
would notice — that gap is the difference between *calling* a language model and
*evaluating* one.

> **Read the status note before quoting numbers.** The prompt in `critique/prompts.py` is
> currently out of sync with the contract this harness measures, so no live score is
> published yet. Details in *Current status of the numbers* below.

```bash
python -m evals.run selftest      # validate the metric itself — no keys, no network
python -m evals.run run --dry     # exercise the harness on stub text
python -m evals.run run           # score the live model, 5 profiles x 5 tones
python -m evals.run report        # re-aggregate the newest saved run
```

### The headline metric

**Reference precision** — of every item reference the model made, what fraction were real
items from the user's profile?

```
reference_precision = real_references / (real_references + invented_references)
```

A critique naming four real albums scores `1.00`. One naming two real and two invented
scores `0.50`. Reported alongside it: `coverage@10` (did it engage with the top items or
name one and generalize?), `clean_rate` (share of outputs with *zero* inventions),
`length_ok_rate`, `rec_five_rate`, and `mean_latency_s`.

`clean_rate` sits next to the mean deliberately. A single badly hallucinating output is
worse for a user than the average implies, so the distribution matters more than its centre.

### Why detecting inventions is harder than detecting real references

This asymmetry is the substance of the problem. Confirming the model named a *real* item is
a lookup — normalize both strings, test containment, fall back to `SequenceMatcher` against
same-length token windows for typos and truncations (`FUZZY_THRESHOLD = 0.88`, tuned on the
labeled set).

Detecting an *invented* item has no list to check against. It requires first deciding which
spans of English prose were even *meant* as item references, which is open-ended. The
approach here is Title-Case span extraction plus a stoplist, with three refinements that
the labeled set forced:

1. **`and` is not a title joiner.** Allowing it collapsed "Pink Floyd and Joy Division"
   into one span, undercounting two inventions as one. `of`, `the`, `for`, `in`, `de`, `van`
   still join; `and` and `to` do not.
2. **Overlapping spans deduplicate longest-first**, so "Wong Kar-wai" is kept and the bare
   "Wong" nested inside it is not counted as a second invention.
3. **Sentence-opening single words go to a `weak` bucket**, excluded from the headline.
   "Keep following your instincts" shouldn't cost precision because "Keep" is capitalized.

Findings are therefore split into `hallucinations` (confident) and `weak` (probably prose).
Only the confident bucket feeds the headline, and the report labels them *candidates*
rather than verified inventions.

**Known false positive:** creator names. "Wong Kar-wai" is flagged when the model correctly
names the director of two films that *are* in the profile. A string matcher with no world
knowledge cannot distinguish a real director from an invented film. This is documented in
the labeled set rather than papered over, and it is exactly what embedding- or
knowledge-base-backed matching would fix.

### Tone-awareness, and why it matters

The `recommend` tone is *instructed* to name five items that are **not** in the user's data.
Scoring those as hallucinations penalizes the model for obeying the prompt — the first
version of this metric did precisely that and reported a spuriously low precision.

So for `recommend`, list lines are stripped before the invention scan and counted
separately. The diagnosis prose is still held to the grounding rule. The obvious way to
cheat that fix is to exempt the whole tone, so the labeled set contains
`recommend_bad_diagnosis`: same tone, same fixture, two invented films in the diagnosis. It
must still catch both while ignoring all five legitimate suggestions.

### Validating the evaluator

An unvalidated metric is just a number generator. `evals/scoring.py::LABELED` holds five
hand-labeled critiques with expected outcomes, and `selftest` fails loudly if the scorer
stops reproducing them:

| case | tests | precision |
|---|---|---|
| `clean_grounded` | well-grounded prose flags nothing | `1.00` |
| `recommend_five` | five novel suggestions are not inventions | `0.80` |
| `hallucinating` | three invented artists all found — separately | `0.40` |
| `recommend_bad_diagnosis` | but inventions in the diagnosis are caught | `0.33` |
| `generic_ungrounded` | vague flattery names nothing and *still* flags nothing | `0.00` |

All three refinements above were found this way, not by inspection.

### Deterministic fixtures

`evals/fixtures.py` holds five frozen `TasteProfile`s. Live fetches were rejected on
purpose: if the harness hit Last.fm and Jikan every run, a drop in score would be ambiguous
between "the prompt got worse" and "the API returned different data." Freezing the inputs
makes every movement attributable to the prompt or the model.

The fixtures cover the awkward cases, not the easy ones — opposite ends of the popularity
scale, scored mainstream items, a platform with `popularity=None` throughout, and a
non-media domain (`github`) proving the pipeline is domain-agnostic. They are built by the
real `summarize()`, so `text_summary` comes from the production code path.

### Design notes

- **Stdlib only.** `scoring.py` and `fixtures.py` import nothing outside the standard
  library and `critique/`, so the metric runs anywhere.
- **`critique.llm` is imported lazily**, inside the generation call, so `selftest`, `report`
  and `--dry` work with no `openai` installed and no keys configured.
- **One failure must not lose the rest.** Each generation is wrapped; a failure is stored as
  a card with `error` set, excluded from averages, and listed in the report.
- **Scoring and reporting are decoupled** through the results JSON, so a run can be
  re-aggregated after changing the report without paying for generation again.

### ⚠️ Current status of the numbers

`evals/results/` contains **`--dry` stub runs only — the harness has not yet scored the live
model**, so no reference-precision figure for a real model is published here yet.

A live run is also currently blocked on a **prompt/eval contract drift**: `critique/prompts.py`
no longer states the grounding rules or the 150–250 word contract that `evals/scoring.py`
measures, and the `recommend` tone's "5 items" instruction now conflicts with a
"single paragraph, no enumerations" output rule in `BASE_RULES`. Realigning the prompt with
the measured contract is a prerequisite to publishing any score. Tracked as the next task.

---

## 🌟 Platform coverage

Six integrations, each normalized into the same `TasteProfile`:

| Platform | Source | What it reads |
|---|---|---|
| **MyAnimeList** | Jikan, or official MAL API | anime/manga favorites, mean score, days watched, completion rate, genres |
| **Last.fm** | AudioScrobbler API | top artists, track scrobbles, listening history, listener-based obscurity |
| **Spotify** | Web API via OAuth 2.0 | top artists, top tracks, genres, track/artist popularity |
| **Letterboxd** | RSS feed (no official API) | film diary entries, star ratings, rewatches |
| **GitHub** | public REST API | repositories, stars, languages, topics |
| **Chess.com** | free PubAPI | Rapid/Blitz/Bullet/Daily/Tactics ratings, win rates, favorite openings |

### Five tones

🔥 **Roast** (witty, savage-but-clever) · 🎩 **Formal** (analytical cultural critic) ·
🤗 **Supportive** (warm; celebrates what your taste reveals about you) · 🧠 **Philosophical** (identity, memory,
meaning) · 🧭 **Recommend** (diagnoses blind spots, suggests 5 concrete new works)

---

## 🏗️ Architecture

A left-to-right pipeline where each stage has exactly one job:

```
UI (platform + username + tone)
  → Fetcher    (per-platform API/scrape)  → returns a normalized TasteProfile
  → Analysis   (stats + text_summary)
  → Prompt     (tone-specific system prompt)
  → LLM        (OpenAI-compatible endpoint)
  → UI         (verdict card + stats + copy-to-share)
```

**The one idea that matters:** every platform, however different its API, is squeezed into
the same `TasteProfile` shape. Analysis, prompting, and the UI therefore never know which
platform the data came from. **Adding a platform = one new fetcher plus four lines in the
registry module** (`import`, `_REGISTRY`, `DISPLAY_TO_KEY`, and the display `order` list).
**Nothing else changes.** The `github` and `chessdotcom` fetchers exist partly as proof — they
are not media platforms at all, and the downstream pipeline needed no modification.

Layers:

- **`critique/models.py`** — `MediaItem` / `TasteProfile`. The data contract.
- **`critique/fetchers/`** — one module per platform behind a `BaseFetcher` ABC.
  `base.py::get_json()` retries 3× with 0.8/1.6/2.4s backoff on 429/5xx/network errors,
  while treating 404 and 401/403 as definitive and never retrying them.
- **`critique/analysis.py`** — normalized **Shannon entropy** over the genre distribution as
  a 0–1 diversity score (`0` = one-note, `1` = eclectic), and a 0–100 **obscurity** score
  inverting mean item popularity. Platform-agnostic: reads only `top_items` and `stats`.
  Each *fetcher* is responsible for normalizing its platform's native popularity signal onto
  the shared 0–100 scale first — **log-scaled** for the platforms reporting raw audience
  counts (MyAnimeList members, Last.fm listeners, GitHub stars), passed through directly
  where the API already returns a bounded score (Spotify).
- **`critique/prompts.py`** — system prompt = personality/tone; user message = the real data
  summary. Shared `BASE_RULES` keep every tone grounded.
- **`critique/llm.py`** — provider-agnostic. Anything speaking OpenAI `chat/completions`
  works, including a streaming variant for SSE. Swap providers with three env vars and zero
  code change.
- **`evals/`** — the harness described above.

### Frontends

Three entry points share the identical pipeline:

```bash
reflex run                                    # Reflex component UI (critique_ui/)
python -m uvicorn api:app --reload            # FastAPI + SSE streaming -> :8000/docs
streamlit run app.py                          # original Streamlit UI -> :8501
```

---

## 🚀 Quick start

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements.txt
cp .env.example .env          # then fill it in
```

Only the LLM variables are required. Every platform key is optional — unconfigured
platforms simply fail with a clear message.

```ini
LLM_BASE_URL=https://api.openai-compatible-provider.example/v1
LLM_API_KEY=your_key_here
LLM_MODEL=your_model_here

LASTFM_API_KEY=            # last.fm/api/account/create — free, instant
SPOTIFY_CLIENT_ID=         # developer.spotify.com/dashboard
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://localhost:8501   # match your frontend's port (8501 Streamlit / 8000 FastAPI)
MAL_CLIENT_ID=             # optional: unlocks the full anime list vs. stats+favorites
```

Verify the install with no keys and no network:

```bash
python -m evals.run selftest
```

---

## 🔭 Next

- Realign `prompts.py` with the contract `evals/` measures, then publish a live score.
- Replace exact/fuzzy matching with **sentence-embedding similarity**, to catch aliases the
  matcher misses today ("Attack on Titan" vs. "Shingeki no Kyojin") and to give the
  invention detector a real notion of whether a flagged span denotes a plausible existing
  work.
- Easy further platforms, given the architecture: AniList, Trakt, Steam.

---

## 📄 License

MIT.
