"""
tests/playwright/test_ui_contrast_dark.py

Targeted dark-mode audit (a gap this project had: almost all of this
session's live back-and-forth debugging happened in light mode, so dark
mode was the least-checked area). A manual visual pass found dark mode
already in good shape -- these tests lock that state in as regression
protection rather than leaving it unverified.

Same structure as test_ui_contrast.py's light-mode tests; expected values
come directly from app/styles.py's `if is_dark:` branch. Computed-style
assertions only (no screenshot baseline) -- one baseline per theme is
enough to prove the screenshot-diff mechanism works; the real regression
protection for both themes lives in these color assertions.
"""
import pytest

PRIMARY_COLOR_RGB = "rgb(51, 65, 85)"        # #334155 -- theme-independent
WHITE_RGB = "rgb(255, 255, 255)"
DARK_MODE_TEXT_RGB = "rgb(241, 245, 249)"    # #F1F5F9
DARK_MODE_CARD_BORDER_RGB = "rgb(51, 65, 85)"  # #334155

DARK_ALERT_INFO_BG_RGB = "rgb(12, 45, 94)"      # #0C2D5E
DARK_ALERT_ERROR_BG_RGB = "rgb(76, 20, 20)"     # #4C1414
DARK_ALERT_WARNING_BG_RGB = "rgb(74, 50, 0)"    # #4A3200
DARK_ALERT_SUCCESS_BG_RGB = "rgb(5, 46, 26)"    # #052E1A

STREAMLIT_DEFAULT_RED_RGB = "rgb(255, 75, 75)"

PROBE_VIEWPORT = {"width": 900, "height": 1150}


@pytest.fixture
def probe_page(page, style_probe_url_dark):
    page.set_viewport_size(PROBE_VIEWPORT)
    page.goto(style_probe_url_dark, wait_until="networkidle")
    page.wait_for_timeout(1500)
    return page


def test_button_label_text_is_readable_white_dark(probe_page):
    color = probe_page.eval_on_selector("div.stButton button p", "el => getComputedStyle(el).color")
    assert color == WHITE_RGB, f"button label text should be white in dark mode too, got {color}"


def test_native_alert_boxes_use_dark_tokens(probe_page):
    expectations = [
        ("stAlertContentInfo", DARK_ALERT_INFO_BG_RGB),
        ("stAlertContentError", DARK_ALERT_ERROR_BG_RGB),
        ("stAlertContentWarning", DARK_ALERT_WARNING_BG_RGB),
        ("stAlertContentSuccess", DARK_ALERT_SUCCESS_BG_RGB),
    ]
    for testid, expected_bg in expectations:
        bg = probe_page.eval_on_selector(
            f'[data-testid="{testid}"]',
            "el => getComputedStyle(el.closest('[data-testid=\"stAlertContainer\"]')).backgroundColor",
        )
        assert bg == expected_bg, f"{testid} dark-mode background should be {expected_bg}, got {bg}"


def test_custom_alert_boxes_match_native_dark_tokens(probe_page):
    expectations = [
        ("info", DARK_ALERT_INFO_BG_RGB),
        ("error", DARK_ALERT_ERROR_BG_RGB),
        ("warning", DARK_ALERT_WARNING_BG_RGB),
        ("success", DARK_ALERT_SUCCESS_BG_RGB),
    ]
    for kind, expected_bg in expectations:
        bg = probe_page.eval_on_selector(f".app-alert-box.{kind}", "el => getComputedStyle(el).backgroundColor")
        assert bg == expected_bg, f".app-alert-box.{kind} dark-mode background should be {expected_bg}, got {bg}"


def test_nav_radio_selected_pill_uses_app_palette_dark(probe_page):
    bg = probe_page.eval_on_selector(
        'label[data-testid="stRadioOption"][data-selected="true"]',
        "el => getComputedStyle(el).backgroundColor",
    )
    assert bg == PRIMARY_COLOR_RGB, f"selected nav pill should use the app's primary color in dark mode, got {bg}"


def test_checkbox_checked_state_uses_app_palette_dark(probe_page):
    bg = probe_page.eval_on_selector(
        'div.stCheckbox label[data-selected="true"] div:has(+ [data-testid="stWidgetLabel"])',
        "el => getComputedStyle(el).backgroundColor",
    )
    assert bg == PRIMARY_COLOR_RGB, f"checked checkbox should use the app's primary color in dark mode, got {bg}"

    checkmark_color = probe_page.eval_on_selector(
        'div.stCheckbox label[data-selected="true"] svg',
        "el => getComputedStyle(el).stroke",
    )
    assert checkmark_color == WHITE_RGB, f"checkmark should stay white for contrast in dark mode, got {checkmark_color}"


def test_bullet_list_text_has_readable_contrast_dark(probe_page):
    color = probe_page.eval_on_selector("li", "el => getComputedStyle(el).color")
    assert color == DARK_MODE_TEXT_RGB, f"bullet list text should be the dark-mode body text color, got {color}"


def test_selectbox_border_uses_app_palette_not_red_focus_ring_dark(probe_page):
    border = probe_page.eval_on_selector('.stSelectbox [role="group"]', "el => getComputedStyle(el).borderColor")
    assert border == DARK_MODE_CARD_BORDER_RGB, f"selectbox border should be the dark-mode neutral border color, got {border}"
    assert border != STREAMLIT_DEFAULT_RED_RGB


def test_no_streamlit_default_red_anywhere_on_page_dark(probe_page):
    matches = probe_page.evaluate(
        """() => {
            const all = document.querySelectorAll('*');
            const hits = [];
            for (const el of all) {
                const cs = getComputedStyle(el);
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
    assert matches == [], f"Streamlit's default red accent leaked through in dark mode on: {matches}"
