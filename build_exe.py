from pathlib import Path

from build_icon_helper import build_icon_from_dist_jpeg


def main() -> None:
    try:
        import PyInstaller.__main__ as pyinstaller
    except ImportError:
        raise SystemExit(
            "未安装 PyInstaller。请先在 IDE 安装依赖：pip install pyinstaller"
        )

    root = Path(__file__).resolve().parent
    app_file = root / "run_pomodoro.py"

    exe_name = "PomodoroFocus"
    icon_path = build_icon_from_dist_jpeg(root)

    args = [
        str(app_file),
        f"--name={exe_name}",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
    ]
    if icon_path is not None:
        args.append(f"--icon={icon_path}")

    pyinstaller.run(args)

    dist_exe = root / "dist" / f"{exe_name}.exe"
    if dist_exe.exists():
        print(f"打包完成: {dist_exe}")
    else:
        print("打包流程结束，但未找到 exe，请检查打包日志。")


if __name__ == "__main__":
    main()
