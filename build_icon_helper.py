from __future__ import annotations

from pathlib import Path


def build_icon_from_dist_jpeg(root: Path) -> Path | None:
    jpeg_path = root / "dist" / "tomato.jpeg"
    if not jpeg_path.exists():
        print(f"未找到图标源文件: {jpeg_path}，将使用默认图标。")
        return None

    ico_path = root / "dist" / "tomato.ico"

    if ico_path.exists() and ico_path.stat().st_mtime >= jpeg_path.stat().st_mtime:
        return ico_path

    try:
        from PIL import Image
    except ImportError:
        print("未安装 Pillow，无法将 dist/tomato.jpeg 转为 ico，将使用默认图标。")
        return None

    with Image.open(jpeg_path) as img:
        img = img.convert("RGBA")
        img.save(
            ico_path,
            format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
        )

    print(f"已生成图标: {ico_path}")
    return ico_path
