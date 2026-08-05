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
    .consumer-card {{
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

    /* Stable WebRTC Component container styling */
    iframe[title="streamlit_webrtc.webrtc_streamer"], .stWebRtcStreamer, iframe {{
        height: 340px !important;
        width: 100% !important;
        border-radius: 12px !important;
        border: 1px solid {card_border} !important;
        overflow: hidden !important;
        background: #000000 !important;
    }}
    
    .stWebRtcStreamer video {{
        width: 100% !important;
        height: 340px !important;
        object-fit: cover !important;
        border-radius: 12px !important;
    }}

    /* Crucial stacking context fix: Force the parent container block containing the overlay to have a higher z-index than the video iframe container */
    .element-container:has(.face-guide-overlay) {{
        position: relative !important;
        z-index: 9999 !important;
        pointer-events: none !important;
    }}

    /* Center face guide overlay using normal document flow shifted up by height of video container */
    .face-guide-overlay {{
        position: relative !important;
        margin-top: -340px !important; /* Pull overlay exactly on top of the 340px high camera */
        height: 340px !important;
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        pointer-events: none !important;
        z-index: 9999 !important;
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
    
    /* Head + Neck contour path styling */
    .guide-path {{
        fill: none !important;
        stroke: rgba(255, 255, 255, 0.85) !important;
        stroke-width: 3.5 !important;
        stroke-dasharray: 8,6 !important;
        transition: all 0.3s ease !important;
    }}
    
    .guide-path.detected {{
        stroke: #10B981 !important; /* Green */
        stroke-dasharray: none !important;
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
</style>
"""
