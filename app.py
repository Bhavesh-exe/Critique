"""Critique — Streamlit app.

Run locally:   .venv/Scripts/python -m streamlit run app.py
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from critique.analysis import summarize
from critique.fetchers import FetchError, available_platforms, get_fetcher
from critique.llm import LLMAuthError, LLMConfigError, generate_critique, is_configured
from critique.prompts import TONE_ORDER, TONES, build

st.set_page_config(page_title="Critique — judge your taste", layout="centered")

# --- a little styling so it doesn't read as default Streamlit ---------------
st.markdown(
    """
    <style>
      .block-container { max-width: 780px; }
      .critique-card {
        background: #191b24; border: 1px solid #2a2d3a; border-radius: 16px;
        padding: 1.4rem 1.6rem; line-height: 1.6; font-size: 1.02rem;
      }
      .verdict-title { font-weight: 700; letter-spacing: .3px; margin-bottom: .3rem; }
      .stat-pill {
        display:inline-block; background:#22252f; border:1px solid #333747;
        border-radius:999px; padding:.25rem .7rem; margin:.15rem .25rem; font-size:.85rem;
      }
      .muted { color:#9aa0ad; font-size:.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Critique")
st.markdown(
    "<p class='muted'>Enter a profile, pick a tone, and let an AI judge your media taste "
    "— then tell you how to level it up.</p>",
    unsafe_allow_html=True,
)

# --- config warning ---------------------------------------------------------
if not is_configured():
    st.warning(
        "The AI isn't configured yet. Add **LLM_BASE_URL** and **LLM_API_KEY** to a `.env` "
        "file (copy `.env.example`) or to Streamlit secrets, then reload."
    )

# --- inputs -----------------------------------------------------------------
platforms = available_platforms()

# Spotify OAuth code callback check
if "code" in st.query_params:
    auth_code = st.query_params["code"]
    try:
        from critique.fetchers.spotify import exchange_code_for_token
        token_info = exchange_code_for_token(auth_code)
        st.session_state["spotify_token"] = token_info
        st.query_params.clear()
        st.success("Spotify connected successfully!")
    except Exception as e:
        st.error(f"Spotify authentication failed: {e}")

col1, col2 = st.columns([1, 1])
with col1:
    platform = st.selectbox("Platform", platforms)

username = ""
spotify_connected = bool(st.session_state.get("spotify_token"))

with col2:
    if platform == "Spotify":
        if spotify_connected:
            st.write("**Spotify Account Connected**")
            if st.button("Disconnect Spotify", type="secondary"):
                del st.session_state["spotify_token"]
                st.rerun()
        else:
            try:
                from critique.fetchers.spotify import get_authorize_url
                auth_url = get_authorize_url()
                st.link_button("Connect Spotify", auth_url, type="primary", use_container_width=True)
            except Exception as e:
                st.caption(f"{e}")
    else:
        placeholders = {
            "GitHub": "e.g. torvalds or your GitHub username",
            "Chess.com": "e.g. hikaru or your Chess.com username",
            "Letterboxd": "e.g. your Letterboxd handle",
            "Spotify": "your Spotify username",
            "MyAnimeList": "e.g. your MAL username",
            "Last.fm": "e.g. your Last.fm username",
        }
        username = st.text_input(
            "Username",
            placeholder=placeholders.get(platform, "Enter username"),
        )


tone = st.radio(
    "Tone",
    TONE_ORDER,
    format_func=lambda k: f"{TONES[k]['label']}",
    horizontal=True,
)

go = st.button("Analyze my taste", type="primary", use_container_width=True)


def _share_button(text: str) -> None:
    """Render a copy-to-clipboard button (works inside Streamlit's iframe)."""
    safe = text.replace("\\", "\\\\").replace("`", "\\`")
    components.html(
        f"""
        <button id="cp" style="width:100%;padding:.6rem;border-radius:10px;border:1px solid #333747;
          background:#22252f;color:#f4f4f6;cursor:pointer;font-size:.95rem;">
          Copy critique to share
        </button>
        <script>
          const t = `{safe}`;
          document.getElementById('cp').onclick = async () => {{
            try {{ await navigator.clipboard.writeText(t); }}
            catch (e) {{
              const ta=document.createElement('textarea'); ta.value=t; document.body.appendChild(ta);
              ta.select(); document.execCommand('copy'); ta.remove();
            }}
            const b=document.getElementById('cp'); b.innerText='Copied!';
            setTimeout(()=>b.innerText='Copy critique to share', 1500);
          }};
        </script>
        """,
        height=60,
    )


# --- run --------------------------------------------------------------------
if go:
    if platform == "Spotify" and not spotify_connected:
        st.error("Please click 'Connect Spotify' above before analyzing.")
        st.stop()
    elif platform != "Spotify" and not username.strip():
        st.error(f"Please enter your {platform} username first.")
        st.stop()

    if not is_configured():
        st.error("Set up the AI (LLM_BASE_URL / LLM_API_KEY) before analyzing.")
        st.stop()

    try:
        with st.spinner(f"Reading your {platform} taste…"):
            fetcher = get_fetcher(platform)
            if platform == "Spotify":
                profile = fetcher.fetch("", token=st.session_state.get("spotify_token"))
            else:
                profile = fetcher.fetch(username)
            summarize(profile)
        with st.spinner("Forming a verdict…"):
            critique = generate_critique(build(tone), profile.text_summary)
    except FetchError as e:
        st.error(f"Couldn't fetch that profile: {e}")
        st.stop()
    except LLMConfigError as e:
        st.error(str(e))
        st.stop()
    except LLMAuthError as e:
        st.error(f"**LLM Authentication Failed**: {e}\n\n"
                 "Your API key was rejected by the provider (e.g. AgentRouter). "
                 "Please update `LLM_API_KEY` in your `.env` file (or switch to another provider like Groq, Google Gemini, OpenRouter, or OpenAI).")
        st.stop()
    except Exception as e:  # noqa: BLE001 — surface anything else cleanly
        st.error(f"Something went wrong: {e}")
        st.stop()

    # verdict card
    st.markdown(
        f"<div class='critique-card'><div class='verdict-title'>"
        f"Your {TONES[tone]['label']} verdict</div>{critique}</div>",
        unsafe_allow_html=True,
    )
    st.write("")

    # stats panel
    stats = profile.stats
    pills = []
    if "obscurity" in stats:
        pills.append(f"Obscurity {stats['obscurity']}/100")
    if "diversity" in stats:
        pills.append(f"Diversity {stats['diversity']}")
    for k, v in stats.items():
        if k in {"top_genres", "obscurity", "diversity"} or v is None:
            continue
        pills.append(f"{k}: {v}")
    if pills:
        st.markdown(
            "".join(f"<span class='stat-pill'>{p}</span>" for p in pills),
            unsafe_allow_html=True,
        )
    tg = stats.get("top_genres")
    if tg:
        st.markdown(
            "<span class='muted'>Top genres: </span>"
            + ", ".join(f"{g}" for g, _ in tg),
            unsafe_allow_html=True,
        )

    st.write("")
    share_text = f"My {TONES[tone]['label']} taste verdict from Critique:\n\n{critique}"
    _share_button(share_text)

    with st.expander("See the raw data the AI judged"):
        st.code(profile.text_summary, language="text")
