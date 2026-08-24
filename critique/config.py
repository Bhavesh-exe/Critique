"""Configuration & secrets.

Reads settings from Streamlit secrets (used on Streamlit Community Cloud) first,
then falls back to a local `.env` file for development. Import `settings`
anywhere; it's evaluated lazily per attribute so tests and scripts work too.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Load a local .env if present (no-op on Streamlit Cloud where secrets are used).
load_dotenv()


def _get(key: str, default: str | None = None) -> str | None:
    """Return a setting: Streamlit secrets win, then environment, then default."""
    # st.secrets raises if there is no secrets file, so guard the whole thing.
    try:
        import streamlit as st

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


class Settings:
    """Typed-ish accessors for every configuration value."""

    # --- LLM (AgentRouter, OpenAI-compatible) ---
    @property
    def LLM_BASE_URL(self) -> str:
        return _get("LLM_BASE_URL", "https://agentrouter.org/v1")

    @property
    def LLM_API_KEY(self) -> str | None:
        return _get("LLM_API_KEY")

    @property
    def LLM_MODEL(self) -> str:
        return _get("LLM_MODEL", "claude-opus-5")

    # --- Last.fm ---
    @property
    def LASTFM_API_KEY(self) -> str | None:
        return _get("LASTFM_API_KEY")

    # --- Spotify ---
    @property
    def SPOTIFY_CLIENT_ID(self) -> str | None:
        return _get("SPOTIFY_CLIENT_ID")

    @property
    def SPOTIFY_CLIENT_SECRET(self) -> str | None:
        return _get("SPOTIFY_CLIENT_SECRET")

    @property
    def SPOTIFY_REDIRECT_URI(self) -> str:
        return _get("SPOTIFY_REDIRECT_URI", "http://localhost:8501")

    # --- MyAnimeList (optional) ---
    @property
    def MAL_CLIENT_ID(self) -> str | None:
        return _get("MAL_CLIENT_ID") or None

    # --- GitHub (optional) ---
    @property
    def GITHUB_TOKEN(self) -> str | None:
        return _get("GITHUB_TOKEN") or None


settings = Settings()

