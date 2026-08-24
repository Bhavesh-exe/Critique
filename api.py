"""FastAPI backend for Critique.

Wraps the *existing* pipeline without changing it. The flow is identical to the
one `app.py` runs:

    fetcher.fetch(username) -> summarize(profile) -> generate_critique(build(tone), summary)

Nothing platform-specific lives here — this file only turns that pipeline into
HTTP. Adding a platform still means writing one fetcher and registering it.

Run:
    .venv/Scripts/python.exe -m uvicorn api:app --reload
    -> http://localhost:8000        (serves web/index.html)
    -> http://localhost:8000/docs   (auto-generated API docs)

The Streamlit app still works; this is additive.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from critique.analysis import _SPECIAL_KEYS, _fmt, summarize
from critique.fetchers import (
    DISPLAY_TO_KEY,
    KEY_TO_DISPLAY,
    FetchError,
    available_platforms,
    get_fetcher,
)
from critique.llm import LLMConfigError, generate_critique, is_configured, stream_critique
from critique.models import TasteProfile
from critique.prompts import TONE_ORDER, TONES, build

app = FastAPI(
    title="Critique API",
    version="0.2.0",
    description="Judges a person's taste from their real platform activity.",
)

# Wide open so the frontend can be opened straight from disk during development.
# Before deploying, replace with your actual frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Platforms that authenticate instead of taking a username.
OAUTH_PLATFORMS = {"spotify"}

# The word stamped on the report, per tone. Same document, five different voices.
TONE_STAMPS = {
    "roast": "Roasted",
    "formal": "Examined",
    "supportive": "Commended",
    "philosophical": "Considered",
    "recommend": "Prescribed",
}


# --------------------------------------------------------------------------- #
# schemas
# --------------------------------------------------------------------------- #
class CritiqueRequest(BaseModel):
    platform: str = Field(..., description="Platform key ('lastfm') or display label ('Last.fm')")
    username: str = Field("", description="Ignored for OAuth platforms like Spotify")
    tone: str = Field("roast", description="One of: " + ", ".join(TONE_ORDER))
    spotify_token: dict[str, Any] | None = Field(
        None, description="Token dict from /api/spotify/callback; Spotify only"
    )


class ItemOut(BaseModel):
    title: str
    kind: str = ""
    genres: list[str] = []
    score: float | None = None
    count: int | None = None
    popularity: float | None = None
    url: str | None = None


class CritiqueResponse(BaseModel):
    platform: str
    platform_label: str
    username: str
    display_name: str
    tone: str
    tone_label: str
    tone_emoji: str
    stamp: str
    critique: str
    obscurity: float | None = None
    diversity: float | None = None
    top_genres: list[tuple[str, int]] = []
    measurements: list[tuple[str, str]] = []
    items: list[ItemOut] = []
    raw_summary: str = ""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _resolve_platform(name: str) -> str:
    """Accept either a display label or an internal key; return the key."""
    key = DISPLAY_TO_KEY.get(name, name).lower()
    if key not in DISPLAY_TO_KEY.values():
        raise HTTPException(400, f"Unknown platform '{name}'.")
    return key


def _resolve_tone(tone: str) -> str:
    if tone not in TONES:
        raise HTTPException(400, f"Unknown tone '{tone}'. Try one of: {', '.join(TONE_ORDER)}.")
    return tone


def _fetch_profile(key: str, username: str, spotify_token: dict | None) -> TasteProfile:
    """Run the fetch + analysis half of the pipeline, mapping errors to HTTP."""
    if key in OAUTH_PLATFORMS:
        if not spotify_token:
            raise HTTPException(401, "Connect Spotify before analysing.")
    elif not username.strip():
        raise HTTPException(400, f"Enter a {KEY_TO_DISPLAY.get(key, key)} username first.")

    try:
        fetcher = get_fetcher(key)
        if key in OAUTH_PLATFORMS:
            profile = fetcher.fetch("", token=spotify_token)
        else:
            profile = fetcher.fetch(username.strip())
        return summarize(profile)
    except FetchError as e:
        # 502: the upstream platform said no, not the client's fault
        raise HTTPException(502, str(e)) from e


def _measurements(profile: TasteProfile) -> list[tuple[str, str]]:
    """Scalar stats a fetcher added, minus the ones rendered specially."""
    out: list[tuple[str, str]] = []
    for k, v in profile.stats.items():
        if k in _SPECIAL_KEYS or v is None or v == "":
            continue
        out.append((k.replace("_", " "), _fmt(v)))
    return out


def _payload(profile: TasteProfile, key: str, tone: str, critique: str) -> dict:
    stats = profile.stats
    return CritiqueResponse(
        platform=key,
        platform_label=KEY_TO_DISPLAY.get(key, key),
        username=profile.username,
        display_name=profile.display_name or profile.username,
        tone=tone,
        tone_label=TONES[tone]["label"],
        tone_emoji=TONES[tone]["emoji"],
        stamp=TONE_STAMPS.get(tone, "Examined"),
        critique=critique,
        obscurity=stats.get("obscurity"),
        diversity=stats.get("diversity"),
        top_genres=[(g, c) for g, c in stats.get("top_genres", [])],
        measurements=_measurements(profile),
        items=[ItemOut(**vars(it)) for it in profile.top_items[:25]],
        raw_summary=profile.text_summary,
    ).model_dump()


# --------------------------------------------------------------------------- #
# routes
# --------------------------------------------------------------------------- #
@app.get("/api/meta")
def meta() -> dict:
    """Everything the UI needs to render its form. No hardcoded lists client-side."""
    return {
        "llm_ready": is_configured(),
        "platforms": [
            {
                "key": DISPLAY_TO_KEY[label],
                "label": label,
                "oauth": DISPLAY_TO_KEY[label] in OAUTH_PLATFORMS,
            }
            for label in available_platforms()
        ],
        "tones": [
            {
                "key": k,
                "label": TONES[k]["label"],
                "emoji": TONES[k]["emoji"],
                "stamp": TONE_STAMPS.get(k, "Examined"),
            }
            for k in TONE_ORDER
        ],
    }


@app.post("/api/critique", response_model=CritiqueResponse)
def critique(req: CritiqueRequest) -> dict:
    """Fetch, analyse, and judge in one request."""
    key = _resolve_platform(req.platform)
    tone = _resolve_tone(req.tone)

    if not is_configured():
        raise HTTPException(503, "The AI isn't configured. Set LLM_BASE_URL and LLM_API_KEY.")

    profile = _fetch_profile(key, req.username, req.spotify_token)

    try:
        text = generate_critique(build(tone), profile.text_summary)
    except LLMConfigError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:  # noqa: BLE001 — provider errors vary too much to enumerate
        raise HTTPException(502, f"The model did not respond: {e}") from e

    return _payload(profile, key, tone, text)


@app.post("/api/critique/stream")
def critique_stream(req: CritiqueRequest) -> StreamingResponse:
    """Same thing, streamed as server-sent events.

    Event order:
        {"type":"profile", ...full payload with critique:""}
        {"type":"delta","text":"..."}   (many)
        {"type":"done"}
        {"type":"error","detail":"..."} (instead of done, on failure)
    """
    key = _resolve_platform(req.platform)
    tone = _resolve_tone(req.tone)

    if not is_configured():
        raise HTTPException(503, "The AI isn't configured. Set LLM_BASE_URL and LLM_API_KEY.")

    # Fetch before opening the stream so failures are still real HTTP errors.
    profile = _fetch_profile(key, req.username, req.spotify_token)

    def events() -> Iterator[str]:
        head = _payload(profile, key, tone, "")
        head["type"] = "profile"
        yield f"data: {json.dumps(head)}\n\n"
        try:
            for piece in stream_critique(build(tone), profile.text_summary):
                yield f"data: {json.dumps({'type': 'delta', 'text': piece})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/spotify/authorize")
def spotify_authorize() -> dict:
    """URL to send the user to for Spotify consent."""
    try:
        from critique.fetchers.spotify import get_authorize_url

        return {"url": get_authorize_url()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Spotify isn't configured: {e}") from e


class SpotifyCallback(BaseModel):
    code: str


@app.post("/api/spotify/callback")
def spotify_callback(body: SpotifyCallback) -> dict:
    """Exchange the ?code= Spotify redirected back with for a token dict."""
    try:
        from critique.fetchers.spotify import exchange_code_for_token

        return {"token": exchange_code_for_token(body.code)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Spotify authentication failed: {e}") from e


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "llm_ready": is_configured()}


# --------------------------------------------------------------------------- #
# static frontend — mounted LAST so /api/* wins the route match
# --------------------------------------------------------------------------- #
_WEB = Path(__file__).parent / "web"
if _WEB.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB), html=True), name="web")
