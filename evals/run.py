"""Eval runner: score generated critiques across fixtures and tones.

    python -m evals.run selftest              # validate the metric, no API calls
    python -m evals.run run --dry             # exercise the whole harness, no API calls
    python -m evals.run run                   # score the live model
    python -m evals.run run --tones roast recommend --profiles letterboxd
    python -m evals.run report                # re-aggregate the newest saved run
    python -m evals.run report evals/results/run-20260822-1930.json

Design notes worth knowing before changing this file:

* `critique.llm` is imported **inside** `_generate`, not at module level. That
  keeps `selftest`, `report` and `--dry` working on machines with no `openai`
  installed and no keys configured — which is what makes the harness itself
  testable rather than only the model.
* One failed generation must not lose the other N-1. Every call is wrapped, and
  a failure is recorded as a card with `error` set so it shows up in the report
  instead of vanishing.
* Results are written as JSON, and `report` reads that JSON back. Scoring and
  reporting are therefore decoupled: you can re-aggregate an old run after
  changing the report, without paying for generation again.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

from critique.prompts import TONE_ORDER, build
from evals import fixtures
from evals.scoring import ScoreCard, score, selftest

RESULTS_DIR = Path(__file__).resolve().parent / "results"


# --------------------------------------------------------------------------- #
# generation
# --------------------------------------------------------------------------- #
def _dry_text(profile, tone: str) -> str:
    """A deterministic stand-in for a real generation.

    Deliberately imperfect: it names three real items, invents one, and for the
    `recommend` tone emits five list lines. That way a --dry run produces
    non-trivial numbers and exercises every branch of the scorer, which is how
    the harness gets tested without spending tokens.
    """
    titles = [it.title for it in profile.top_items]
    real = ", ".join(titles[:3]) if titles else "nothing much"
    filler = (
        "This is stub output used to exercise the harness, padded so the length "
        "check has something to bite on. "
    )
    body = (
        f"Looking at {real}, a pattern is visible. {filler * 6}"
        f"The presence of Bogus Invented Title here undercuts the rest."
    )
    if tone == "recommend":
        body += "\n" + "\n".join(
            f"{i}. Placeholder Suggestion {i} — reason {i}." for i in range(1, 6)
        )
    return body


def _generate(profile, tone: str, dry: bool) -> tuple[str, float]:
    """Return (critique_text, latency_seconds). Raises on failure."""
    system = build(tone)
    user = profile.text_summary
    t0 = time.perf_counter()
    if dry:
        text = _dry_text(profile, tone)
    else:
        # Imported here on purpose — see the module docstring.
        from critique.llm import generate_critique

        text = generate_critique(system, user)
    return text, round(time.perf_counter() - t0, 2)


# --------------------------------------------------------------------------- #
# aggregation
# --------------------------------------------------------------------------- #
def _mean(xs: list[float]) -> float:
    return round(statistics.fmean(xs), 3) if xs else 0.0


def aggregate(cards: list[dict]) -> dict:
    """Roll a list of card dicts into per-tone and overall summaries."""
    good = [c for c in cards if not c.get("error")]

    def block(rows: list[dict]) -> dict:
        if not rows:
            return {"n": 0}
        return {
            "n": len(rows),
            "reference_precision": _mean([r["reference_precision"] for r in rows]),
            "coverage_at_10": _mean([r["coverage_at_10"] for r in rows]),
            # Fraction of generations containing at least one invented item.
            # Reported alongside the mean because one badly-hallucinating output
            # matters more than the average suggests.
            "clean_rate": _mean([1.0 if r["hallucination_count"] == 0 else 0.0 for r in rows]),
            "mean_hallucinations": _mean([float(r["hallucination_count"]) for r in rows]),
            "length_ok_rate": _mean([1.0 if r["words_in_range"] else 0.0 for r in rows]),
            "mean_words": _mean([float(r["word_count"]) for r in rows]),
            "mean_latency_s": _mean([float(r["latency_s"]) for r in rows if r.get("latency_s")]),
        }

    by_tone = {t: block([c for c in good if c["tone"] == t]) for t in TONE_ORDER}
    by_tone = {t: b for t, b in by_tone.items() if b["n"]}
    by_platform = {}
    for c in good:
        by_platform.setdefault(c["platform"], []).append(c)
    by_platform = {p: block(rows) for p, rows in sorted(by_platform.items())}

    # Which invented spans recur — the actionable output, since a span that
    # shows up repeatedly is a prompt problem, not a sampling accident.
    tally: dict[str, int] = {}
    for c in good:
        for h in c["hallucinations"]:
            tally[h] = tally.get(h, 0) + 1
    top_flags = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[:15]

    rec = [c for c in good if c["tone"] == "recommend" and c.get("rec_compliant") is not None]

    return {
        "overall": block(good),
        "errors": len(cards) - len(good),
        "by_tone": by_tone,
        "by_platform": by_platform,
        "top_flags": top_flags,
        "rec_five_rate": _mean([1.0 if c["rec_compliant"] else 0.0 for c in rec]) if rec else None,
    }


def print_report(payload: dict) -> None:
    meta = payload.get("meta", {})
    cards = payload.get("cards", [])
    agg = aggregate(cards)
    o = agg["overall"]

    print("=" * 74)
    dry_tag = "  [DRY RUN — stub text, not the model]" if meta.get("dry") else ""
    err_tag = f"   {agg['errors']} errors" if agg["errors"] else ""
    print(f"  Critique eval — {meta.get('model', '?')}{dry_tag}")
    print(f"  {meta.get('timestamp', '?')}   {o.get('n', 0)} generations{err_tag}")
    print("=" * 74)

    if not o.get("n"):
        print("  no successful generations")
        return

    print(f"\n  reference precision   {o['reference_precision']:.3f}"
          "     <- headline: share of item references that were real")
    print(f"  coverage@10           {o['coverage_at_10']:.3f}"
          "     <- share of the user's top items actually named")
    print(f"  clean outputs         {o['clean_rate']:.3f}"
          "     <- share with zero invented items")
    print(f"  length compliance     {o['length_ok_rate']:.3f}"
          f"     <- mean {o['mean_words']:.0f} words")
    if agg["rec_five_rate"] is not None:
        print(f"  recommend = 5 items   {agg['rec_five_rate']:.3f}")
    print(f"  mean latency          {o['mean_latency_s']:.2f}s")

    hdr = f"\n  {'tone':<16}{'n':>3}  {'prec':>6}{'cov@10':>8}{'clean':>7}{'len':>7}{'words':>7}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 3))
    for tone, b in agg["by_tone"].items():
        print(f"  {tone:<16}{b['n']:>3}  {b['reference_precision']:>6.2f}"
              f"{b['coverage_at_10']:>8.2f}{b['clean_rate']:>7.2f}"
              f"{b['length_ok_rate']:>7.2f}{b['mean_words']:>7.0f}")

    print(f"\n  {'platform':<16}{'n':>3}  {'prec':>6}{'cov@10':>8}{'clean':>7}")
    print("  " + "-" * 40)
    for plat, b in agg["by_platform"].items():
        print(f"  {plat:<16}{b['n']:>3}  {b['reference_precision']:>6.2f}"
              f"{b['coverage_at_10']:>8.2f}{b['clean_rate']:>7.2f}")

    if agg["top_flags"]:
        print("\n  most-flagged spans (candidate inventions, recurring first)")
        print("  " + "-" * 52)
        for span, n in agg["top_flags"]:
            print(f"  {n:>3}x  {span}")
        print("\n  Reminder: these are heuristic candidates, not verified"
              " inventions.\n  Skim them — creator names are a known false-positive class.")

    if agg["errors"]:
        print("\n  errors")
        for c in cards:
            if c.get("error"):
                print(f"   - {c['profile']}/{c['tone']}: {c['error']}")


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_run(args: argparse.Namespace) -> int:
    profiles = args.profiles or list(fixtures.PROFILES)
    tones = args.tones or list(TONE_ORDER)

    unknown = [p for p in profiles if p not in fixtures.PROFILES] + \
              [t for t in tones if t not in TONE_ORDER]
    if unknown:
        print(f"unknown profile/tone: {', '.join(unknown)}", file=sys.stderr)
        print(f"profiles: {', '.join(fixtures.PROFILES)}", file=sys.stderr)
        print(f"tones:    {', '.join(TONE_ORDER)}", file=sys.stderr)
        return 2

    if not args.dry:
        try:
            from critique.llm import is_configured
        except ImportError as exc:
            print(f"cannot import the LLM client ({exc}).\n"
                  "Install deps:  pip install -r requirements.txt\n"
                  "Or test the harness with no deps and no keys:  "
                  "python -m evals.run run --dry", file=sys.stderr)
            return 3

        if not is_configured():
            print("LLM is not configured — set LLM_API_KEY (and LLM_BASE_URL, "
                  "LLM_MODEL) in .env.\nTo test the harness itself without keys: "
                  "python -m evals.run run --dry", file=sys.stderr)
            return 3

        from critique.config import settings

        model = settings.LLM_MODEL
    else:
        model = "stub"

    total = len(profiles) * len(tones)
    print(f"{total} generations: {len(profiles)} profiles x {len(tones)} tones "
          f"-> {model}{' (dry)' if args.dry else ''}\n")

    cards: list[dict] = []
    i = 0
    for pname in profiles:
        profile = fixtures.load(pname)
        for tone in tones:
            i += 1
            print(f"  [{i}/{total}] {pname} / {tone} ... ", end="", flush=True)
            try:
                text, latency = _generate(profile, tone, args.dry)
                card = score(text, profile, tone, model=model)
                card.profile = pname
                card.latency_s = latency
                cards.append(card.as_dict())
                print(card.headline())
            except KeyboardInterrupt:
                print("interrupted")
                raise
            except Exception as exc:  # one failure must not lose the rest
                blank = ScoreCard(profile=pname, platform=profile.platform,
                                  tone=tone, model=model)
                d = blank.as_dict()
                d["error"] = f"{type(exc).__name__}: {exc}"
                cards.append(d)
                print(f"ERROR {type(exc).__name__}: {exc}")

    payload = {
        "meta": {
            "model": model,
            "dry": bool(args.dry),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "profiles": profiles,
            "tones": tones,
        },
        "cards": cards,
    }

    out = Path(args.out) if args.out else (
        RESULTS_DIR / f"run-{datetime.now():%Y%m%d-%H%M%S}"
                      f"{'-dry' if args.dry else ''}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print_report(payload)
    print(f"\nsaved -> {out}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    if args.path:
        path = Path(args.path)
    else:
        runs = sorted(RESULTS_DIR.glob("run-*.json"))
        if not runs:
            print(f"no saved runs in {RESULTS_DIR}", file=sys.stderr)
            return 1
        path = runs[-1]
    if not path.exists():
        print(f"no such file: {path}", file=sys.stderr)
        return 1
    print_report(json.loads(path.read_text(encoding="utf-8")))
    print(f"\nsource -> {path}")
    return 0


def cmd_selftest(_: argparse.Namespace) -> int:
    return 0 if selftest() else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals.run",
                                 description="Critique evaluation harness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("selftest", help="validate the metric against labeled examples")

    r = sub.add_parser("run", help="generate and score across fixtures x tones")
    r.add_argument("--profiles", nargs="*", metavar="NAME",
                   help=f"default all: {', '.join(fixtures.PROFILES)}")
    r.add_argument("--tones", nargs="*", metavar="TONE",
                   help=f"default all: {', '.join(TONE_ORDER)}")
    r.add_argument("--out", metavar="PATH", help="where to write results JSON")
    r.add_argument("--dry", action="store_true",
                   help="use stub text instead of the model (no keys, no network)")

    p = sub.add_parser("report", help="aggregate a saved run")
    p.add_argument("path", nargs="?", help="results JSON (default: newest)")

    args = ap.parse_args(argv)
    return {"selftest": cmd_selftest, "run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
