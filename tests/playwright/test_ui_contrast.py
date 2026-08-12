"""
tests/playwright/test_ui_contrast.py

Regression tests for the UI contrast/color bugs found and fixed during
this project's live testing: invisible button text, a native red accent
bleeding through the radio nav and checkbox, a red focus ring on the
selectbox, and low-contrast bullet-list text. Each of these was found by
a human clicking around and screenshotting -- these tests exist so the
same class of bug is caught automatically instead.

Uses pytest-playwright's `page` fixture, which already supports running
this whole file once per browser via `pytest --browser chromium
--browser firefox --browser webkit` (see pytest.ini/CI config) --
computed CSS values are reliable across browsers, unlike pixel-exact
screenshots, so cross-browser coverage lives here, not in the screenshot
test below.
"""
import os

import pytest

BASELINE_DIR = os.path.join(os.path.dirname(__file__), "baselines")

# Expected values, derived directly from app/branding_config.py and
# app/styles.py's light-mode token definitions -- if these ever
# legitimately change (a deliberate palette change), update both the
# source file and this test together, not just one.
PRIMARY_COLOR_RGB = "rgb(51, 65, 85)"       # #334155
WHITE_RGB = "rgb(255, 255, 255)"
BODY_TEXT_RGB = "rgb(15, 23, 42)"           # #0F172A
CARD_BORDER_RGB = "rgb(226, 232, 240)"      # #E2E8F0
ALERT_INFO_BG_RGB = "rgb(239, 246, 255)"    # #EFF6FF
ALERT_ERROR_BG_RGB = "rgb(254, 242, 242)"   # #FEF2F2
ALERT_WARNING_BG_RGB = "rgb(255, 251, 235)" # #FFFBEB
ALERT_SUCCESS_BG_RGB = "rgb(236, 253, 245)" # #ECFDF5

# Streamlit's own default accent color -- must NEVER appear anywhere in
# this app's rendered UI. Every bug this file guards against was this
# exact color leaking through unstyled.
STREAMLIT_DEFAULT_RED_RGB = "rgb(255, 75, 75)"


# Playwright's full_page=True screenshot capture does not reliably extend
# past the viewport for this app (Streamlit manages its own internal
# scroll container) -- confirmed directly rather than assumed, so instead
# of relying on full-page capture, the viewport itself is sized generously
# above the probe app's actual content height (~1080px at this width).
PROBE_VIEWPORT = {"width": 900, "height": 1150}


@pytest.fixture
def probe_page(page, style_probe_url_light):
    page.set_viewport_size(PROBE_VIEWPORT)
    page.goto(style_probe_url_light, wait_until="networkidle")
    page.wait_for_timeout(1500)
    return page


def test_button_label_text_is_readable_white(probe_page):
    # The actual bug: Streamlit wraps button labels in a <p> tag that a
    # broad global text-color rule was overriding to near-black, even
    # though the button itself was styled white -- a direct rule on the
    # <p> element beats a color merely inherited from its parent button.
    color = probe_page.eval_on_selector("div.stButton button p", "el => getComputedStyle(el).color")
    assert color == WHITE_RGB, f"button label text should be white, got {color}"


def test_alert_boxes_use_app_palette_not_browser_theme(probe_page):
    # Streamlit colors its native alert boxes from the browser/OS color
    # scheme independently of this app's own theme -- pinned explicitly
    # so they always match regardless of what the browser thinks.
    expectations = [
        ("stAlertContentInfo", ALERT_INFO_BG_RGB),
        ("stAlertContentError", ALERT_ERROR_BG_RGB),
        ("stAlertContentWarning", ALERT_WARNING_BG_RGB),
        ("stAlertContentSuccess", ALERT_SUCCESS_BG_RGB),
    ]
    for testid, expected_bg in expectations:
        bg = probe_page.eval_on_selector(
            f'[data-testid="{testid}"]',
            "el => getComputedStyle(el.closest('[data-testid=\"stAlertContainer\"]')).backgroundColor",
        )
        assert bg == expected_bg, f"{testid} background should be {expected_bg}, got {bg}"


def test_custom_alert_boxes_match_native_alert_tokens(probe_page):
    # This app's own custom alert-style boxes (.app-alert-box, used for
    # things like "Look at the camera" / "Photo captured successfully")
    # were previously hand-maintained with slightly different shades than
    # the native st.info/error/warning/success boxes above -- migrated to
    # share the exact same tokens, so a fix to one can't silently drift
    # from the other. Same expected colors as the native-alert test.
    expectations = [
        ("info", ALERT_INFO_BG_RGB),
        ("error", ALERT_ERROR_BG_RGB),
        ("warning", ALERT_WARNING_BG_RGB),
        ("success", ALERT_SUCCESS_BG_RGB),
    ]
    for kind, expected_bg in expectations:
        bg = probe_page.eval_on_selector(f".app-alert-box.{kind}", "el => getComputedStyle(el).backgroundColor")
        assert bg == expected_bg, f".app-alert-box.{kind} background should be {expected_bg}, got {bg}"


