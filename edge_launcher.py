from __future__ import annotations

import os
import socket
import subprocess
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time


PORT = 38765


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


class SilentHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args) -> None:
        return


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def serve() -> None:
    root = app_root()
    handler = partial(SilentHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    server.serve_forever()


def launch_server_in_thread() -> None:
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    for _ in range(25):
        if port_open(PORT):
            return
        time.sleep(0.15)


def open_edge(url: str) -> None:
    try:
        os.startfile(f"microsoft-edge:{url}")
        return
    except Exception:
        pass

    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("ProgramFiles", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
    ]
    for path in candidates:
        if path.exists():
            subprocess.Popen([str(path), url], close_fds=True)
            return

    import webbrowser

    webbrowser.open(url)


def main() -> None:
    url = f"http://127.0.0.1:{PORT}/index.html"
    if port_open(PORT):
        open_edge(url)
        return

    launch_server_in_thread()
    open_edge(url)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
