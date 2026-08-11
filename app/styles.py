# app/styles.py
# Warm, consumer-grade light and dark themes matching Apple Face ID / modern banking app design.

from app.branding_config import PRIMARY_COLOR, ACCENT_COLOR

def get_css_styles(theme_mode="light"):
    is_dark = (theme_mode == "dark")
    
    # Theme color tokens
    bg_color = "#0F172A" if is_dark else "#F8FAFC"
    card_bg = "#1E293B" if is_dark else "#FFFFFF"
    card_border = "#334155" if is_dark else "#E2E8F0"
    text_color = "#F1F5F9" if is_dark else "#0F172A"
    # #64748B on this light-mode background measured ~3.6:1 contrast --
    # below the 4.5:1 WCAG AA minimum for normal-size text, which is why
    # checklist labels/subtitles/unselected-tab text read as too faint.
    # #475569 measures ~5.9:1, comfortably passing, while still reading as
    # visually secondary against the near-black primary text color.
    subtext_color = "#94A3B8" if is_dark else "#475569"
    input_bg = "#1E293B" if is_dark else "#FFFFFF"
    segment_bg = "#1E293B" if is_dark else "#F1F5F9"
    progress_bg = "#334155" if is_dark else "#F1F5F9"
    dot_inactive = "#475569" if is_dark else "#CBD5E1"

    # st.info/error/warning/success color pairs. Streamlit colors its own
    # native alert boxes from the browser/OS color scheme, independently of
    # this app's own theme_mode toggle above -- when the two disagree (e.g.
    # this app set to dark while the browser reports light), Streamlit
    # picks dark text meant for a light page and this app paints a dark
    # background under it, so the message becomes unreadable. Pinned
    # explicitly below so contrast always matches this app's actual
    # background, regardless of what the browser's own theme detection says.
    if is_dark:
        alert_info_bg, alert_info_text, alert_info_border = "#0C2D5E", "#93C5FD", "#1D4ED8"
        alert_error_bg, alert_error_text, alert_error_border = "#4C1414", "#FCA5A5", "#DC2626"
        alert_warning_bg, alert_warning_text, alert_warning_border = "#4A3200", "#FCD34D", "#D97706"
        alert_success_bg, alert_success_text, alert_success_border = "#052E1A", "#6EE7A0", "#059669"
    else:
        alert_info_bg, alert_info_text, alert_info_border = "#EFF6FF", "#1D4ED8", "#BFDBFE"
        alert_error_bg, alert_error_text, alert_error_border = "#FEF2F2", "#DC2626", "#FCA5A5"
        alert_warning_bg, alert_warning_text, alert_warning_border = "#FFFBEB", "#B45309", "#FDE68A"
        alert_success_bg, alert_success_text, alert_success_border = "#ECFDF5", "#059669", "#A7F3D0"

    return f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    /* Base Font Overrides */
    html, body, [class*="css"], .stApp {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }}
    
    /* Force Theme Colors globally across all elements */
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"], .main {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}
    
    /* Hide Sidebar Completely */
    [data-testid="stSidebar"] {{
        display: none !important;
    }}
    
    /* Consumer Card Elements */
    .consumer-card, div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: {card_bg} !important;
        border: 1px solid {card_border} !important;
        border-radius: 12px !important;
        padding: 24px !important;
        margin-bottom: 1.5rem !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -2px rgba(0, 0, 0, 0.02) !important;
        color: {text_color} !important;
    }}
    
    .consumer-title {{
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        color: {text_color} !important;
        margin-bottom: 0.5rem !important;
    }}
    
    .consumer-sub {{
        font-size: 0.85rem !important;
        color: {subtext_color} !important;
        margin-bottom: 1.5rem !important;
    }}

    /* Minimalist Badges */
    .status-badge {{
        display: inline-flex !important;
        align-items: center !important;
        gap: 6px !important;
        padding: 6px 12px !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        border-radius: 20px !important;
        border: 1px solid transparent !important;
    }}
    
    .status-badge.success {{
        background: #ECFDF5 !important;
        color: #059669 !important;
        border-color: #A7F3D0 !important;
    }}
    
    .status-badge.warning {{
        background: #FFFBEB !important;
        color: #D97706 !important;
        border-color: #FDE68A !important;
    }}
    
    .status-badge.danger {{
        background: #FEF2F2 !important;
        color: #DC2626 !important;
        border-color: #FCA5A5 !important;
    }}
    
    .status-badge.info {{
        background: #EFF6FF !important;
        color: {PRIMARY_COLOR} !important;
        border-color: #BFDBFE !important;
    }}

    /* Friendly Header Bar */
    .header-bar {{
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        padding: 16px 20px !important;
        margin-bottom: 2rem !important;
        background: {card_bg} !important;
        border: 1px solid {card_border} !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.01) !important;
    }}
    
    .header-logo {{
        width: 36px !important;
        height: 36px !important;
        background: {PRIMARY_COLOR} !important;
        border-radius: 8px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-weight: 800 !important;
        color: #FFFFFF !important;
        font-size: 1.2rem !important;
    }}
    
    .header-name {{
        font-weight: 700 !important;
        font-size: 1.15rem !important;
        color: {text_color} !important;
    }}

    /* Beautiful Segments for quality profiles */
    div.stRadio > div[role="radiogroup"] {{
        display: flex !important;
        flex-direction: row !important;
        background: {segment_bg} !important;
        border: 1px solid {card_border} !important;
        border-radius: 8px !important;
        padding: 4px !important;
        gap: 4px !important;
    }}
    
    div.stRadio > div[role="radiogroup"] > label {{
        flex: 1 !important;
        text-align: center !important;
        background: transparent !important;
        border-radius: 6px !important;
        padding: 6px 12px !important;
        color: {subtext_color} !important;
        transition: all 0.2s ease !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        margin: 0 !important;
        border: none !important;
        cursor: pointer !important;
    }}
    
    div.stRadio label[data-testid="stRadioOption"][data-selected="true"] {{
        background: {PRIMARY_COLOR} !important;
        border-radius: 6px !important;
    }}

    div.stRadio label[data-testid="stRadioOption"][data-selected="true"] [data-testid="stMarkdownContainer"] p {{
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }}

    /* Streamlit renders its own colored dot indicator next to each radio
    option (using Streamlit's default red accent, unrelated to this app's
    palette) as a plain div immediately before the option's text -- selected
    via that structural relationship rather than its emotion-generated
    class name, which is not stable across Streamlit versions. This app's
    pill-highlight styling above already shows which option is selected, so
    the dot is redundant and hidden rather than recolored. */
    div.stRadio label[data-testid="stRadioOption"] div:has(+ [data-testid="stMarkdownContainer"]) {{
        display: none !important;
    }}

    /* st.checkbox's box+checkmark, same structural approach: the box is a
    plain div immediately before the widget's text label. Pinned explicitly
    to this app's own palette rather than left to Streamlit's native
    checked-state color (default red, and not guaranteed to keep the
    checkmark itself legible against it in every environment). */
    div.stCheckbox div:has(+ [data-testid="stWidgetLabel"]) {{
        background: {input_bg} !important;
        border: 1.5px solid {card_border} !important;
        border-radius: 4px !important;
    }}
    div.stCheckbox label[data-selected="true"] div:has(+ [data-testid="stWidgetLabel"]) {{
        background: {PRIMARY_COLOR} !important;
        border-color: {PRIMARY_COLOR} !important;
    }}
    div.stCheckbox label[data-selected="true"] div:has(+ [data-testid="stWidgetLabel"]) svg,
    div.stCheckbox label[data-selected="true"] div:has(+ [data-testid="stWidgetLabel"]) polyline {{
        stroke: #FFFFFF !important;
    }}

    /* Stable WebRTC Component container styling */
    iframe[title="streamlit_webrtc.webrtc_streamer"], .stWebRtcStreamer, iframe {{
        width: 100% !important;
        aspect-ratio: 16 / 9 !important;
        height: auto !important;
        border-radius: 12px !important;
        border: 1px solid {card_border} !important;
        overflow: hidden !important;
        background: #000000 !important;
    }}
    
    .stWebRtcStreamer video {{
        width: 100% !important;
        height: 100% !important;
        aspect-ratio: 16 / 9 !important;
        object-fit: cover !important;
        border-radius: 12px !important;
    }}

    /* Friendly Round Buttons */
    div.stButton > button {{
        background: {PRIMARY_COLOR} !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
        width: 100% !important;
        box-shadow: 0 2px 4px 0 rgba(37, 99, 235, 0.1) !important;
    }}
    
    div.stButton > button:hover {{
        background: {ACCENT_COLOR} !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 6px 0 rgba(37, 99, 235, 0.15) !important;
    }}

    /* Streamlit wraps a button's label text in its own <p> tag, which the
    global bare-"p" text-color rule further down matches directly -- a
    direct rule on an element always wins over a color merely inherited
    from its parent, even with !important on both sides, so button text was
    silently coming out as this app's dark body-text color regardless of
    the white set on the button itself. Overridden here with higher
    selector specificity so button labels reliably render white. */
    div.stButton > button p {{
        color: #FFFFFF !important;
    }}
    
    div.stButton > button:active {{
        transform: translateY(0) !important;
    }}

    /* Quiet secondary look for manual fallback buttons */
    div.stButton > button[key*="manual_fallback"] {{
        background: transparent !important;
        color: {subtext_color} !important;
        border: 1px dashed {card_border} !important;
        font-size: 0.8rem !important;
        padding: 6px 16px !important;
        box-shadow: none !important;
        width: auto !important;
    }}
    div.stButton > button[key*="manual_fallback"]:hover {{
        background: {segment_bg} !important;
        color: {text_color} !important;
        border-color: {subtext_color} !important;
    }}

    /* Friendly Step Tracker Bar */
    .step-progress-container {{
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        background: {progress_bg} !important;
        border-radius: 8px !important;
        padding: 12px 20px !important;
        margin-bottom: 1.5rem !important;
    }}
    
    .step-progress-text {{
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: {text_color} !important;
    }}
    
    .step-progress-dots {{
        display: flex !important;
        gap: 6px !important;
    }}
    
    .step-dot {{
        width: 8px !important;
        height: 8px !important;
        border-radius: 50% !important;
        background: {dot_inactive} !important;
        transition: all 0.3s ease !important;
    }}
    
    .step-dot.active {{
        background: {PRIMARY_COLOR} !important;
        transform: scale(1.2) !important;
    }}
    
    .step-dot.completed {{
        background: #10B981 !important;
    }}
    
    /* Input and form controls overrides */
    div[data-baseweb="input"], input, select, div[role="listbox"], button[role="tab"] {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid {card_border} !important;
        border-radius: 6px !important;
    }}

    /* st.selectbox's outer wrapper (its own [role="group"] div, a level up
    from the <input> targeted above) shows Streamlit's default red accent
    as a border on focus -- same root cause as the earlier radio-dot fix:
    Streamlit's native focus/accent styling, unrelated to this app's own
    palette wherever this app hasn't explicitly overridden it. */
    div.stSelectbox [role="group"] {{
        border: 1px solid {card_border} !important;
        border-radius: 6px !important;
    }}
    div.stSelectbox [role="group"]:focus-within {{
        border-color: {PRIMARY_COLOR} !important;
    }}
    
    h1, h2, h3, h4, h5, h6, p, span, label, li, .stMarkdown, .stText, .stCheckbox {{
        color: {text_color} !important;
    }}

    /* Native st.info/error/warning/success alert boxes -- see the
    alert_*_bg/text/border comment above for why these are pinned
    explicitly instead of left to Streamlit's own theming. */
    [data-testid="stAlertContainer"] {{
        border-radius: 8px !important;
        border: 1px solid transparent !important;
    }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {{
        background: {alert_info_bg} !important;
        border-color: {alert_info_border} !important;
    }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) * {{
        color: {alert_info_text} !important;
    }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{
        background: {alert_error_bg} !important;
        border-color: {alert_error_border} !important;
    }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) * {{
        color: {alert_error_text} !important;
    }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{
        background: {alert_warning_bg} !important;
        border-color: {alert_warning_border} !important;
    }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) * {{
        color: {alert_warning_text} !important;
    }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {{
        background: {alert_success_bg} !important;
        border-color: {alert_success_border} !important;
    }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) * {{
        color: {alert_success_text} !important;
    }}

    /* Animated arrows for turn prompts */
    .face-arrow {{
        position: absolute !important;
        font-size: 2.2rem !important;
        color: #3b82f6 !important;
        font-weight: 700 !important;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3) !important;
    }}
    
    .face-arrow-left {{
        top: 50% !important;
        left: 20px !important;
        transform: translateY(-50%) !important;
        animation: guide-pulse-left 0.8s infinite alternate !important;
    }}
    
    .face-arrow-right {{
        top: 50% !important;
        right: 20px !important;
        transform: translateY(-50%) !important;
        animation: guide-pulse-right 0.8s infinite alternate !important;
    }}

    @keyframes guide-pulse-left {{
        from {{ transform: translateY(-50%) translateX(0); }}
        to {{ transform: translateY(-50%) translateX(-8px); }}
    }}
    
    @keyframes guide-pulse-right {{
        from {{ transform: translateY(-50%) translateX(0); }}
        to {{ transform: translateY(-50%) translateX(8px); }}
    }}

    /* Dynamic guidance text change animations */
    .guidance-text-container {{
        animation: guidance-fade-in 0.3s ease-out !important;
    }}
    
    @keyframes guidance-fade-in {{
        from {{ opacity: 0.6; transform: translateY(2px); }}
        to {{ opacity: 1.0; transform: translateY(0); }}
    }}

    /* Live "checks passing" checklist -- reuses the same status-badge
    success/warning color tokens above (#059669 green, #D97706 amber)
    rather than introducing new colors. */
    .checklist-grid {{
        display: grid !important;
        grid-template-columns: 1fr 1fr !important;
        gap: 6px 14px !important;
        margin-top: 10px !important;
    }}
    .checklist-item {{
        display: flex !important;
        align-items: center !important;
        gap: 7px !important;
        font-size: 0.78rem !important;
        color: {subtext_color} !important;
    }}
    .checklist-dot {{
        flex-shrink: 0 !important;
        width: 9px !important;
        height: 9px !important;
        border-radius: 50% !important;
    }}
    .checklist-dot.pass {{
        background: #059669 !important;
        border: 1px solid #059669 !important;
    }}
    .checklist-dot.fail {{
        background: transparent !important;
        border: 1.5px solid #D97706 !important;
    }}
    .checklist-dot.in_progress {{
        background: transparent !important;
        border: 1.5px solid {subtext_color} !important;
        animation: checklist-pulse 1s ease-in-out infinite !important;
    }}
    .checklist-dot.pending {{
        background: transparent !important;
        border: 1.5px solid {dot_inactive} !important;
    }}
    @keyframes checklist-pulse {{
        0%, 100% {{ opacity: 0.35; transform: scale(0.85); }}
        50% {{ opacity: 1.0; transform: scale(1.05); }}
    }}

    /* Premium Verified Success Screen and Checkmark Animation */
    .success-screen-card {{
        text-align: center !important;
        padding: 40px 24px !important;
        border-radius: 12px !important;
        background: #F0FDF4 !important;
        border: 1px solid #BBF7D0 !important;
        box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.05) !important;
        animation: success-card-fade 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
    }}
    
    .success-screen-title {{
        font-size: 1.5rem !important;
        font-weight: 800 !important;
        color: #166534 !important;
        margin-top: 20px !important;
        margin-bottom: 6px !important;
    }}
    
    .success-screen-sub {{
        font-size: 0.95rem !important;
        color: #15803D !important;
        font-weight: 600 !important;
    }}

    .success-checkmark-circle {{
        width: 84px !important;
        height: 84px !important;
        margin: 0 auto !important;
    }}
    
    .checkmark-svg {{
        width: 100% !important;
        height: 100% !important;
    }}
    
    .checkmark-circle-path {{
        stroke-dasharray: 166 !important;
        stroke-dashoffset: 166 !important;
        stroke-width: 3.5 !important;
        stroke-miterlimit: 10 !important;
        stroke: #10B981 !important;
        fill: none !important;
        animation: checkmark-stroke 0.5s cubic-bezier(0.65, 0, 0.45, 1) forwards !important;
    }}
    
    .checkmark-check-path {{
        transform-origin: 50% 50% !important;
        stroke-dasharray: 48 !important;
        stroke-dashoffset: 48 !important;
        stroke-width: 4.5 !important;
        stroke-linecap: round !important;
        stroke: #10B981 !important;
        fill: none !important;
        animation: checkmark-stroke-check 0.3s cubic-bezier(0.65, 0, 0.45, 1) 0.5s forwards !important;
    }}
    
    @keyframes checkmark-stroke {{
        100% {{ stroke-dashoffset: 0; }}
    }}
    
    @keyframes checkmark-stroke-check {{
        100% {{ stroke-dashoffset: 0; }}
    }}
    
    @keyframes success-card-fade {{
        from {{ transform: scale(0.96); opacity: 0; }}
        to {{ transform: scale(1.0); opacity: 1; }}
    }}
</style>
"""
