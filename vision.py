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


_cache: dict[tuple[str, bool], np.ndarray] = {}


def template(name: str, color: bool = False) -> np.ndarray:
    key = (name, color)
    if key not in _cache:
        img = imread(TEMPLATE_DIR / f"{name}.png")
        _cache[key] = img if color else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return _cache[key]


def _prepare(img, name, box, margin, binary, color):
    """切出搜尋區域並把區域和模板轉成同一種格式。回傳 (區域, 模板, 區域左上角)。"""
    tpl = template(name, color)
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    sx1, sy1 = max(0, x1 - margin), max(0, y1 - margin)
    sx2, sy2 = min(w, x2 + margin), min(h, y2 + margin)
    region = img[sy1:sy2, sx1:sx2]
    if not color and region.ndim == 3:
        region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    if binary is not None:
        region, tpl = _binarize(region, binary), _binarize(tpl, binary)
    return region, tpl, (sx1, sy1)


def match_all(img, name: str, box, threshold: float = 0.85, color: bool = False,
              min_gap: int = 40) -> list[tuple[float, tuple[int, int]]]:
    """在 box 內找出所有分數 >= threshold 的位置（中心座標），由上到下排序。

    相鄰 min_gap 像素內只保留分數最高的一個。
    """
    region, tpl, (ox, oy) = _prepare(img, name, box, 0, None, color)
    res = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
    th, tw = tpl.shape[:2]
    ys, xs = np.where(res >= threshold)
    hits = sorted(((float(res[y, x]), (int(ox + x + tw // 2), int(oy + y + th // 2))) for y, x in zip(ys, xs)),
                  reverse=True)
    kept: list[tuple[float, tuple[int, int]]] = []
    for s, (cx, cy) in hits:
        if all(abs(cx - kx) > min_gap or abs(cy - ky) > min_gap for _, (kx, ky) in kept):
            kept.append((s, (cx, cy)))
    return sorted(kept, key=lambda k: k[1][1])


def _binarize(gray: np.ndarray, thresh: int) -> np.ndarray:
    return cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)[1]


def match(img, name: str, box, margin: int = 20, binary: int | None = None,
          color: bool = False) -> tuple[float, tuple[int, int]]:
    """在 box 附近（往外擴 margin）找模板，回傳 (最高分數, 模板中心座標)。

    box = (x1, y1, x2, y2) 搜尋中心區域，通常就是當初切模板的位置。
    binary: 給門檻值就先二值化（只留亮字），用在背景會隨關卡變的地方。
    color: 用彩色比對，用在形狀相同只差顏色的東西（例如四種果實）。
    """
    region, tpl, (ox, oy) = _prepare(img, name, box, margin, binary, color)
    res = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, (lx, ly) = cv2.minMaxLoc(res)
    th, tw = tpl.shape[:2]
    return float(score), (int(ox + lx + tw // 2), int(oy + ly + th // 2))
