"""影像工具：讀寫圖檔（支援中文路徑）與模板比對。座標一律以 1280x720 為準。"""
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).parent
TEMPLATE_DIR = ROOT / "templates"


def imread(path) -> np.ndarray:
    # cv2.imread 在 Windows 不吃中文路徑，改用 imdecode
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)
    return img


def imwrite(path, img) -> None:
    Path(path).write_bytes(cv2.imencode(".png", img)[1].tobytes())


_cache: dict[str, np.ndarray] = {}


def template(name: str) -> np.ndarray:
    if name not in _cache:
        _cache[name] = cv2.cvtColor(imread(TEMPLATE_DIR / f"{name}.png"), cv2.COLOR_BGR2GRAY)
    return _cache[name]


def _binarize(gray: np.ndarray, thresh: int) -> np.ndarray:
    return cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)[1]


def match(img, name: str, box, margin: int = 20, binary: int | None = None) -> tuple[float, tuple[int, int]]:
    """在 box 附近（往外擴 margin）找模板，回傳 (分數, 模板中心座標)。

    box = (x1, y1, x2, y2)，也就是當初切模板的位置。
    binary: 給門檻值就先二值化（只留亮字），用在背景會隨關卡變的地方。
    """
    tpl = template(name)
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    sx1, sy1 = max(0, x1 - margin), max(0, y1 - margin)
    sx2, sy2 = min(w, x2 + margin), min(h, y2 + margin)
    region = img[sy1:sy2, sx1:sx2]
    if region.ndim == 3:
        region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    if binary is not None:
        region, tpl = _binarize(region, binary), _binarize(tpl, binary)
    res = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, (lx, ly) = cv2.minMaxLoc(res)
    th, tw = tpl.shape[:2]
    return float(score), (sx1 + lx + tw // 2, sy1 + ly + th // 2)
