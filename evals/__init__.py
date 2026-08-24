"""Evaluation harness for Critique.

Measures whether generated critiques keep the promises made in
`critique/prompts.py` — grounding in real data, no invented items, length
compliance. Runs offline against frozen fixtures so results are comparable
across prompt and model changes.

    python -m evals.run selftest    # validate the metric itself, no API calls
    python -m evals.run run         # score the live model across tones
    python -m evals.run report      # aggregate a previous run
"""
