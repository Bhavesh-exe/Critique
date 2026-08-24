"""Hero masthead component for Critique - The Critic's Desk.

Uses the CSS class system from assets/critique.css:
  .kicker        - mono uppercase strip (vol / issue labels)
  .wordmark      - Bodoni Moda display heading with settling animation
  .standfirst    - italic serif subtitle
"""

import reflex as rx


from critique_ui.state import State


def header_component() -> rx.Component:
    return rx.el.header(
        # Kicker: mono caps metadata strip with Dark/Light mode toggle
        rx.el.div(
            rx.el.div(
                rx.el.span("Vol. I", class_name="kicker__accent"),
                rx.el.span(" · Critique · "),
                rx.el.span("AI Taste Judge", class_name="kicker__accent"),
                style={"display": "flex", "align_items": "center", "gap": "0.3rem"},
            ),
            rx.el.button(
                rx.icon(State.theme_icon, size=13),
                rx.el.span(State.theme_label),
                class_name="theme-toggle",
                on_click=State.toggle_theme,
                type="button",
            ),
            class_name="kicker rise",
            style={"--d": "0ms", "display": "flex", "justify_content": "space-between", "align_items": "center", "width": "100%"},
        ),
        # Wordmark: the signature settling animation
        rx.el.h1(
            "Critiqu",
            rx.el.em("e"),
            class_name="wordmark",
        ),
        # Standfirst: italic serif subtitle
        rx.el.p(
            "Your taste. On record. Judged by machine.",
            class_name="standfirst rise",
            style={"--d": "200ms"},
        ),
        style={"margin_bottom": "2.5rem"},
    )
