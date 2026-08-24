"""Stats and metrics scorecard component.

Uses the .panel + .meter + .index + .tag CSS classes from assets/critique.css.
"""

import reflex as rx

from critique_ui.state import State


def _meter(label: str, value_str: rx.Var, pct_var: rx.Var, lo: str, hi: str) -> rx.Component:
    """Animated meter bar with dotted tick marks."""
    return rx.el.div(
        rx.el.div(
            rx.el.span(label, class_name="meter__label"),
            rx.el.span(value_str, class_name="meter__val"),
            class_name="meter__head",
        ),
        rx.el.div(
            rx.el.div(
                class_name="meter__fill",
                style={"--fill": pct_var, "width": pct_var},
            ),
            class_name="meter__track",
        ),
        rx.el.div(
            rx.el.span(lo),
            rx.el.span(hi),
            class_name="meter__scale",
        ),
        class_name="meter",
    )


def stats_display_component() -> rx.Component:
    return rx.cond(
        State.has_result,
        rx.el.section(
            # Section title
            rx.el.div("Taste Analysis", class_name="card-title"),

            # Meters: Obscurity + Diversity
            rx.cond(
                State.has_scorecard,
                rx.el.div(
                    rx.cond(
                        State.has_obscurity,
                        _meter(
                            "Obscurity",
                            State.obscurity_pct,
                            State.obscurity_pct,
                            "mainstream",
                            "underground",
                        ),
                    ),
                    rx.cond(
                        State.has_diversity,
                        _meter(
                            "Diversity",
                            State.diversity_verdict,
                            State.diversity_pct,
                            "one-note",
                            "eclectic",
                        ),
                    ),
                    class_name="meters",
                ),
            ),

            # Index: dotted-leader rows for platform stats
            rx.cond(
                State.has_index_rows,
                rx.el.div(
                    rx.foreach(
                        State.index_rows,
                        lambda row: rx.el.div(
                            rx.el.span(row["key"], class_name="index__key"),
                            rx.el.div(class_name="index__dots"),
                            rx.el.span(row["value"], class_name="index__val"),
                            class_name="index__row",
                        ),
                    ),
                    class_name="index",
                    style={"margin_top": "1.6rem"},
                ),
            ),

            # Genre tags
            rx.cond(
                State.has_genres,
                rx.el.div(
                    rx.foreach(
                        State.top_genres,
                        lambda g: rx.el.span(g, class_name="tag"),
                    ),
                    class_name="tags",
                    style={"margin_top": "1.4rem"},
                ),
            ),

            class_name="panel rise",
            style={"--d": "0ms", "margin_top": "1.6rem"},
        ),
    )
