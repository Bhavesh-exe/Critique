"""LLM access layer — talks to AgentRouter via the OpenAI-compatible API.

Because AgentRouter (like Groq/OpenRouter/Gemini's compat endpoint) speaks the
OpenAI `chat/completions` format, this whole file is provider-agnostic: swap
providers by changing LLM_BASE_URL / LLM_API_KEY / LLM_MODEL in your .env only.
"""

from __future__ import annotations

from typing import Iterator

from openai import OpenAI

from .config import settings


class LLMConfigError(RuntimeError):
    """Raised when the LLM isn't configured (missing key/base URL)."""


class LLMAuthError(RuntimeError):
    """Raised when the LLM provider rejects authentication (401/403)."""


def is_configured() -> bool:
    return bool(settings.LLM_API_KEY and settings.LLM_BASE_URL)


DEFAULT_CLIENT_HEADERS = {
    "User-Agent": "claude-cli/0.2.29 (external, cli)",
    "anthropic-version": "2023-06-01",
    "anthropic-beta": "claude-code-20250219",
    "x-stainless-lang": "js",
    "x-stainless-package-version": "0.2.29",
    "x-stainless-os": "Windows",
    "x-stainless-arch": "x64",
    "x-stainless-runtime": "node",
}


def _client() -> OpenAI:
    if not is_configured():
        raise LLMConfigError(
            "LLM is not configured. Set LLM_BASE_URL and LLM_API_KEY in your .env "
            "(or Streamlit secrets)."
        )
    return OpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        default_headers=DEFAULT_CLIENT_HEADERS,
    )


def generate_critique(system_prompt: str, user_block: str, *, temperature: float = 0.9) -> str:
    """Send the tone (system) + data summary (user) to the model, return the text."""
    print("\n" + "=" * 64, flush=True)
    print(f"[CRITIQUE PIPELINE] Calling LLM ({settings.LLM_MODEL})", flush=True)
    print("-" * 64, flush=True)
    print(">>> PLATFORM DATA PAYLOAD (Sent to AI as User Message):", flush=True)
    print(user_block.strip(), flush=True)
    print("-" * 64, flush=True)
    print(">>> SYSTEM PROMPT (Sent to AI):", flush=True)
    print(system_prompt.strip(), flush=True)
    print("=" * 64 + "\n", flush=True)

    try:
        resp = _client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_block},
            ],
            temperature=temperature,
            max_tokens=1500,
        )
        verdict = (resp.choices[0].message.content or "").strip()
        print("\n" + "=" * 64, flush=True)
        print("[CRITIQUE PIPELINE] LLM Response Received:", flush=True)
        print(verdict, flush=True)
        print("=" * 64 + "\n", flush=True)
        return verdict
    except Exception as e:
        if "401" in str(e) or "unauthorized" in str(e).lower() or "unauthenticated" in str(e).lower():
            raise LLMAuthError(
                f"Authentication failed with {settings.LLM_BASE_URL}: {e}. "
                "Please check or refresh your LLM_API_KEY in .env."
            ) from e
        raise


def stream_critique(
    system_prompt: str, user_block: str, *, temperature: float = 0.9
) -> Iterator[str]:
    """Same call, but yield text fragments as the model produces them.

    Used by the FastAPI `/api/critique/stream` endpoint so the verdict appears
    a few words at a time instead of after one long pause. Any provider that
    speaks the OpenAI streaming format works unchanged.
    """
    stream = _client().chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_block},
        ],
        temperature=temperature,
        max_tokens=1500,
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        piece = getattr(chunk.choices[0].delta, "content", None)
        if piece:
            yield piece
