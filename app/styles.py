# app/styles.py
# Warm, consumer-grade light styling matching Apple Face ID / modern banking app design.

from app.branding_config import PRIMARY_COLOR, ACCENT_COLOR

CSS_STYLES = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    /* Base Font Overrides */
    html, body, [class*="css"], .stApp {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }}
    
    /* Force Light Theme Colors globally across all elements */
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"], .main {{
        background-color: #F8FAFC !important;
        color: #0F172A !important;
    }}
    
    /* Hide Sidebar Completely */
    [data-testid="stSidebar"] {{
        display: none !important;
    }}
    
    /* Consumer Card Elements */
    .consumer-card {{
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 24px !important;
        margin-bottom: 1.5rem !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -2px rgba(0, 0, 0, 0.02) !important;
        color: #0F172A !important;
    }}
    
    .consumer-title {{
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        margin-bottom: 0.5rem !important;
    }}
    
    .consumer-sub {{
        font-size: 0.85rem !important;
        color: #64748B !important;
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
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
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
        color: #0F172A !important;
    }}

    /* Beautiful Segments for quality profiles */
    div.stRadio > div[role="radiogroup"] {{
        display: flex !important;
        flex-direction: row !important;
        background: #F1F5F9 !important;
        border: 1px solid #E2E8F0 !important;
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
        color: #64748B !important;
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

    /* Control the camera components size and iframe dimensions directly */
    iframe[title="streamlit_webrtc.webrtc_streamer"], .stWebRtcStreamer, iframe {{
        height: 340px !important;
        width: 100% !important;
        border-radius: 12px !important;
        border: 1px solid #E2E8F0 !important;
        overflow: hidden !important;
    }}
    
    .camera-wrapper {{
        width: 100% !important;
        height: 340px !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }}

    /* Centered dashed oval overlay in parent DOM on top of WebRTC iframe */
    .face-guide-overlay {{
        position: relative !important;
        margin-top: -340px !important; /* Pull overlay exactly on top of the 340px high camera */
        height: 340px !important;
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        pointer-events: none !important;
        z-index: 1000 !important;
    }}
    
    .face-oval {{
        width: 180px !important;
        height: 245px !important;
        border: 3.5px dashed rgba(255, 255, 255, 0.85) !important;
        border-radius: 50% !important;
        box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.45) !important; /* Vignette cutout */
        transition: all 0.3s ease !important;
        position: relative !important;
    }}
    
    .face-oval.detected {{
        border-style: solid !important;
        border-color: #10B981 !important; /* Green */
        box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.15) !important;
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
        background: #F1F5F9 !important;
        border-radius: 8px !important;
        padding: 12px 20px !important;
        margin-bottom: 1.5rem !important;
    }}
    
    .step-progress-text {{
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: #0F172A !important;
    }}
    
    .step-progress-dots {{
        display: flex !important;
        gap: 6px !important;
    }}
    
    .step-dot {{
        width: 8px !important;
        height: 8px !important;
        border-radius: 50% !important;
        background: #CBD5E1 !important;
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
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 6px !important;
    }}
    
    h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown, .stText, .stCheckbox {{
        color: #0F172A !important;
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
