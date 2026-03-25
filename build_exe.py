from pathlib import Path


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

    pyinstaller.run(
        [
            str(app_file),
            f"--name={exe_name}",
            "--onefile",
            "--windowed",
            "--clean",
            "--noconfirm",
        ]
    )

    dist_exe = root / "dist" / f"{exe_name}.exe"
    if dist_exe.exists():
        print(f"打包完成: {dist_exe}")
    else:
        print("打包流程结束，但未找到 exe，请检查打包日志。")


if __name__ == "__main__":
    main()
