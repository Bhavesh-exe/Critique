"""Raw data appendix component.

Uses native HTML <details>/<summary> with .appendix CSS classes
from assets/critique.css. No Radix dependency.
"""

import reflex as rx

from critique_ui.state import State


def raw_accordion_component() -> rx.Component:
    return rx.cond(
        State.has_result,
        rx.el.details(
            rx.el.summary(
                rx.icon("chevron_right", size=14, class_name="appendix__chev"),
                rx.el.span("Inspect Raw AI Context Data"),
                class_name="appendix__summary",
            ),
            rx.el.div(
                rx.el.pre(
                    State.raw_summary,
                    class_name="appendix__pre",
                ),
                class_name="appendix__body",
            ),
            class_name="appendix",
        ),
    )
