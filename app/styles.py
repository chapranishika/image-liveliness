# app/styles.py
# Clean modular stylesheet holding all presentation layout variables dynamically matching branding configuration.

from app.branding_config import COMPANY_NAME, PRIMARY_COLOR, ACCENT_COLOR

CSS_STYLES = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    /* Base Font Overrides */
    html, body, [class*="css"], .stApp {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }}
    
    .mono-text, .system-monitor, .compliance-badge, .diagnostic-console, .step-indicator-bar, .preview-box-empty, .artifact-meta, .code-output {{
        font-family: 'JetBrains Mono', monospace !important;
    }}
    
    /* Strict Industrial Dark Color Palette */
    .stApp {{
        background-color: #0A0D12 !important;
        color: #E2E8F0 !important;
    }}
    
    /* Premium Asymmetric Sidebar */
    [data-testid="stSidebar"] {{
        background-color: #07090D !important;
        border-right: 1px solid #1E293B !important;
        padding-top: 2rem !important;
    }}
    
    /* Branding Area / Top Bar area */
    .top-brand-bar {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        margin-bottom: 2rem;
        background: #0E121A;
        border: 1px solid #1E293B;
        border-radius: 6px;
    }}
    .brand-logo-slot {{
        width: 32px;
        height: 32px;
        background: {PRIMARY_COLOR};
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        color: #0A0D12;
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.1rem;
    }}
    .brand-name {{
        font-weight: 700;
        font-size: 1.1rem;
        color: #F8FAFC;
        letter-spacing: 0.05em;
        font-family: 'JetBrains Mono', monospace;
    }}
    .brand-tagline {{
        font-size: 0.75rem;
        color: #64748B;
        margin-left: auto;
        font-family: 'JetBrains Mono', monospace;
    }}

    /* Card Components */
    .dashboard-card {{
        background: #0E121A;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 20px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
    }}
    .dashboard-card-title {{
        font-size: 0.75rem;
        font-weight: 700;
        color: #94A3B8;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 1rem;
        border-bottom: 1px solid #1E293B;
        padding-bottom: 8px;
        font-family: 'JetBrains Mono', monospace;
    }}

    /* Empty/Loading States */
    .empty-state {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
        text-align: center;
        border: 1px dashed #1E293B;
        border-radius: 4px;
        background: rgba(14, 18, 26, 0.5);
        margin: 10px 0;
    }}
    .empty-state-icon {{
        font-size: 1.25rem;
        color: #475569;
        margin-bottom: 8px;
        font-family: 'JetBrains Mono', monospace;
    }}
    .empty-state-text {{
        font-size: 0.8rem;
        color: #94A3B8;
        font-weight: 500;
        font-family: 'JetBrains Mono', monospace;
    }}
    .empty-state-sub {{
        font-size: 0.7rem;
        color: #475569;
        margin-top: 4px;
        font-family: 'JetBrains Mono', monospace;
    }}

    /* Clinical Badges/Pills */
    .status-pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        font-size: 0.7rem;
        font-weight: 600;
        border-radius: 3px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-family: 'JetBrains Mono', monospace !important;
    }}
    .status-pill.success {{
        background: rgba(16, 185, 129, 0.1);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.2);
    }}
    .status-pill.warning {{
        background: rgba(245, 158, 11, 0.1);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.2);
    }}
    .status-pill.danger {{
        background: rgba(244, 63, 94, 0.1);
        color: #f43f5e;
        border: 1px solid rgba(244, 63, 94, 0.2);
    }}
    .status-pill.info {{
        background: rgba(6, 182, 212, 0.1);
        color: {PRIMARY_COLOR};
        border: 1px solid rgba(6, 182, 212, 0.2);
    }}
    .status-pill.neutral {{
        background: rgba(71, 85, 105, 0.1);
        color: #94A3B8;
        border: 1px solid rgba(71, 85, 105, 0.2);
    }}

    /* Clinical End User Reassurance Message */
    .reassurance-bar {{
        background: rgba(6, 182, 212, 0.08);
        border-left: 3px solid {PRIMARY_COLOR};
        padding: 10px 16px;
        margin-bottom: 1.25rem;
        font-size: 0.85rem;
        font-weight: 500;
        color: #F8FAFC;
    }}

    /* Segmented Quality Profile Selector (Streamlit Radio horizontal styling override) */
    div.stRadio > div[role="radiogroup"] {{
        display: flex !important;
        flex-direction: row !important;
        background: #0B0E14 !important;
        border: 1px solid #1E293B !important;
        border-radius: 4px !important;
        padding: 4px !important;
        gap: 4px !important;
    }}
    div.stRadio > div[role="radiogroup"] > label {{
        flex: 1 !important;
        text-align: center !important;
        background: transparent !important;
        border-radius: 3px !important;
        padding: 6px 12px !important;
        color: #64748B !important;
        transition: all 0.2s ease !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        margin: 0 !important;
        border: none !important;
        cursor: pointer !important;
    }}
    div.stRadio > div[role="radiogroup"] > label:hover {{
        color: #E2E8F0 !important;
        background: rgba(255, 255, 255, 0.02) !important;
    }}
    div.stRadio > div[role="radiogroup"] div[data-checked="true"] {{
        background: {PRIMARY_COLOR} !important;
    }}
    div.stRadio > div[role="radiogroup"] div[data-checked="true"] span {{
        color: #0A0D12 !important;
        font-weight: 700 !important;
    }}

    /* Sharp Technical Tab-List Gating (folder tabs) */
    div[data-baseweb="tab-list"] {{
        background: #0E121A !important;
        border-radius: 0px !important;
        padding: 0px !important;
        border: none !important;
        border-bottom: 1px solid #1E293B !important;
        margin-bottom: 2rem !important;
        display: flex !important;
        justify-content: flex-start !important;
    }}
    button[data-baseweb="tab"] {{
        color: #64748B !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.05em !important;
        padding: 12px 24px !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        border-bottom: 1px solid #1E293B !important;
        border-radius: 0px !important;
        margin-right: 4px !important;
        margin-bottom: -1px !important;
        transition: all 0.15s ease-in-out !important;
    }}
    button[data-baseweb="tab"]:hover {{
        color: #94A3B8 !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {PRIMARY_COLOR} !important;
        background: #111622 !important;
        border: 1px solid #1E293B !important;
        border-bottom: 1px solid #111622 !important;
    }}

    /* Bounding Face Guide & Camera Overlay Scanline */
    .scanner-container {{
        position: relative !important;
        border: 1px solid #334155 !important;
        border-radius: 4px !important;
        overflow: hidden !important;
        background: #020617 !important;
    }}
    .scanner-container::before {{
        content: '' !important;
        position: absolute !important;
        width: 50% !important;
        height: 60% !important;
        border: 2px dashed rgba(6, 182, 212, 0.4) !important;
        border-radius: 50% !important;
        top: 50% !important;
        left: 50% !important;
        transform: translate(-50%, -50%) !important;
        z-index: 10 !important;
        pointer-events: none !important;
        box-shadow: 0 0 0 9999px rgba(11, 15, 25, 0.25) !important;
    }}
    .scanner-container::after {{
        content: '' !important;
        position: absolute !important;
        width: 100% !important;
        height: 2px !important;
        background: linear-gradient(90deg, transparent, {PRIMARY_COLOR}, transparent) !important;
        top: 0 !important;
        left: 0 !important;
        animation: scan 4s linear infinite !important;
        z-index: 11 !important;
    }}
    @keyframes scan {{
        0% {{ top: 0%; }}
        50% {{ top: 100%; }}
        100% {{ top: 0%; }}
    }}
    
    /* Live Capture Step Indicator */
    .step-indicator-bar {{
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        background: #0B0E14 !important;
        border: 1px solid #1E293B !important;
        border-radius: 4px !important;
        padding: 12px 16px !important;
        margin-bottom: 1.5rem !important;
    }}
    .step-indicator-bar .step-node {{
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        color: #475569 !important;
    }}
    .step-indicator-bar .step-node.active {{
        color: {PRIMARY_COLOR} !important;
    }}
    .step-indicator-bar .step-node.completed {{
        color: #10b981 !important;
    }}
    .step-indicator-bar .step-num {{
        font-size: 0.85rem !important;
        font-weight: 700 !important;
    }}
    .step-indicator-bar .step-label {{
        font-size: 0.6rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.05em !important;
        margin-top: 2px !important;
    }}
    .step-indicator-bar .step-line {{
        flex-grow: 1 !important;
        height: 1px !important;
        background: #1E293B !important;
        margin: 0 12px !important;
    }}
    
    /* Technical Capture Matrix Artifacts */
    .preview-box-empty {{
        width: 100%;
        height: 140px;
        background: #0B0E14;
        border: 1px dashed #1E293B;
        border-radius: 4px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }}
    .preview-box-empty .crosshair-indicator {{
        width: 24px;
        height: 24px;
        border: 1px solid #1E293B;
        border-radius: 50%;
        position: relative;
        margin-bottom: 8px;
    }}
    .preview-box-empty .crosshair-indicator::before {{
        content: '';
        position: absolute;
        width: 100%;
        height: 1px;
        background: #1E293B;
        top: 50%;
        left: 0;
    }}
    .preview-box-empty .crosshair-indicator::after {{
        content: '';
        position: absolute;
        height: 100%;
        width: 1px;
        background: #1E293B;
        left: 50%;
        top: 0;
    }}
    .preview-box-empty .mono-label {{
        font-size: 0.65rem;
        color: #475569;
        font-weight: 500;
        letter-spacing: 0.05em;
    }}
    .artifact-meta {{
        font-size: 0.65rem;
        color: #64748B;
        text-align: center;
        margin-top: 6px;
        letter-spacing: 0.05em;
    }}
    
    /* Interactive Clinical Buttons (no shadow/roundness) */
    div.stButton > button {{
        background: #0E121A !important;
        color: #F8FAFC !important;
        border: 1px solid #334155 !important;
        border-radius: 4px !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        letter-spacing: 0.02em !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
        width: 100% !important;
        box-shadow: none !important;
    }}
    div.stButton > button:hover {{
        background: #111622 !important;
        border-color: {PRIMARY_COLOR} !important;
        transform: none !important;
    }}
    div.stButton > button:active {{
        background: #1E293B !important;
    }}
    
    /* Diagnostic Telemetry Console */
    .diagnostic-console {{
        background: #0B0E14;
        border: 1px solid #1E293B;
        border-radius: 4px;
        padding: 16px;
        font-size: 0.75rem;
        margin-bottom: 1.5rem;
    }}
    .diagnostic-console .console-line {{
        margin-bottom: 8px;
        line-height: 1.4;
    }}
    .diagnostic-console .console-line:last-child {{
        margin-bottom: 0;
    }}
    .diagnostic-console .console-line.pending {{ color: #475569; }}
    .diagnostic-console .console-line.running {{ color: {PRIMARY_COLOR}; }}
    .diagnostic-console .console-line.passed {{ color: #10b981; }}
    .diagnostic-console .console-line.failed {{ color: #f43f5e; }}
    
    /* Asymmetrical Headings & Sections */
    .terminal-section-title {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        color: #64748B !important;
        letter-spacing: 0.08em !important;
        margin-top: 1.5rem !important;
        margin-bottom: 0.75rem !important;
        border-left: 2px solid #334155 !important;
        padding-left: 8px !important;
        text-transform: uppercase;
    }}
    .sidebar-brand {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.85rem !important;
        font-weight: 800 !important;
        color: #F8FAFC !important;
        letter-spacing: 0.12em !important;
        padding: 8px 0;
        text-align: left;
    }}
    .mono-section-title {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.65rem !important;
        font-weight: 700 !important;
        color: #475569 !important;
        letter-spacing: 0.08em !important;
        margin-bottom: 0.5rem !important;
    }}
    
    /* Forms & Text Input elements */
    div[data-baseweb="input"] {{
        background: #0E121A !important;
        border: 1px solid #1E293B !important;
        border-radius: 4px !important;
        color: #F8FAFC !important;
    }}
</style>
"""
