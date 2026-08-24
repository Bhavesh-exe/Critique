"""Verdict card component - the editorial payoff.

Uses .verdict CSS class system from assets/critique.css:
  .verdict           - outer container with left-edge accent bar (::before)
  .verdict__scan     - one-time scan sweep animation on reveal
  .verdict__head     - mono metadata strip (tone + handle + platform)
  .verdict__title    - serif heading
  .verdict__body     - serif body with Didone drop cap (::first-letter)
  .verdict__foot     - bottom rule with copy button
  .ghost-btn         - transparent outlined button
"""

import reflex as rx

from critique_ui.state import State


def verdict_card_component() -> rx.Component:
    return rx.cond(
        State.has_result,
        rx.el.article(
            # Scan sweep animation overlay - plays once on reveal
            rx.el.div(class_name="verdict__scan"),
            # Metadata strip
            rx.el.div(
                rx.el.span(State.verdict_title, class_name="verdict__stamp"),
                rx.el.span(State.dossier_line),
                class_name="verdict__head",
            ),
            # Serif heading
            rx.el.h2(
                State.verdict_title,
                " Verdict",
                class_name="verdict__title",
            ),
            # Body copy with drop cap
            rx.el.p(
                State.verdict,
                class_name="verdict__body",
            ),
            # Footer: byline + copy button
            rx.el.div(
                rx.el.span("AI-Generated Cultural Critique"),
                rx.el.button(
                    rx.icon("copy", size=14),
                    " Copy Verdict",
                    class_name="ghost-btn",
                    on_click=[
                        State.copy_verdict,
                        rx.toast.info("Verdict copied to clipboard!"),
                    ],
                    type="button",
                ),
                class_name="verdict__foot",
            ),
            class_name="verdict",
        ),
    )
