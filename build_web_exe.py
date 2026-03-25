from pathlib import Path

from build_icon_helper import build_icon_from_dist_jpeg


def main() -> None:
    try:
        import PyInstaller.__main__ as pyinstaller
    except ImportError:
        raise SystemExit("未安装 PyInstaller，请先在 IDE 安装：pip install pyinstaller")

    root = Path(__file__).resolve().parent
    app_file = root / "web_shell.py"
    html_file = root / "index.html"
    add_data = f"{html_file};."
    icon_path = build_icon_from_dist_jpeg(root)

    args = [
        str(app_file),
        "--name=PomodoroFocusWeb",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        f"--add-data={add_data}",
    ]
    if icon_path is not None:
        args.append(f"--icon={icon_path}")

    pyinstaller.run(args)

    dist_exe = root / "dist" / "PomodoroFocusWeb.exe"
    if dist_exe.exists():
        print(f"打包完成: {dist_exe}")
    else:
        print("打包流程结束，但未找到 exe，请检查打包日志。")


if __name__ == "__main__":
    main()
