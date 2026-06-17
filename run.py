from __future__ import annotations

import os
import sys
import subprocess
import signal
import time
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    
    # Verify environment variables
    # Load .env if it exists
    env_file = root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

    print("==========================================================")
    print("🧠 Starting Mental Health Agentic Chatbot Stack 🧠")
    print("==========================================================")
    
    processes = []
    
    def kill_all_processes(signum=None, frame=None):
        print("\nStopping all services...")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        print("All processes stopped. Exiting.")
        sys.exit(0)

    # Register signals for clean exit
    signal.signal(signal.SIGINT, kill_all_processes)
    signal.signal(signal.SIGTERM, kill_all_processes)

    # 1. Start FastAPI Backend (Port 8000)
    print("Launching Backend Server (FastAPI) on http://127.0.0.1:8000 ...")
    backend_cmd = [
        "python3.11", "-m", "uvicorn", "backend.main:app",
        "--host", "127.0.0.1", "--port", "8000"
    ]
    try:
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(backend_proc)
    except Exception as e:
        print(f"Failed to start FastAPI backend: {e}")
        sys.exit(1)

    # 2. Wait a brief moment for backend to initialize database
    time.sleep(2.5)

    # Check if backend crashed immediately
    if backend_proc.poll() is not None:
        print("FastAPI Backend failed to start. Logs:")
        out, _ = backend_proc.communicate()
        print(out)
        sys.exit(1)

    # 3. Start Streamlit Frontend (Port 8501)
    print("Launching Frontend App (Streamlit) on http://127.0.0.1:8501 ...")
    frontend_cmd = [
        "python3.11", "-m", "streamlit", "run", "frontend/app.py",
        "--server.port", "8501", "--server.address", "127.0.0.1"
    ]
    try:
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(frontend_proc)
    except Exception as e:
        print(f"Failed to start Streamlit frontend: {e}")
        kill_all_processes()
        sys.exit(1)

    print("\n==========================================================")
    print("🎉 Both servers launched successfully! 🎉")
    print("👉 Frontend: http://127.0.0.1:8501")
    print("👉 API Docs: http://127.0.0.1:8000/docs")
    print("👉 Press Ctrl+C to terminate both servers.")
    print("==========================================================\n")

    # Monitor subprocess logs asynchronously in a simple loop
    # We will print lines from both stdout streams if available
    os.set_blocking(backend_proc.stdout.fileno(), False)
    os.set_blocking(frontend_proc.stdout.fileno(), False)

    try:
        while True:
            # Check if any process has terminated
            if backend_proc.poll() is not None:
                print("Backend server crashed. Stopping stack.")
                break
            if frontend_proc.poll() is not None:
                print("Frontend server crashed. Stopping stack.")
                break

            # Read stdout lines from backend
            try:
                line = backend_proc.stdout.readline()
                if line:
                    print(f"[Backend] {line.strip()}")
            except Exception:
                pass

            # Read stdout lines from frontend
            try:
                line = frontend_proc.stdout.readline()
                if line:
                    print(f"[Frontend] {line.strip()}")
            except Exception:
                pass

            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        kill_all_processes()


if __name__ == "__main__":
    main()
