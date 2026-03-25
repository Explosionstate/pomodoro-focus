from pathlib import Path


def main() -> None:
    try:
        import PyInstaller.__main__ as pyinstaller
    except ImportError:
        raise SystemExit("未安装 PyInstaller，请先在 IDE 安装：pip install pyinstaller")

    root = Path(__file__).resolve().parent
    app_file = root / "web_shell.py"
    html_file = root / "index.html"
    add_data = f"{html_file};."

    pyinstaller.run(
        [
            str(app_file),
            "--name=PomodoroFocusWeb",
            "--onefile",
            "--windowed",
            "--clean",
            "--noconfirm",
            f"--add-data={add_data}",
        ]
    )

    dist_exe = root / "dist" / "PomodoroFocusWeb.exe"
    if dist_exe.exists():
        print(f"打包完成: {dist_exe}")
    else:
        print("打包流程结束，但未找到 exe，请检查打包日志。")


if __name__ == "__main__":
    main()
