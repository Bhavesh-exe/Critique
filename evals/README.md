# Evaluation harness

Measures whether the model actually keeps the promises the prompt makes.

`critique/prompts.py` tells the model three checkable things:

> "Reference SPECIFIC titles/artists/films/repos/openings from the data. Name them."
> "NEVER invent items that aren't in the data."
> "Keep it to 150-250 words."

Before this harness existed, nothing verified any of them. The app could have been
inventing albums on every request and no one would have known. That is the gap
between *calling* a language model and *evaluating* one, and it is the only part
of an LLM application that produces a number you can defend.

```bash
python -m evals.run selftest      # validate the metric itself — no keys, no network
python -m evals.run run --dry     # exercise the whole harness on stub text
python -m evals.run run           # score the live model, 5 profiles x 5 tones
python -m evals.run report        # re-aggregate the newest saved run
```

## The headline metric

**Reference precision** — of every item reference the model made, what fraction
were real items from the user's profile?

```
reference_precision = real_references / (real_references + invented_references)
```

A critique naming four real albums scores `1.00`. One naming two real and two
invented scores `0.50`. Reported alongside it:

| metric | question it answers |
|---|---|
| `coverage@10` | did it engage with the user's top items, or name one and generalise? |
| `clean_rate` | what share of outputs contained *zero* inventions? |
| `length_ok_rate` | does it obey the 150-250 word contract? |
| `rec_five_rate` | does the `recommend` tone actually produce five items? |
| `mean_latency_s` | cost of a generation |

`clean_rate` is reported next to the mean deliberately. A single badly
hallucinating output is worse for a user than the average implies, so the
distribution matters more than its centre.

## Why finding inventions is harder than finding real references

This asymmetry is the interesting part of the problem.

Checking whether the model named a *real* item is a lookup: normalise both
strings, test for containment, and fall back to `SequenceMatcher` against
same-length token windows for typos and truncations (`FUZZY_THRESHOLD = 0.88`,
tuned on the labeled set).

Detecting an *invented* item has no such list to check against. It requires
first deciding which spans of English prose were even *meant* to be item
references — an open-ended problem. The approach here is Title Case span
extraction plus a stoplist, with three refinements the labeled set forced:

1. **`and` is not a title joiner.** Allowing it collapsed "Pink Floyd and Joy
   Division" into one span and undercounted two inventions as one. `of`, `the`,
   `for`, `in`, `de`, `van` and friends still join; `and` and `to` do not.
2. **Overlapping spans are deduplicated longest-first.** Otherwise
   "Wong Kar-wai" and the bare "Wong" nested inside it count as two separate
   inventions.
3. **Sentence-opening single words go to a `weak` bucket**, excluded from the
   headline number. "Keep following your instincts" should not cost the model
   precision because "Keep" is capitalised.

Because the detector is a heuristic, findings are split into `hallucinations`
(confident) and `weak` (probably prose). Only the confident bucket feeds the
headline, and the report labels the list as *candidates* rather than verified
inventions.

### Known false positive: creator names

"Wong Kar-wai" gets flagged when the model correctly names the director of two
films that *are* in the profile. A string matcher with no world knowledge cannot
tell a real director from an invented film. This is documented in the labeled
set rather than papered over, and it is exactly what embedding- or
knowledge-base-backed matching would fix.

## Tone-awareness, and why it matters

The `recommend` tone is *instructed* to name five items that are **not** in the
user's data. Scoring those as hallucinations penalises the model for obeying the
prompt — the first version of this metric did precisely that and reported a
false `0.40` precision.

So for `recommend`, list lines are stripped before the invention scan and counted
separately as `recommendations`. The diagnosis prose is still held to the
grounding rule.

The obvious way to cheat that fix is to exempt the whole tone from the check, so
the labeled set contains `recommend_bad_diagnosis`: same tone, same fixture, but
with two invented films in the diagnosis. It must still catch both while ignoring
all five legitimate suggestions.

## Validating the evaluator

An unvalidated metric is just a number generator. `evals/scoring.py::LABELED`
holds five hand-labeled critiques with expected outcomes, and `selftest` fails
loudly if the scorer stops reproducing them:

| case | tests |
|---|---|
| `clean_grounded` | well-grounded prose scores `1.00` and flags nothing |
| `hallucinating` | three invented artists are all found — separately |
| `generic_ungrounded` | vague flattery names nothing and *still* flags nothing |
| `recommend_five` | five novel suggestions are not inventions |
| `recommend_bad_diagnosis` | but invented items in the diagnosis are |

Every change to the extraction heuristics runs against these first. All three
refinements listed above were found this way, not by inspection.

## Deterministic fixtures

`evals/fixtures.py` holds five frozen `TasteProfile`s. Live fetches were
rejected on purpose: if the harness hit Last.fm and Jikan every run, a drop in
score would be ambiguous between "the prompt got worse" and "the API returned
different data." Freezing the inputs makes every movement in the numbers
attributable to the prompt or the model.

The fixtures are chosen to cover the awkward cases, not the easy ones:

- `lastfm_mainstream` / `lastfm_obscure` — opposite ends of the popularity scale
- `myanimelist` — scored items, mainstream shonen
- `letterboxd` — **`popularity=None` throughout**, since several platforms
  provide no popularity signal at all
- `github` — a non-media domain, proving the pipeline is domain-agnostic

They are built by the real `summarize()`, so `text_summary` comes from the
production code path rather than a hand-written approximation of it.

## Design notes

- **Stdlib only.** `scoring.py` and `fixtures.py` import nothing outside the
  standard library and `critique/`, so the metric runs anywhere.
- **`critique.llm` is imported lazily**, inside the generation call. `selftest`,
  `report` and `--dry` therefore work with no `openai` installed and no keys
  configured — the harness is testable independently of the model.
- **One failure must not lose the rest.** Each generation is wrapped; a failure
  is stored as a card with `error` set, excluded from the averages, and listed
  in the report instead of vanishing.
- **Scoring and reporting are decoupled** through the results JSON, so a run can
  be re-aggregated after changing the report without paying for generation again.

## Next

Reference precision is a *string-matching* metric. Replacing exact and fuzzy
matching with sentence-embedding similarity would catch aliases the matcher
misses today — "Attack on Titan" versus "Shingeki no Kyojin" — and would give the
invention detector a real notion of whether a flagged span denotes a plausible
existing work.
