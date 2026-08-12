# Contributing

## Before shipping any CSS or UI change: verify against the real rendered page, not against reasoning alone

This project shipped several contrast/visibility bugs that all followed the
same pattern: a CSS fix looked correct on paper, got shipped, and turned out
wrong the moment someone actually looked at the rendered page — invisible
button text, a native red accent bleeding through three different widgets, a
stray focus ring, text hidden by a merged-content bug. In more than one case
a *second* guess, made without checking, was also wrong.

The fix that actually worked, every time, was the same: stop guessing at
Streamlit's internal DOM structure and CSS specificity, and instead

1. Render the actual element in a real browser (a small standalone
   Streamlit script is enough — see `tests/playwright/style_probe_app.py`).
2. Inspect the real computed styles (`getComputedStyle()`) and/or a real
   screenshot.
3. Only then write the fix, and verify it the same way before considering it
   done.

**This is not optional for CSS/`app/styles.py`/inline-HTML changes.**
Streamlit's internal component structure is not part of its public API, has
changed between versions before, and does not match what a quick look at the
Python source would suggest. Reasoning about what a fix "should" do is a
hypothesis, not a verification.

### What this looks like in practice

`tests/playwright/` exists specifically to make this fast and repeatable
instead of a one-off manual check every time:

- `style_probe_app.py` is a permanent fixture rendering every UI element
  type that has had a real bug: alert boxes (native and custom), the nav
  radio pill, checkbox, buttons, bullet lists, selectbox — using this app's
  real `app.styles.get_css_styles()`, not a reimplementation.
- `test_ui_contrast.py` / `test_ui_contrast_dark.py` assert computed colors
  against expected values, in both themes, across Chromium/Firefox/WebKit.

Before trusting any CSS change:

```bash
python -m pytest tests/playwright/ --browser chromium --browser firefox --browser webkit -v
```

If your change touches a UI element not already covered by the probe app,
add it there and write an assertion for it — that's how the coverage grew
to begin with, one real bug at a time. Don't just fix the one instance you
found and move on; the CI workflow (`.github/workflows/tests.yml`) checks
that a UI-affecting change is accompanied by a `tests/playwright/` change,
specifically so this isn't optional.

## Before shipping any change to the active-liveness gate

`run_verification_logic()` and `_capture_enrollment_photo()` in
`app/streamlit_app.py` are the only two functions that can finalize a
verification or enrollment decision, and both check
`active_challenge_passed` internally as a structural safety net — a real
bypass bug shipped here once, from two buttons that each independently
forgot to check the gate before calling into the decision logic.
`tests/test_active_liveness_gate.py` exists to catch that specific class of
regression; run it (it's part of the normal `pytest tests/` suite) before
trusting any change near this code path.

## Running the full test suite

```bash
pytest tests/ --ignore=tests/playwright        # backend logic (ML-heavy)
pytest tests/playwright/ --browser chromium --browser firefox --browser webkit  # UI/contrast
```

Both run automatically in CI on every push and pull request.