def test_nav_radio_selected_pill_uses_app_palette(probe_page):
    bg = probe_page.eval_on_selector(
        'label[data-testid="stRadioOption"][data-selected="true"]',
        "el => getComputedStyle(el).backgroundColor",
    )
    assert bg == PRIMARY_COLOR_RGB, f"selected nav pill should use the app's primary color, got {bg}"
    assert bg != STREAMLIT_DEFAULT_RED_RGB


def test_nav_radio_native_dot_is_hidden(probe_page):
    # Streamlit renders its own colored dot indicator (Streamlit's default
    # red accent) next to each radio option -- this app's pill highlight
    # already shows selection, so the redundant dot must stay hidden.
    display = probe_page.eval_on_selector(
        'label[data-testid="stRadioOption"] div:has(+ [data-testid="stMarkdownContainer"])',
        "el => getComputedStyle(el).display",
    )
    assert display == "none", f"native radio dot should be hidden, got display={display}"


def test_checkbox_checked_state_uses_app_palette(probe_page):
    bg = probe_page.eval_on_selector(
        'div.stCheckbox label[data-selected="true"] div:has(+ [data-testid="stWidgetLabel"])',
        "el => getComputedStyle(el).backgroundColor",
    )
    assert bg == PRIMARY_COLOR_RGB, f"checked checkbox should use the app's primary color, got {bg}"
    assert bg != STREAMLIT_DEFAULT_RED_RGB

    checkmark_color = probe_page.eval_on_selector(
        'div.stCheckbox label[data-selected="true"] svg',
        "el => getComputedStyle(el).stroke",
    )
    assert checkmark_color == WHITE_RGB, f"checkmark should be white for contrast, got {checkmark_color}"


def test_bullet_list_text_has_readable_contrast(probe_page):
    # <li> was missing from the global text-color rule, so bullet lists
    # (e.g. "Before you start") fell back to Streamlit's lighter default.
    color = probe_page.eval_on_selector("li", "el => getComputedStyle(el).color")
    assert color == BODY_TEXT_RGB, f"bullet list text should be this app's body text color, got {color}"


def test_selectbox_border_uses_app_palette_not_red_focus_ring(probe_page):
    border = probe_page.eval_on_selector(
        '.stSelectbox [role="group"]',
        "el => getComputedStyle(el).borderColor",
    )
    assert border == CARD_BORDER_RGB, f"selectbox border should be the app's neutral border color, got {border}"
    assert border != STREAMLIT_DEFAULT_RED_RGB


def test_no_streamlit_default_red_anywhere_on_page(probe_page):
    # Broadest possible guard: whatever specific element the next version
    # of this bug shows up on, Streamlit's own default accent color
    # should never appear anywhere in this app's rendered page at all.
    matches = probe_page.evaluate(
        """() => {
            const all = document.querySelectorAll('*');
            const hits = [];
            for (const el of all) {
                const cs = getComputedStyle(el);
                // Skip elements that aren't actually visible (e.g. the
                // native radio dot, deliberately hidden via display:none
                // -- its computed color is irrelevant since it's never
                // painted) -- only a color a user could actually see counts.
                if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) {
                    continue;
                }
                if (cs.backgroundColor === 'rgb(255, 75, 75)' || cs.color === 'rgb(255, 75, 75)' || cs.borderColor === 'rgb(255, 75, 75)') {
                    hits.push(el.tagName + '.' + el.className);
                }
            }
            return hits;
        }"""
    )
    assert matches == [], f"Streamlit's default red accent leaked through on: {matches}"


def test_full_page_screenshot_matches_baseline(probe_page, browser_name):
    if browser_name != "chromium":
        pytest.skip("Pixel-exact screenshot regression runs on chromium only -- cross-browser font "
                    "rendering differences make exact pixel comparison unreliable on firefox/webkit; "
                    "the computed-style tests above already provide real cross-browser coverage.")

    baseline_path = os.path.join(BASELINE_DIR, "style_probe_light_chromium.png")
    if not os.path.exists(baseline_path):
        pytest.skip(f"No baseline image at {baseline_path} yet -- run once to establish one")

    # Viewport-only, not full_page=True -- see PROBE_VIEWPORT's comment.
    current = probe_page.screenshot()
    with open(baseline_path, "rb") as f:
        baseline = f.read()

    # Byte-identical is too strict (anti-aliasing can vary by a pixel run
    # to run even on the same engine); compare via a lightweight mean
    # pixel-difference check instead of requiring exact equality.
    import io
    from PIL import Image
    import numpy as np

    img_current = np.array(Image.open(io.BytesIO(current)).convert("RGB"))
    img_baseline = np.array(Image.open(io.BytesIO(baseline)).convert("RGB"))

    if img_current.shape != img_baseline.shape:
        pytest.fail(
            f"Screenshot dimensions changed: baseline {img_baseline.shape} vs current {img_current.shape} "
            f"-- likely a real layout change, review and update the baseline if intentional"
        )

    mean_diff = float(np.abs(img_current.astype(int) - img_baseline.astype(int)).mean())
    assert mean_diff < 5.0, (
        f"Full-page screenshot differs from baseline by mean pixel diff {mean_diff:.2f} "
        f"(threshold 5.0) -- review the change; if intentional, update "
        f"tests/playwright/baselines/style_probe_light_chromium.png"
    )
