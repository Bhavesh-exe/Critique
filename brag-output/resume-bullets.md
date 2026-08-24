# Critique — resume & interview material

Written 2026-08-23. Every claim below is traceable to code in this repo.
Anything not yet verified is marked **[UNVERIFIED]** — do not put those on a resume
until the run behind them exists.

---

## The framing that matters

Most student LLM projects are "I called an API and rendered the response." Yours has
something the large majority do not: **an evaluation harness with a validated metric.**
That single asset is the difference between *using* a model and *evaluating* one, and it
is exactly the distinction ML interviews probe for.

So lead with the eval. The six platform integrations are supporting evidence of
engineering breadth; they are not the headline. A recruiter skimming six API names sees a
CRUD project. A recruiter seeing "built a hallucination-detection metric and validated it
against a hand-labeled set" sees an ML engineer.

---

## Primary bullets — ML/AI-focused roles

Use three to four of these. Ordered by strength.

- Built an **LLM evaluation harness** measuring output grounding for a
  multi-platform taste-critique app: defined *reference precision* — the share of item
  references in a generation that are real items from the user's profile versus
  hallucinated — over a **25-cell matrix of 5 frozen profile fixtures × 5 prompt tones**.

- **Validated the evaluator itself** against 5 hand-labeled critiques with expected
  outcomes, so the metric is regression-tested rather than assumed correct; the labeled
  set reproduces precision values of 1.00, 0.80, 0.40, 0.33 and 0.00 across
  clean, tone-compliant, hallucinating, and deliberately-ungrounded cases.

- Designed the invention detector around the **asymmetry that finding hallucinated
  references is strictly harder than finding real ones** — real items are a lookup, while
  inventions require first deciding which prose spans were *meant* as references.
  Implemented Title-Case span extraction with a 173-term stoplist, Unicode NFKD
  normalization, and `SequenceMatcher` fuzzy matching (threshold 0.88) against
  same-length token windows to absorb typos and truncations.

- Split findings into **confident and weak buckets** so only high-confidence spans reach
  the headline number, and **documented a known false-positive class** (creator names —
  a string matcher with no world knowledge cannot distinguish a real director from an
  invented film) rather than hiding it; specified sentence-embedding similarity as the
  principled fix.

- Made the metric **tone-aware after it reported a spuriously low precision**: one prompt mode
  is *instructed* to name items absent from the user's data, so scanning its suggestions
  penalized the model for obeying the prompt. Excluded those list lines while keeping the
  surrounding diagnosis under the grounding rule, and added an adversarial labeled case to
  block the obvious cheat of exempting the whole mode.

- Chose **deterministic frozen fixtures over live API fetches** so score movement is
  attributable to the prompt or model rather than upstream data drift; selected fixtures
  for edge coverage — opposite ends of the popularity scale, a platform with
  `popularity=None` throughout, and a non-media domain to prove the pipeline is
  domain-agnostic.

- Reported **`clean_rate` alongside the mean deliberately**, on the reasoning that one
  badly hallucinating output harms a user more than the average implies — the
  distribution matters more than its center.

---

## Secondary bullets — SWE / full-stack breadth

- Architected a **six-platform ingestion layer** (MyAnimeList, Last.fm, Spotify,
  Letterboxd, GitHub, Chess.com) normalizing every API into one `TasteProfile` dataclass,
  so the analysis, prompting, and UI layers are entirely platform-agnostic and adding a
  platform touches exactly one new file plus four lines in the registry module.

- Implemented **error-class-aware HTTP retry logic**: up to 4 attempts (1 initial + 3
  retries) with 0.8/1.6/2.4s linear backoff for transient 429 and 5xx failures, while
  treating 404 and 401/403 as definitive and never retrying them — each mapped to a distinct
  user-facing message.

- Computed taste metrics from raw activity: **normalized Shannon entropy** over the genre
  distribution as a 0–1 diversity score (`entropy / log(n_genres)`), and a 0–100 obscurity
  score inverting mean item popularity — where each fetcher first normalizes its platform's
  native popularity signal onto a shared scale, **log-scaling audience size** for the
  platforms that report raw counts rather than a bounded score.

- Built a **FastAPI backend with server-sent-event streaming** so verdicts render
  progressively, plus a **Reflex** component UI and **Spotify OAuth 2.0** authorization flow.

- Kept the LLM layer **provider-agnostic** behind the OpenAI-compatible `chat/completions`
  contract, so switching providers is a three-variable config change with zero code change.

- Wrote the scorer and fixtures **stdlib-only** with the model client imported lazily, so
  the entire harness — self-test, dry run, and report aggregation — runs with no API keys,
  no network, and no dependencies installed.

---

## One-line project descriptions

**Shortest:**
> Critique — LLM app that judges media taste from six platform APIs, with an evaluation
> harness measuring output grounding via a validated hallucination-detection metric.

**With the ML emphasis:**
> Critique — Python/FastAPI app generating tone-conditioned critiques of a user's media
> taste from six platform integrations, evaluated by a custom reference-precision metric
> that is itself regression-tested against a hand-labeled set.

