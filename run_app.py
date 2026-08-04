"""
run_app.py

Unified Application Launcher
Launches both the FastAPI backend server (uvicorn) and the Streamlit frontend
dashboard concurrently in separate subprocesses. Manages key environment variables
and handles graceful shutdown on Ctrl+C.
"""
import os
import sys
import subprocess
import time
import signal

# Default credentials for local demonstration
DEFAULT_ENCRYPTION_KEY = "G5F1yYt4-6R6pW_nZ6t01vT1gQ15yV2uT3r4_n5m6t0="
DEFAULT_API_KEY = "test_developer_api_key_123"

def main():
    print("=" * 80)
    print("SECURE FACE FRAMEWORK — UNIFIED APPLICATION LAUNCHER")
    print("=" * 80)

    # Initialize environment variables
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    
    if not env.get("FACE_DB_ENCRYPTION_KEY"):
        print(f"[Launcher] Setting default database encryption key: {DEFAULT_ENCRYPTION_KEY}")
        env["FACE_DB_ENCRYPTION_KEY"] = DEFAULT_ENCRYPTION_KEY
        
    if not env.get("FACE_API_KEY"):
        print(f"[Launcher] Setting default developer API key: {DEFAULT_API_KEY}")
        env["FACE_API_KEY"] = DEFAULT_API_KEY

    # Detect python executable in venv
    python_exe = sys.executable
    print(f"[Launcher] Using Python executable: {python_exe}")

    # 1. Start FastAPI backend (uvicorn)
    backend_cmd = [
        python_exe, "-m", "uvicorn", "api.api:app",
        "--host", "127.0.0.1",
        "--port", "8000",
        "--log-level", "info"
    ]
    print("[Launcher] Starting FastAPI backend on http://127.0.0.1:8000 ...")
    backend_proc = subprocess.Popen(
        backend_cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Wait a moment for the backend to bind to the port
    time.sleep(2)

    # 2. Start Streamlit frontend
    frontend_cmd = [
        python_exe, "-m", "streamlit", "run", "app/streamlit_app.py",
        "--server.port", "8501",
        "--server.address", "127.0.0.1"
    ]
    print("[Launcher] Starting Streamlit frontend on http://127.0.0.1:8501 ...")
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        env=env
    )

    print("\n[Launcher] System successfully initialized! Open your browser at http://127.0.0.1:8501")
    print("[Launcher] Press Ctrl+C in this terminal to shut down both applications cleanly.\n")

    # Monitor processes
    try:
        while True:
            # Check if backend crashed
            backend_poll = backend_proc.poll()
            if backend_poll is not None:
                print(f"[Launcher] Error: FastAPI backend exited unexpectedly with code {backend_poll}")
                # Print some backend stdout/stderr log
                if backend_proc.stdout:
                    print("--- Backend Log output ---")
                    print("".join(backend_proc.stdout.readlines()[-20:]))
                break
                
            # Check if frontend crashed
            frontend_poll = frontend_proc.poll()
            if frontend_poll is not None:
                print(f"[Launcher] Error: Streamlit frontend exited unexpectedly with code {frontend_poll}")
                break
                
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[Launcher] Received shutdown signal (Ctrl+C). Terminating applications...")
        
    finally:
        # Graceful shutdown
        print("[Launcher] Stopping Streamlit dashboard...")
        try:
            frontend_proc.terminate()
            frontend_proc.wait(timeout=5)
        except Exception:
            try:
                frontend_proc.kill()
            except Exception:
                pass

        print("[Launcher] Stopping FastAPI backend...")
        try:
            backend_proc.terminate()
            backend_proc.wait(timeout=5)
        except Exception:
            try:
                backend_proc.kill()
            except Exception:
                pass

        print("[Launcher] Shutdown complete. Goodbye!")

if __name__ == "__main__":
    main()
