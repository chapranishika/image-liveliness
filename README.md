# Secure Face Registration and Verification Framework

This repository implements a secure, modular face registration and verification pipeline with integrated quality assessment and liveness detection.

## Project Structure

```
.
├── .gitignore
├── requirements.txt
├── setup_folders.py          # Script to establish project directory layout
├── sanity_check.py           # Verification script for environment dependencies
├── capture_images.py         # Webcam capture tool with integrated face detector
├── download_datasets.py      # Downloads CFP and CelebA-Spoof development datasets
├── src/
│   ├── __init__.py
│   ├── quality_checks.py     # Real-time brightness and blur quality checks
│   ├── liveness_passive.py   # Placeholder for passive liveness checks
│   ├── liveness_active.py    # Placeholder for active liveness checks
│   ├── rppg.py               # Placeholder for remote photoplethysmography
│   ├── face_matching.py      # Placeholder for face verification engine
│   ├── pipeline.py           # Coordinator pipeline
│   └── db.py                 # Face enrollment database interface
├── api/
│   ├── __init__.py
│   └── api.py                # FastAPI endpoints
├── app/
│   └── streamlit_app.py      # Streamlit demonstration dashboard
├── data/
│   ├── celeba_spoof_sample/  # Curated CelebA-Spoof development sample
│   ├── cfp_sample/           # Curated CFP identity verification sample
│   └── self_collected/       # User self-collected dataset
├── logs/
│   ├── capture_log.csv       # Event log of self-collected frames
│   └── session_summary.json  # Aggregated counts per capture session
└── README.md
```

## Setup & Running

### 1. Create Virtual Environment and Install Libraries
Ensure you are using **Python 3.11** or **3.10**:
```bash
# Create virtual environment
py -3.11 -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 2. Establish Folders and Run Sanity Check
```bash
# Initialize folders
python setup_folders.py

# Verify environment imports, webcam accessibility, and model initialization
python sanity_check.py
```

### 3. Self-Data Collection
To collect your own facial pictures for testing under multiple sessions:
```bash
python capture_images.py --session 1
```
Use the following keys on the preview window:
- **`F`**: Frontal pose (requires exactly 1 face).
- **`L`**: Left pose (15–35° yaw).
- **`R`**: Right pose (15–35° yaw).
- **`B`**: Bad Quality capture (opens terminal submenu to select category: Too Dark, Overexposed, Blur, Extreme Angle, Occlusion).
- **`A`**: Attack Sample capture (opens terminal submenu to select type: Printed Photo, Screen Replay, Video Replay, Frozen Frame, Multiple Faces).
- **`Q`**: Exit and output session summary.

All events are logged to [logs/capture_log.csv](file:///E:/Projects/ML%20liveliness/logs/capture_log.csv) and [logs/session_summary.json](file:///E:/Projects/ML%20liveliness/logs/session_summary.json).
