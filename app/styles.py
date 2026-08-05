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
    
    /* Warm Clean Light Theme Palette */
    .stApp {{
        background-color: #F8FAFC !important;
        color: #0F172A !important;
    }}
    
    /* Clean Sidebar */
    [data-testid="stSidebar"] {{
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
        padding-top: 2rem !important;
    }}
    
    /* Consumer Card Elements */
    .consumer-card {{
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -2px rgba(0, 0, 0, 0.02);
    }}
    
    .consumer-title {{
        font-size: 1.1rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 0.5rem;
    }}
    
    .consumer-sub {{
        font-size: 0.85rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }}

    /* Empty/Standby States */
    .clean-empty-state {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 30px 20px;
        text-align: center;
        border: 1.5px dashed #CBD5E1;
        border-radius: 8px;
        background: #F8FAFC;
        margin: 10px 0;
    }}
    
    .clean-empty-text {{
        font-size: 0.85rem;
        color: #64748B;
        font-weight: 500;
    }}

    /* Minimalist Badges */
    .status-badge {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        font-size: 0.75rem;
        font-weight: 600;
        border-radius: 20px;
        border: 1px solid transparent;
    }}
    
    .status-badge.success {{
        background: #ECFDF5;
        color: #059669;
        border-color: #A7F3D0;
    }}
    
    .status-badge.warning {{
        background: #FFFBEB;
        color: #D97706;
        border-color: #FDE68A;
    }}
    
    .status-badge.danger {{
        background: #FEF2F2;
        color: #DC2626;
        border-color: #FCA5A5;
    }}
    
    .status-badge.info {{
        background: #EFF6FF;
        color: {PRIMARY_COLOR};
        border-color: #BFDBFE;
    }}

    /* Friendly Header Bar */
    .header-bar {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px 20px;
        margin-bottom: 2rem;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.01);
    }}
    
    .header-logo {{
        width: 36px;
        height: 36px;
        background: {PRIMARY_COLOR};
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        color: #FFFFFF;
        font-size: 1.2rem;
    }}
    
    .header-name {{
        font-weight: 700;
        font-size: 1.15rem;
        color: #0F172A;
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

    /* Smooth rounded tabs */
    div[data-baseweb="tab-list"] {{
        background: #F1F5F9 !important;
        border-radius: 10px !important;
        padding: 4px !important;
        border: 1px solid #E2E8F0 !important;
        margin-bottom: 2rem !important;
        display: flex !important;
        justify-content: flex-start !important;
    }}
    
    button[data-baseweb="tab"] {{
        color: #64748B !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        padding: 10px 20px !important;
        background: transparent !important;
        border: none !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
        margin-right: 4px !important;
    }}
    
    button[data-baseweb="tab"]:hover {{
        color: #0F172A !important;
    }}
    
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: #0F172A !important;
        background: #FFFFFF !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05) !important;
    }}

    /* Camera wrapper & absolute Face Guide overlay styling */
    [data-testid="column"] {{
        position: relative !important;
    }}
    
    .camera-wrapper {{
        position: relative !important;
        width: 100% !important;
        border-radius: 12px !important;
        overflow: hidden !important;
        border: 1px solid #E2E8F0 !important;
        background: #000000 !important;
    }}
    
    .face-guide-overlay {{
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        pointer-events: none !important;
        z-index: 100 !important;
    }}
    
    .face-oval {{
        width: 175px !important;
        height: 240px !important;
        border: 3px dashed rgba(255, 255, 255, 0.75) !important;
        border-radius: 50% !important;
        box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.4) !important;
        transition: all 0.3s ease !important;
        position: relative !important;
    }}
    
    .face-oval.detected {{
        border-style: solid !important;
        border-color: #10B981 !important; /* Green border when face is detected */
        box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.15) !important;
    }}
    
    /* Friendly direction arrows for posture prompts */
    .face-arrow {{
        position: absolute !important;
        font-size: 2.2rem !important;
        color: {PRIMARY_COLOR} !important;
        font-weight: 700 !important;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
    }}
    
    .face-arrow-left {{
        top: 50% !important;
        left: -45px !important;
        transform: translateY(-50%) !important;
        animation: guide-pulse-left 0.8s infinite alternate !important;
    }}
    
    .face-arrow-right {{
        top: 50% !important;
        right: -45px !important;
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
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #F1F5F9;
        border-radius: 8px;
        padding: 12px 20px;
        margin-bottom: 1.5rem;
    }}
    
    .step-progress-text {{
        font-size: 0.85rem;
        font-weight: 600;
        color: #0F172A;
    }}
    
    .step-progress-dots {{
        display: flex;
        gap: 6px;
    }}
    
    .step-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #CBD5E1;
        transition: all 0.3s ease;
    }}
    
    .step-dot.active {{
        background: {PRIMARY_COLOR};
        transform: scale(1.2);
    }}
    
    .step-dot.completed {{
        background: #10B981;
    }}
</style>
