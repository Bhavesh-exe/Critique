"""Tone / persona selector component.

Uses the .voices grid from assets/critique.css.
Each persona card (.voice) carries its own --own CSS variable for its
unique accent color, independent of the global --accent.
"""

import reflex as rx

from critique_ui.state import State
from critique_ui.styles import TONE_ACCENTS, TONE_BLURBS


_PERSONAS: list[tuple[str, str, str]] = [
    ("roast",         "Roast",         "No mercy, all wit"),
    ("formal",        "Formal",        "Measured and essayistic"),
    ("supportive",    "Supportive",    "Warm and generous"),
    ("philosophical", "Philosophical", "Meaning and identity"),
    ("recommend",     "Recommend",     "Blind spots and cures"),
]


def _voice_card(key: str, label: str, blurb: str) -> rx.Component:
    own_color = TONE_ACCENTS[key]
    return rx.el.button(
        rx.el.span(label, class_name="voice__name"),
        rx.el.span(blurb, class_name="voice__blurb"),
        class_name=rx.cond(
            State.selected_tone == key,
            "voice voice--on",
            "voice",
        ),
        style={"--own": own_color},
        on_click=State.set_tone(key),
        type="button",
    )


def tone_selector_component() -> rx.Component:
    return rx.el.div(
        # Step header
        rx.el.div(
            rx.el.span("02", class_name="step__num"),
            rx.el.span("Persona", style={"letter_spacing": "0.22em", "font_size": "0.66rem", "text_transform": "uppercase", "font_family": "var(--mono)"}),
            rx.el.div(class_name="step__line"),
            class_name="step",
        ),
        # Voices grid
        rx.el.div(
            *[_voice_card(k, l, b) for k, l, b in _PERSONAS],
            class_name="voices",
        ),
    )
