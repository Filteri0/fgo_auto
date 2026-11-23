"""從 assets/icon_source.png 產生程式圖示。換圖後重跑：uv run python make_icon.py

大尺寸（64 以上：Alt+Tab、檔案總管）用整張圖；
小尺寸（48 以下：標題列、工作列）用「頭 + 角」的裁切，縮小後角色還認得出來。

產出：
    assets/icon_large.png   整張圖 512px（介面用）
    assets/icon_small.png   頭 + 角 256px（介面用）
    assets/app.ico          多尺寸 .ico（之後打包 exe 用），各尺寸挑對應的圖
"""
import struct
from pathlib import Path

import cv2
import numpy as np

from vision import imread, imwrite

ASSETS = Path(__file__).parent / "assets"
SMALL_SIZES = (16, 20, 24, 32, 40, 48)
LARGE_SIZES = (64, 128, 256)
# 頭 + 角的裁切（相對原圖的比例）：水平置中寬 60%，從上面 6% 開始，正方形不變形
CROP_X, CROP_Y, CROP_W = 0.20, 0.06, 0.60


def head_crop(src: np.ndarray) -> np.ndarray:
    h, w = src.shape[:2]
    side = int(w * CROP_W)
    x, y = int(w * CROP_X), int(h * CROP_Y)
    return src[y:y + side, x:x + side]


def resize(img: np.ndarray, size: int) -> np.ndarray:
    return cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)


def write_ico(path: Path, images: list[np.ndarray]) -> None:
    """寫多尺寸 .ico（每個尺寸存成 PNG，Windows Vista 以後都支援）。"""
    blobs = [cv2.imencode(".png", img)[1].tobytes() for img in images]
    offset = 6 + 16 * len(blobs)
    header = struct.pack("<HHH", 0, 1, len(blobs))
    entries = b""
    for img, blob in zip(images, blobs):
        size = img.shape[0]
        dim = 0 if size >= 256 else size  # 256 在 .ico 裡記成 0
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    path.write_bytes(header + entries + b"".join(blobs))


def build() -> None:
    src = imread(ASSETS / "icon_source.png")
    if src.shape[0] != src.shape[1]:
        raise ValueError(f"原圖要是正方形，現在是 {src.shape[1]}x{src.shape[0]}")
    head = head_crop(src)
    imwrite(ASSETS / "icon_large.png", resize(src, 512))
    imwrite(ASSETS / "icon_small.png", resize(head, 256))
    images = [resize(head, s) for s in SMALL_SIZES] + [resize(src, s) for s in LARGE_SIZES]
    write_ico(ASSETS / "app.ico", images)
    print("已產生 icon_large.png、icon_small.png、app.ico（" + "、".join(str(i.shape[0]) for i in images) + "）")


if __name__ == "__main__":
    build()
