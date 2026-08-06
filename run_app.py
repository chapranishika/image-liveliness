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
import urllib.request
import urllib.error

from src.keys import load_env_file


def warm_up_frontend(url="http://127.0.0.1:8501", timeout_seconds=45):
    """
    The Streamlit script's first execution in a fresh process pays a one-time
    ~10-15s cost importing TensorFlow/DeepFace/MediaPipe (confirmed via direct
    timing instrumentation: import-cache reruns after the first are near
    instant). A plain HTTP GET is enough to trigger that first script
    execution server-side. Firing one here, before printing "ready", means
    the real user's first browser load never pays that cost -- the launcher
    absorbs it instead of a live camera session doing so.
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=5)
            return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(1)
    return False


def kill_processes_on_ports(ports=[8000, 8501]):
    """
    Self-healing utility to scan local ports and terminate any orphaned
    processes, preventing bind exceptions on subsequent launches.
    """
    import re
    for port in ports:
        try:
            output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True).decode()
            pids = set()
            for line in output.strip().split("\n"):
                if "LISTENING" in line or "ESTABLISHED" in line:
                    parts = re.split(r'\s+', line.strip())
                    if len(parts) >= 5:
                        pids.add(parts[-1])
            for pid in pids:
                if pid != "0" and pid.isdigit():
                    print(f"[Launcher] Port {port} is occupied by PID {pid}. Terminating process...")
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def main():
    # Redirected output (e.g. via Start-Process) is fully buffered by default,
    # which delays every print below until process exit -- reconfigure so
    # progress is visible in real time whether run interactively or piped.
    sys.stdout.reconfigure(line_buffering=True)
    print("=" * 80)
    print("SECURE FACE FRAMEWORK — UNIFIED APPLICATION LAUNCHER")
    print("=" * 80)
    
    # Self-healing: clean up ports 8000 and 8501
    kill_processes_on_ports([8000, 8501])

    # Load local environment variables from .env
    load_env_file()

    # Verify required environment variables are set
    missing_vars = []
    if not os.environ.get("FACE_DB_ENCRYPTION_KEY"):
        missing_vars.append("FACE_DB_ENCRYPTION_KEY")
    if not os.environ.get("FACE_API_KEY"):
        missing_vars.append("FACE_API_KEY")

    if missing_vars:
        print(f"\n[Error] Required environment variable(s) not set: {', '.join(missing_vars)}")
        print("\nPlease configure these variables in a local '.env' file in the project root.")
        print("You can copy '.env.example' to '.env' and populate it with new secure keys:")
        print("  1. Generate a new database encryption key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        print("  2. Generate a new API key: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        print("\nDO NOT commit '.env' to git history.")
        sys.exit(1)

    env = os.environ.copy()
    env["PYTHONPATH"] = "."

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
    backend_log = open("backend_server.log", "w", encoding="utf-8", buffering=1)
    backend_proc = subprocess.Popen(
        backend_cmd,
        env=env,
        stdout=backend_log,
        stderr=subprocess.STDOUT
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

    print("[Launcher] Warming up ML models (one-time cost, ~10-15s) so your first page load is instant...")
    warmed = warm_up_frontend()
    if warmed:
        print("[Launcher] Warm-up complete.")
    else:
        print("[Launcher] Warm-up did not confirm in time -- the app will still work, first load may be slower.")

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
                try:
                    with open("backend_server.log", "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        print("--- Backend Log output ---")
                        print("".join(lines[-20:]))
                except Exception:
                    pass
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

        try:
            backend_log.close()
        except Exception:
            pass

        print("[Launcher] Shutdown complete. Goodbye!")

if __name__ == "__main__":
    main()
