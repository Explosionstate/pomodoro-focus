from __future__ import annotations

import sys
from pathlib import Path

import webview
from plyer import notification


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


class NativeApi:
    def request_notification(self) -> dict:
        try:
            notification.notify(
                title="番茄聚焦",
                message="桌面提醒已开启，番茄结束会在右下角提醒。",
                app_name="Pomodoro Focus",
                timeout=4,
            )
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def notify(self, title: str, message: str) -> dict:
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Pomodoro Focus",
                timeout=6,
            )
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def main() -> None:
    page = app_root() / "index.html"
    if not page.exists():
        raise SystemExit(f"未找到页面文件: {page}")

    webview.create_window(
        title="番茄聚焦",
        url=page.as_uri(),
        width=1160,
        height=820,
        min_size=(980, 700),
        js_api=NativeApi(),
    )
    webview.start()


if __name__ == "__main__":
    main()
