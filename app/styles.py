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
    subtext_color = "#94A3B8" if is_dark else "#64748B"
    input_bg = "#1E293B" if is_dark else "#FFFFFF"
    segment_bg = "#1E293B" if is_dark else "#F1F5F9"
    progress_bg = "#334155" if is_dark else "#F1F5F9"
    dot_inactive = "#475569" if is_dark else "#CBD5E1"
    
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
    
    div.stRadio > div[role="radiogroup"] div[data-checked="true"] {{
        background: {PRIMARY_COLOR} !important;
        border-radius: 6px !important;
    }}
    
    div.stRadio > div[role="radiogroup"] div[data-checked="true"] span {{
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }}

    /* Wrap the camera video and the guide overlay in a relative box with absolute children */
    div[data-testid="stVerticalBlock"]:has(iframe[title="streamlit_webrtc.webrtc_streamer"]):has(.face-guide-overlay) {{
        position: relative !important;
        height: 340px !important;
        width: 100% !important;
        margin: 0 auto !important;
        overflow: hidden !important;
        border-radius: 12px !important;
    }}

    /* Position the WebRTC iframe container absolutely inside the relative block */
    div[data-testid="stVerticalBlock"]:has(iframe[title="streamlit_webrtc.webrtc_streamer"]):has(.face-guide-overlay) > .element-container:has(iframe[title="streamlit_webrtc.webrtc_streamer"]) {{
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100% !important;
        z-index: 1 !important;
        margin: 0 !important;
        padding: 0 !important;
    }}

    /* Position the overlay container absolutely inside the relative block, covering 100% of the box */
    div[data-testid="stVerticalBlock"]:has(iframe[title="streamlit_webrtc.webrtc_streamer"]):has(.face-guide-overlay) > .element-container:has(.face-guide-overlay) {{
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100% !important;
        z-index: 9999 !important;
        margin: 0 !important;
        padding: 0 !important;
        pointer-events: none !important;
    }}

    /* Stable WebRTC Component container styling */
    iframe[title="streamlit_webrtc.webrtc_streamer"], .stWebRtcStreamer, iframe {{
        height: 100% !important;
        width: 100% !important;
        border-radius: 12px !important;
        border: 1px solid {card_border} !important;
        overflow: hidden !important;
        background: #000000 !important;
    }}
    
    .stWebRtcStreamer video {{
        width: 100% !important;
        height: 100% !important;
        object-fit: cover !important;
        border-radius: 12px !important;
    }}

    /* Face guide overlay styles */
    .face-guide-overlay {{
        height: 100% !important;
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        pointer-events: none !important;
    }}
    
    .face-svg-container {{
        width: 245px !important;
        height: 315px !important;
        position: relative !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}
    
    .guide-svg {{
        width: 100% !important;
        height: 100% !important;
    }}
    
    /* Head + Neck contour path styling with dynamic state transitions */
    .guide-path {{
        fill: none !important;
        stroke: rgba(148, 163, 184, 0.95) !important; /* Neutral gray-dashed, increased opacity */
        stroke-width: 4.5 !important; /* Increased visual weight */
        stroke-dasharray: 10,8 !important;
        transition: stroke 0.3s ease, stroke-dasharray 0.3s ease !important;
    }}
    
    /* Amber/Orange outline warning state */
    .guide-path.warning {{
        stroke: #F59E0B !important; /* Amber */
        stroke-dasharray: 10,8 !important;
        animation: guide-pulse-warning 1s infinite alternate !important;
    }}
    
    /* Green outline success state */
    .guide-path.success {{
        stroke: #10B981 !important; /* Emerald Green */
        stroke-dasharray: none !important;
    }}
    
    @keyframes guide-pulse-warning {{
        from {{ opacity: 0.65; }}
        to {{ opacity: 1.0; }}
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
    
    h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown, .stText, .stCheckbox {{
        color: {text_color} !important;
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
