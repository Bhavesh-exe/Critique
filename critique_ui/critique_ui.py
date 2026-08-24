"""Main page layout and app entry point for Critique.

Root element carries --accent CSS custom property driven by State.accent,
which causes the entire page to interpolate color when a persona is selected
(via the @property --accent registration in critique.css).

The .atmos layer (atmospheric glows + grain) is a fixed overlay behind all content.
"""

import reflex as rx

from critique_ui.components.header import header_component
from critique_ui.components.platform_input import platform_input_component
from critique_ui.components.tone_selector import tone_selector_component
from critique_ui.components.verdict_card import verdict_card_component
from critique_ui.state import State
from critique_ui.styles import BASE_STYLE


def _atmos() -> rx.Component:
    """Fixed atmospheric background layer - glows + film grain + grid ghost."""
    return rx.el.div(
        rx.el.div(class_name="atmos__glow atmos__glow--a"),
        rx.el.div(class_name="atmos__glow atmos__glow--b"),
        rx.el.div(class_name="atmos__grain"),
        rx.el.div(class_name="atmos__grid"),
        class_name="atmos",
    )


def _error_slip() -> rx.Component:
    """Editorial error notice - a rejection slip, not a toast."""
    return rx.cond(
        State.has_error,
        rx.el.div(
            rx.el.div(
                rx.icon("triangle_alert", size=16, class_name="slip__icon"),
                rx.el.div(
                    rx.el.div("Error", class_name="slip__label"),
                    rx.el.div(State.error_message, class_name="slip__msg"),
                ),
                style={"display": "flex", "align_items": "flex_start", "gap": "0.85rem"},
            ),
            class_name="slip",
        ),
    )


def _working_state() -> rx.Component:
    """Loading indicator - Claude Code terminal style ticker with random active verbs."""
    return rx.cond(
        State.is_loading,
        rx.el.div(
            rx.el.div(
                rx.el.span("✻", class_name="claude-spinner"),
                rx.el.span(State.loading_stage, style={"font_family": "var(--mono)", "letter_spacing": "0.08em"}),
                class_name="working__stage",
            ),
            rx.el.div(
                rx.el.div(class_name="rail__run"),
                class_name="rail",
            ),
            # Shimmering skeleton lines
            rx.el.div(
                rx.el.div(class_name="skel__line"),
                rx.el.div(class_name="skel__line"),
                rx.el.div(class_name="skel__line"),
                rx.el.div(class_name="skel__line"),
                class_name="skel",
            ),
            class_name="working",
        ),
    )


def _analyze_button() -> rx.Component:
    return rx.el.button(
        rx.cond(
            State.is_loading,
            rx.el.div(
                rx.el.span("✻", class_name="claude-spinner"),
                rx.el.span(State.loading_stage),
                class_name="file-btn__inner",
            ),
            rx.el.div(
                rx.icon("sparkles", size=16),
                rx.el.span("File — Analyze My Taste"),
                class_name="file-btn__inner",
            ),
        ),
        class_name="file-btn",
        on_click=State.analyze_taste,
        disabled=State.is_loading,
        type="button",
    )


def index() -> rx.Component:
    """The main Critique application interface."""
    return rx.box(
        rx.el.link(rel="stylesheet", href="/critique.css"),
        # Atmospheric layer (fixed, behind everything)
        _atmos(),

        # Content shell
        rx.el.main(
            header_component(),
            _error_slip(),

            # Input panel
            rx.el.div(
                platform_input_component(),
                rx.el.div(class_name="rule", style={"--d": "0ms", "margin": "1.4rem 0"}),
                tone_selector_component(),
                _analyze_button(),
                class_name="panel rise",
                style={"--d": "80ms"},
            ),

            # Working state (inline, below panel)
            _working_state(),

            # Results - verdict paragraph only
            verdict_card_component(),

            # Colophon
            rx.el.footer(
                rx.el.span("Critique"),
                rx.el.span(
                    rx.el.b("AI Cultural Taste Judge"),
                    " · via AgentRouter",
                ),
                class_name="colophon",
            ),

            class_name="shell",
        ),

        # Dynamically apply light-mode or dark-mode class and drive --accent
        class_name=State.theme_class,
        style={**BASE_STYLE, "--accent": State.accent},
    )


app = rx.App(
    stylesheets=["/critique.css"],
)
app.add_page(index, title="Critique — AI Cultural Taste Judge", route="/")