---

## Interview talking points

These are the moments where you sound like an engineer rather than a tutorial follower.
Each is a real decision recorded in the code.

**"Tell me about a bug that taught you something."**
Diversity was originally `unique_genres / num_items`, which returned 2.0 for a supposed
0–1 metric — items carry multiple genres each, so the denominator was wrong. Replaced with
normalized Shannon entropy. The lesson is that a metric with no valid range check will
happily report nonsense; it was caught by running it, not by reading it.

**"How do you know your evaluation is correct?"**
This is the strongest thing you have. An unvalidated metric is a number generator. The
scorer is held to five hand-labeled critiques, and all three refinements to the extraction
heuristic — that `and` is not a title joiner, that overlapping spans deduplicate
longest-first, that sentence-opening single words go to a weak bucket — were discovered by
those labels failing, not by inspection.

**"What are the limits of your approach?"**
Reference precision is string matching, so it cannot tell "Attack on Titan" from
"Shingeki no Kyojin", and it flags creator names as inventions. Embedding-based similarity
fixes both, and would give the detector a real notion of whether a flagged span denotes a
plausible existing work. Knowing this is more impressive than pretending the metric is
clean.

**"Your worst case scores 0.00 — did the model invent everything?"**
No, and this is a good question to be ready for. Precision is undefined at a 0/0 denominator
and the scorer reports it as `0.0` by convention. The `generic_ungrounded` case is vague
flattery that names *nothing* — zero real references and zero inventions — so it is a
grounding failure of a different kind: not hallucination, but total non-engagement with the
user's data. That is exactly why `coverage@10` is reported next to precision; precision alone
cannot tell those two failures apart.

**"What would you do differently?"**
See the drift issue below — noticing that your own eval and your own prompt had silently
diverged is a mature answer about the cost of untested coupling.

---

## ⚠ Fix this before you cite any live number

**[UNVERIFIED]** — the harness has never scored the live model. `evals/results/` contains
only `--dry` stub runs, so there is currently no real reference-precision figure. I tried
to produce one and could not: this sandbox has PyPI and npm blocked, the project `.venv` is
a Windows build, and AgentRouter returned `401 unauthorized client detected` on both
`/chat/completions` and `/models`.

**More importantly, a live run right now would produce meaningless numbers**, because
`critique/prompts.py` has been rewritten and no longer makes the promises the harness
measures. Verified by grep against `prompts.py`:

| The harness measures | Status in `prompts.py` |
|---|---|
| "Reference SPECIFIC titles… Name them" | **absent** (0 matches) |
| "NEVER invent items that aren't in the data" | **absent** (0 matches) |
| 150–250 word contract (`WORD_MIN/WORD_MAX`) | contradicted — now "about 5-6 sentences" |
| `recommend` emits 5 list lines (`rec_five_rate`) | contradicted — "no bullet points or enumerations" |

Consequences if run as-is: `length_ok_rate` collapses toward 0, `rec_five_rate` collapses
toward 0, and `reference_precision` measures grounding the model was never asked for.

There is also a latent bug: `build(tone)` is called without a `data` argument in both
`evals/run.py::_generate` and at four other call sites (`api.py:221`, `api.py:254`,
`app.py:161`, `critique_ui/state.py:279`), so the system prompt's CONTEXT block renders
the literal placeholder *"the user-submitted media activity and profile data"* while the
real summary arrives as the user message. The `{data}` slot is dead in every code path.

**Order of work:** restore the grounding and length rules to `BASE_RULES` (and resolve the
paragraph-vs-list conflict for `recommend`) → re-run `selftest` → then
`python -m evals.run run` → then quote the number.

---

## ⚠ One credibility risk to deal with

`critique/llm.py` defines `DEFAULT_CLIENT_HEADERS` that identify the app as
`claude-cli/0.2.29` with `anthropic-beta: claude-code-20250219` headers. That is
impersonating a different client to reach a third-party reseller endpoint, and it is very
likely why the key now returns `unauthorized client detected` — the provider appears to
have started detecting it.

Two reasons to remove it before this repo is public. It probably breaches the upstream
terms, and an interviewer who opens `llm.py` — a file they *will* open, since it is where
the LLM call lives — sees header spoofing on a portfolio project. That is an avoidable
first impression.

The fix is cheap and you already designed for it: the provider layer is config-only, so
point `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` at a first-party key (Anthropic, OpenAI,
Groq, and Gemini's compat endpoint all speak this format; several have free tiers) and
delete the header block. Zero code change, and the provider-agnostic design becomes a
talking point instead of a liability.

---

## Also still open

- **No git repo.** `git init` has never run, so none of this is on GitHub and nobody can
  look at it. This is the highest-value remaining task by a wide margin — the work is
  strong and currently invisible. Remember the rule in `CLAUDE.md`: init *inside*
  `critique/`, never from the home directory.
- **Not deployed**, so there is no demo link for a resume header.
- `requirements.txt` still describes itself as a Streamlit project and pins nothing.
