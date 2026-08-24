"""Platform and username input component.

Uses .tiles grid for platform selection and .field for username input.
CSS classes from assets/critique.css.
"""

import reflex as rx

from critique_ui.state import State
from critique_ui.styles import PLATFORM_TILES


def _tile(name: str, icon: str, tag: str) -> rx.Component:
    """Single platform tile with active state."""
    return rx.el.button(
        rx.icon(icon, size=18, class_name="tile__icon"),
        rx.el.span(name),
        rx.el.span(tag, class_name="tile__tag"),
        class_name=rx.cond(
            State.selected_platform == name,
            "tile tile--on",
            "tile",
        ),
        on_click=State.set_platform(name),
        type="button",
    )


def platform_input_component() -> rx.Component:
    return rx.el.div(
        # Step header
        rx.el.div(
            rx.el.span("01", class_name="step__num"),
            rx.el.span("Platform", style={"letter_spacing": "0.22em", "font_size": "0.66rem", "text_transform": "uppercase", "font_family": "var(--mono)"}),
            rx.el.div(class_name="step__line"),
            class_name="step",
        ),
        # Platform tiles grid
        rx.el.div(
            *[_tile(name, icon, tag) for name, icon, tag in PLATFORM_TILES],
            class_name="tiles",
        ),
        # Username field
        rx.el.div(
            rx.el.span("@", class_name="field__sigil"),
            rx.input(
                placeholder=State.username_placeholder,
                value=State.username,
                on_change=State.set_username,
                class_name="field__input",
                type="text",
                style={
                    "background": "transparent",
                    "border": "none",
                    "outline": "none",
                    "box_shadow": "none",
                    "color": "inherit",
                    "font_family": "inherit",
                    "font_size": "inherit",
                    "letter_spacing": "inherit",
                    "width": "100%",
                },
            ),
            class_name="field",
        ),
    )
