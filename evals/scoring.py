"""Metrics for a generated critique. Pure stdlib, no network, no API keys.

The prompt in `critique/prompts.py` makes three checkable promises:

    "Reference SPECIFIC titles/artists/films/repos/openings from the data. Name them."
    "NEVER invent items that aren't in the data."
    "Keep it to 150-250 words."

This module turns each of those into a number.

The headline metric is **reference precision**: of all the item references the
model made, what fraction were real items from the profile? A model that names
four real albums scores 1.0. A model that names two real albums and invents two
scores 0.5.

An honest caveat, stated up front because it's the interesting part: finding
*hallucinated* references is strictly harder than finding real ones. Real ones
can be checked by exact lookup against a known list. Hallucinated ones require
first deciding which spans of English prose were meant to be item references at
all, and that is a heuristic — Title Case extraction plus a stoplist. So the
scorer sorts its findings into `hallucinations` (confident) and `weak`
(sentence-opening single words, which are usually prose, occasionally real
inventions). Only the confident bucket feeds the headline number, and
`selftest()` exists to keep the heuristic honest against hand-labeled examples.

The natural upgrade is embedding-based matching, which would catch aliases the
string matcher misses ("Attack on Titan" vs "Shingeki no Kyojin").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher

from critique.models import TasteProfile

# Fuzzy match threshold for title matching. Tuned on the labeled set in
# selftest(); raising it misses real mentions, lowering it invents them.
FUZZY_THRESHOLD = 0.88

# Word count contract from BASE_RULES.
WORD_MIN, WORD_MAX = 150, 250

# Capitalized words that occur constantly in English prose and are never item
# references. Anything here is discarded before hallucination counting.
STOPLIST = {
    # pronouns / determiners / conjunctions
    "a", "an", "and", "as", "at", "be", "but", "by", "each", "even", "every",
    "for", "he", "her", "here", "his", "how", "i", "if", "in", "is", "it",
    "its", "me", "my", "no", "not", "now", "of", "on", "once", "or", "our",
    "she", "so", "some", "still", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "to", "too", "we",
    "what", "when", "where", "which", "while", "who", "why", "with", "yes",
    "yet", "you", "your", "yours",
    # discourse openers
    "actually", "also", "although", "anyway", "because", "besides", "clearly",
    "congratulations", "either", "elsewhere", "finally", "first", "frankly",
    "however", "honestly", "instead", "later", "least", "less", "listen",
    "look", "maybe", "meanwhile", "more", "most", "nevertheless", "next",
    "obviously", "okay", "perhaps", "really", "second", "sure", "therefore",
    "third", "truly", "unfortunately", "verdict", "well", "worse", "worst",
    # domain vocabulary the model uses generically
    "album", "albums", "anime", "artist", "artists", "author", "authors",
    "band", "bands", "book", "books", "count", "diversity", "director",
    "directors", "film", "films", "game", "games", "genre", "genres",
    "growth", "item", "items", "language", "languages", "manga", "movie",
    "movies", "obscurity", "opening", "openings", "platform", "play", "plays",
    "playcount", "rating", "ratings", "recommendation", "recommendations",
    "repo", "repos", "repositories", "repository", "score", "scores",
    "scrobble", "scrobbles", "song", "songs", "star", "stars", "taste",
    "top", "track", "tracks", "user", "username",
    # numerals often title-cased at line starts in lists
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten",
}

# Quoted spans: "like this", 'like this', or curly-quoted.
_QUOTED = re.compile(r"[\"“‘']([^\"“”‘’']{2,60})[\"”’']")

# A Title Case run, allowing lowercase joiners inside (e.g. "In the Mood for Love").
# "and"/"to" are deliberately NOT joiners: allowing them merged two separate
# proper nouns into one span ("Pink Floyd and Joy Division"), undercounting
# inventions. Caught by selftest().
_TITLECASE = re.compile(
    r"\b[A-Z][\w&'’\-]*(?:\s+(?:of|the|in|for|a|an|no|de|la|le|von|van)\s+[A-Z0-9][\w&'’\-]*"
    r"|\s+[A-Z0-9][\w&'’\-]*)*"
)

# A bulleted or numbered list line, for the `recommend` tone's "exactly 5" rule.
_LIST_LINE = re.compile(r"^\s*(?:\d+[.):]|[-*•–])\s+\S", re.MULTILINE)

# The whole list line, for stripping recommendations out before scanning for
# invented items — see the tone-awareness note in score().
_LIST_FULL = re.compile(r"^\s*(?:\d+[.):]|[-*•–])\s+.*$", re.MULTILINE)

_SENT_START = re.compile(r"(?:^|[.!?]\s+|\n)\s*$")


def normalize(s: str) -> str:
    """Casefold, strip accents and punctuation, collapse whitespace."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"[^\w\s]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _windows(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def find_named_items(text: str, titles: list[str]) -> dict[str, str]:
    """Which of `titles` the text actually names. Returns title -> "exact"|"fuzzy"."""
    ntext = normalize(text)
    tokens = ntext.split()
    found: dict[str, str] = {}

    for title in titles:
        nt = normalize(title)
        if not nt:
            continue
        if nt in ntext:
            found[title] = "exact"
            continue

        # Fuzzy pass, for typos and small truncations. Compare the title against
        # same-length token windows only, so cost stays linear in text length.
        wc = len(nt.split())
        if wc > 6:
            continue
        best = 0.0
        for width in {max(1, wc - 1), wc, wc + 1}:
            for w in _windows(tokens, width):
                r = SequenceMatcher(None, nt, w).ratio()
                if r > best:
                    best = r
                    if best >= 0.99:
                        break
        if best >= FUZZY_THRESHOLD:
            found[title] = "fuzzy"

    return found


def _allowed_terms(profile: TasteProfile) -> set[str]:
    """Strings that are legitimately in the text but are not item references."""
    allowed = {normalize(profile.platform), normalize(profile.username),
               normalize(profile.display_name)}
    for g, _ in profile.stats.get("top_genres", []):
        allowed.add(normalize(g))
    for it in profile.top_items:
        for g in it.genres:
            allowed.add(normalize(g))
        allowed.add(normalize(it.kind))
    # platform display names the model may spell out
    allowed |= {"myanimelist", "mal", "last fm", "lastfm", "spotify",
                "letterboxd", "github", "chess com", "chessdotcom", "jikan"}
    allowed.discard("")
    return allowed


def extract_candidates(text: str) -> list[tuple[str, bool]]:
    """Spans that look like item references.

    Returns (span, at_sentence_start). Quoted spans are never treated as
    sentence-start, since quoting is itself strong evidence of a reference.
    """
    out: list[tuple[str, bool]] = []
    for m in _QUOTED.finditer(text):
        out.append((m.group(1).strip(), False))
    for m in _TITLECASE.finditer(text):
        span = m.group(0).strip()
        before = text[max(0, m.start() - 40) : m.start()]
        out.append((span, bool(_SENT_START.search(before)) or m.start() == 0))
    return out


@dataclass
class ScoreCard:
    """One scored critique."""

    profile: str = ""
    platform: str = ""
    tone: str = ""
    model: str = ""

    items_available: int = 0
    named: list[str] = field(default_factory=list)
    named_count: int = 0
    coverage_at_10: float = 0.0

    hallucinations: list[str] = field(default_factory=list)
    weak: list[str] = field(default_factory=list)
    hallucination_count: int = 0

    reference_precision: float = 0.0

    word_count: int = 0
    words_in_range: bool = False

    listed_lines: int = 0
    rec_compliant: bool | None = None
    recommendations: int = 0

    latency_s: float | None = None
    critique: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    def headline(self) -> str:
        return (
            f"precision {self.reference_precision:.2f}  "
            f"named {self.named_count}/{min(10, self.items_available)}  "
            f"halluc {self.hallucination_count}  "
            f"words {self.word_count}{'' if self.words_in_range else ' ✗'}"
        )


def score(critique: str, profile: TasteProfile, tone: str = "", *, model: str = "") -> ScoreCard:
    """Score one generated critique against the profile it was generated from."""
    titles = [it.title for it in profile.top_items]
    card = ScoreCard(
        platform=profile.platform,
        tone=tone,
        model=model,
        items_available=len(titles),
        critique=critique,
    )

    # --- grounding: real items actually named -------------------------------
    found = find_named_items(critique, titles)
    card.named = sorted(found)
    card.named_count = len(found)
    denom = min(10, len(titles)) or 1
    card.coverage_at_10 = round(min(card.named_count, denom) / denom, 3)

    # --- invented-item candidates -------------------------------------------
    # Tone-awareness, and the most important correctness point in this file:
    # the `recommend` tone is *instructed* to name five items that are NOT in
    # the user's data. Its list lines are therefore correct behaviour, not
    # invention — scanning them would penalise the model for obeying the
    # prompt. For that tone the suggestions are counted separately and only the
    # diagnosis prose is held to the "never invent" rule.
    scan_text = critique
    if tone == "recommend":
        card.recommendations = len(_LIST_LINE.findall(critique))
        scan_text = _LIST_FULL.sub("", critique)

    allowed = _allowed_terms(profile)
    named_norm = {normalize(t) for t in titles}

    raw = extract_candidates(scan_text)
    # Longest span first, so "Wong Kar-wai" is kept and the bare "Wong" nested
    # inside it is dropped rather than counted as a second, separate invention.
    order = sorted(range(len(raw)), key=lambda i: -len(raw[i][0]))
    kept: dict[int, tuple[str, bool]] = {}
    kept_norm: list[str] = []

    for i in order:
        span, at_start = raw[i]
        n = normalize(span)
        if not n or len(n) < 3:
            continue
        words = n.split()
        # entirely stoplist -> prose
        if all(w in STOPLIST for w in words):
            continue
        if n in allowed:
            continue
        # a real item, possibly partially quoted
        if n in named_norm or any(n in t or t in n for t in named_norm):
            continue
        if any(SequenceMatcher(None, n, t).ratio() >= FUZZY_THRESHOLD for t in named_norm):
            continue
        # a repeat, or already covered by a longer accepted span
        if any(n == k or n in k for k in kept_norm):
            continue
        kept_norm.append(n)
        kept[i] = (span, at_start)

    # Emit in reading order, not length order, so the report is legible.
    for i in sorted(kept):
        span, at_start = kept[i]
        # single word opening a sentence is usually prose, not an invention
        if at_start and len(span.split()) == 1:
            card.weak.append(span)
        else:
            card.hallucinations.append(span)

    card.hallucination_count = len(card.hallucinations)

    total_refs = card.named_count + card.hallucination_count
    card.reference_precision = round(card.named_count / total_refs, 3) if total_refs else 0.0

    # --- format compliance ---------------------------------------------------
    card.word_count = len(critique.split())
    card.words_in_range = WORD_MIN <= card.word_count <= WORD_MAX

    card.listed_lines = len(_LIST_LINE.findall(critique))
    if tone == "recommend":
        card.rec_compliant = card.listed_lines == 5

    return card

# --------------------------------------------------------------------------- #
# metric validation
# --------------------------------------------------------------------------- #
# Hand-labeled critiques with expected outcomes. This is the part that keeps the
# heuristic trustworthy: before believing any number the scorer reports about a
# real model, it has to reproduce known answers on these.
LABELED: list[dict] = [
    {
        "name": "clean_grounded",
        "fixture": "lastfm_mainstream",
        "tone": "formal",
        "text": (
            "There is a coherence here that resists easy mockery. Radiohead and Beach House "
            "share an interest in texture over melody, and Tame Impala sits between them as the "
            "obvious bridge. The presence of Alvvays is the one genuine surprise, a jangle-pop "
            "outlier among otherwise weightier choices. Frank Ocean complicates the picture "
            "usefully. What emerges is a listener who trusts atmosphere."
        ),
        "expect": {"min_named": 5, "hallucinations": 0},
    },
    {
        "name": "hallucinating",
        "fixture": "lastfm_mainstream",
        "tone": "roast",
        "text": (
            "Radiohead at the top, obviously. But then you reach for Pink Floyd and Joy Division "
            "as though nobody would notice the pivot, and frankly The Velvet Underground is doing "
            "nothing for you here. Tame Impala at least you earned."
        ),
        "expect": {"min_named": 2, "hallucinations": 3},
    },
    {
        "name": "generic_ungrounded",
        "fixture": "lastfm_mainstream",
        "tone": "supportive",
        "text": (
            "Your taste shows real depth and a willingness to explore. You clearly value "
            "atmosphere and songwriting, and there is an emotional intelligence to the way you "
            "listen. Keep following your instincts, because they are serving you well."
        ),
        "expect": {"min_named": 0, "max_named": 0, "hallucinations": 0},
    },
    {
        "name": "recommend_five",
        "fixture": "letterboxd",
        "tone": "recommend",
        "text": (
            "You have the arthouse canon down; what you lack is anything playful. "
            "In the Mood for Love and Chungking Express suggest you would follow Wong Kar-wai "
            "anywhere, so start there.\n"
            "1. Days of Being Wild — the missing early Wong.\n"
            "2. Yi Yi — domestic scale, same patience as Stalker.\n"
            "3. Close-Up — for the documentary instinct you have not used.\n"
            "4. The Long Day Closes — memory film, quieter than Paris, Texas.\n"
            "5. Tampopo — because nothing here is fun.\n"
            "Growth direction: comedy with formal ambition."
        ),
        # The five suggestions are new titles *by design*, so none of them count
        # as inventions. The one flag is "Wong Kar-wai" — a real director of two
        # films in the profile. Creator names are a known false-positive class
        # for a string matcher with no world knowledge; documented, not hidden.
        # This is precisely what an embedding/knowledge-base upgrade would fix.
        "expect": {"min_named": 3, "hallucinations": 1, "listed_lines": 5,
                   "rec_compliant": True, "recommendations": 5},
        "note": "'Wong Kar-wai' is a known false positive: creator name, not an item.",
    },
    {
        # Guards against the obvious way to cheat the fix above: exempting the
        # whole `recommend` tone from the invention check. The diagnosis prose
        # must still be grounded, so an invented item there has to be caught.
        "name": "recommend_bad_diagnosis",
        "fixture": "letterboxd",
        "tone": "recommend",
        "text": (
            "Your love of Mulholland Drive and Persona tells me you want dream logic, "
            "and Stalker confirms the patience for it.\n"
            "1. Days of Being Wild — more of the same register.\n"
            "2. Yi Yi — domestic scale.\n"
            "3. Close-Up — documentary instinct.\n"
            "4. The Long Day Closes — memory film.\n"
            "5. Tampopo — because nothing here is fun.\n"
        ),
        "expect": {"min_named": 1, "hallucinations": 2, "listed_lines": 5,
                   "rec_compliant": True},
    },
]


def selftest(verbose: bool = True) -> bool:
    """Run the scorer against LABELED and report whether it reproduces them."""
    from evals import fixtures

    ok = True
    for case in LABELED:
        profile = fixtures.load(case["fixture"])
        card = score(case["text"], profile, case["tone"])
        exp = case["expect"]
        problems: list[str] = []

        if "min_named" in exp and card.named_count < exp["min_named"]:
            problems.append(f"named {card.named_count} < expected >= {exp['min_named']}")
        if "max_named" in exp and card.named_count > exp["max_named"]:
            problems.append(f"named {card.named_count} > expected <= {exp['max_named']}")
        if "hallucinations" in exp and card.hallucination_count != exp["hallucinations"]:
            problems.append(
                f"hallucinations {card.hallucination_count} != expected "
                f"{exp['hallucinations']} -> {card.hallucinations}"
            )
        if "listed_lines" in exp and card.listed_lines != exp["listed_lines"]:
            problems.append(f"listed {card.listed_lines} != expected {exp['listed_lines']}")
        if "rec_compliant" in exp and card.rec_compliant != exp["rec_compliant"]:
            problems.append(f"rec_compliant {card.rec_compliant} != {exp['rec_compliant']}")
        if "recommendations" in exp and card.recommendations != exp["recommendations"]:
            problems.append(f"recommendations {card.recommendations} != {exp['recommendations']}")

        if problems:
            ok = False
        if verbose:
            mark = "PASS" if not problems else "FAIL"
            print(f"[{mark}] {case['name']:<24} {card.headline()}")
            if card.named:
                print(f"         named:   {', '.join(card.named)}")
            if card.hallucinations:
                print(f"         flagged: {', '.join(card.hallucinations)}")
            if card.weak:
                print(f"         weak:    {', '.join(card.weak)}")
            if case.get("note"):
                print(f"         note:    {case['note']}")
            for p in problems:
                print(f"         -> {p}")

    if verbose:
        print(
            "\nNote: every case shows 'words ✗'. That is expected — these labeled\n"
            "texts are 40-90 words, deliberately short. Length compliance is tested\n"
            f"against real generations, where the {WORD_MIN}-{WORD_MAX} contract applies."
        )
        print("\nmetric validation:", "OK" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    import sys

    sys.exit(0 if selftest() else 1)
