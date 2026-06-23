"""Launch the Seattle Regulatory RAG server and open the chat UI in a browser.

Usage:
    cd /path/to/project
    .venv/bin/python scripts/start.py

Press Ctrl+C or close the terminal to stop the server.
"""

import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_URL = "http://localhost:8000"
HEALTH_URL = f"{SERVER_URL}/api/health"


def _server_ready(timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def main() -> None:
    # If server already up (e.g. left running from a previous session), just open the browser.
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1) as r:
            if r.status == 200:
                print(f"Server already running. Opening {SERVER_URL} ...")
                webbrowser.open(SERVER_URL)
                return
    except Exception:
        pass

    # Start server as a subprocess.
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "src.server.app:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--log-level", "warning",  # quiet — errors only
        ],
        cwd=str(PROJECT_ROOT),
    )

    def _shutdown(signum=None, frame=None):
        print("\nStopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Wait for the server to accept connections.
    print("Starting server...", end="", flush=True)
    if not _server_ready(timeout=30):
        print(" timed out. Check for errors above.")
        _shutdown()

    print(f" ready.  Opening {SERVER_URL} ...")
    webbrowser.open(SERVER_URL)
    print("Press Ctrl+C to stop.\n")

    try:
        proc.wait()  # block until the server process exits on its own
    except KeyboardInterrupt:
        _shutdown()


if __name__ == "__main__":
    main()
