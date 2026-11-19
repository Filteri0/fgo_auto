"""支援列表：找出每一列，切出各欄位，依條件比對。

每一列用「從者」這個固定標籤定位，其他欄位都是相對於標籤中心的固定偏移。
欄位（1280x720，相對「從者」標籤中心）：
    player   玩家名稱
    servant  從者名稱
    np       寶具那一行（寶具名稱 + 寶具等級，所以也隱含了從者）
    level    從者等級（例如 Lv.120/120）
    ce       禮裝圖示
    mlb      禮裝右下角的滿破標記
"""
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from vision import imread, imwrite, template

LIST_BOX = (200, 170, 340, 720)       # 「從者」標籤會出現的直條
ROW_TOP, ROW_BOTTOM = -113, 67        # 一列相對標籤中心的上下緣
SCREEN_H = 720
FIELDS: dict[str, tuple[int, int, int, int]] = {
    "player":  (-38, -108, 284, -69),
    "servant": (82, -15, 484, 15),
    "np":      (59, 21, 524, 51),
    "level":   (-196, -103, -70, -77),
    "ce":      (-186, 21, -96, 51),
    "mlb":     (-98, 35, -72, 61),
}
FIELD_ZH = {"player": "玩家名稱", "servant": "從者", "np": "寶具（含等級）",
            "level": "從者等級", "ce": "禮裝", "mlb": "禮裝滿破"}
MATCH_MARGIN = 6
THRESHOLD = 0.85
LABEL_THRESHOLD = 0.9  # 「寶具」標籤跟「從者」長得像，門檻要高一點


def field_box(row: tuple[int, int], name: str) -> tuple[int, int, int, int]:
    cx, cy = row
    x1, y1, x2, y2 = FIELDS[name]
    return cx + x1, cy + y1, cx + x2, cy + y2


def crop_field(img, row, name) -> np.ndarray:
    x1, y1, x2, y2 = field_box(row, name)
    return img[y1:y2, x1:x2].copy()


def find_rows(img, fully_visible: bool = True) -> list[tuple[int, int]]:
    """回傳每一列「從者」標籤的中心座標，由上到下。fully_visible = 只要整列都在畫面內的。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    x1, y1, x2, y2 = LIST_BOX
    tpl = template("support_row_label")
    res = cv2.matchTemplate(gray[y1:y2, x1:x2], tpl, cv2.TM_CCOEFF_NORMED)
    th, tw = tpl.shape
    hits = sorted(((float(res[y, x]), (x1 + x + tw // 2, y1 + y + th // 2))
                   for y, x in zip(*np.where(res >= LABEL_THRESHOLD))), reverse=True)
    rows: list[tuple[int, int]] = []
    for _, (cx, cy) in hits:
        if all(abs(cy - ry) > 60 for _, ry in rows):
            rows.append((int(cx), int(cy)))
    if fully_visible:
        rows = [r for r in rows if r[1] + ROW_TOP >= y1 and r[1] + ROW_BOTTOM <= SCREEN_H - 2]
    return sorted(rows, key=lambda r: r[1])


def any_row_cut_off(img) -> bool:
    """畫面最下面有沒有只露出一半的列（還要再捲）。"""
    return len(find_rows(img, fully_visible=False)) > len(find_rows(img))


@dataclass
class SupportSpec:
    """指定助戰的條件：有放模板的欄位才比對。"""
    templates: dict[str, np.ndarray] = field(default_factory=dict)  # 欄位名 → BGR 圖
    mlb: bool = False                 # 禮裝要滿破（用內建的滿破標記模板）
    class_tab: str | None = "berserker"

    def describe(self) -> str:
        parts = [FIELD_ZH[k] for k in self.templates]
        if self.mlb:
            parts.append(FIELD_ZH["mlb"])
        return "、".join(parts) or "（沒有條件：選第一個）"

    # ---- 存讀 ----
    def save(self, folder: Path) -> dict:
        folder.mkdir(parents=True, exist_ok=True)
        files = {}
        for k, img in self.templates.items():
            name = f"support_{k}.png"
            imwrite(folder / name, img)
            files[k] = name
        return {"fields": files, "mlb": self.mlb, "class_tab": self.class_tab or ""}

    @classmethod
    def load(cls, folder: Path, data: dict) -> "SupportSpec":
        tpls = {k: imread(folder / f) for k, f in data.get("fields", {}).items() if k in FIELDS and k != "mlb"}
        return cls(tpls, bool(data.get("mlb", False)), data.get("class_tab") or None)


LEVEL_BINARY = 190  # 等級文字疊在從者頭像上：只留白字比對，換頭像也不受影響


def _white(bgr) -> np.ndarray:
    return cv2.threshold(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), LEVEL_BINARY, 255, cv2.THRESH_BINARY)[1]


def _score(img, row, name, tpl) -> float:
    x1, y1, x2, y2 = field_box(row, name)
    m = MATCH_MARGIN
    region = img[max(0, y1 - m):y2 + m, max(0, x1 - m):x2 + m]
    if region.shape[0] < tpl.shape[0] or region.shape[1] < tpl.shape[1]:
        return 0.0
    if name == "level":
        region, tpl = _white(region), _white(tpl)
    res = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
    return float(np.nan_to_num(res).max())


def _star_mask(bgr) -> np.ndarray:
    """滿破星星是黃（上半）到綠（下半）的亮色：只留這些像素，背景的禮裝圖案就不會干擾比對。"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return (((h >= 18) & (h <= 95) & (s >= 80) & (v >= 190)) * 255).astype(np.uint8)


MLB_MARGIN = 10       # 不同列的星星位置會差幾個像素
MLB_MARGIN_DOWN = 24  # 實機：有些列的禮裝區比較高，星星低了約 14 像素


def mlb_score(img, row) -> float:
    x1, y1, x2, y2 = field_box(row, "mlb")
    # 右邊不擴張：禮裝的金色外框就在右側，也是黃色
    region = _star_mask(img[y1 - MLB_MARGIN:y2 + MLB_MARGIN_DOWN, x1 - MLB_MARGIN:x2 + 2])
    tpl = _star_mask(template("support_mlb_star", color=True))
    if region.max() == 0:
        return 0.0
    res = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
    return float(np.nan_to_num(res).max())


def row_scores(img, row, spec: SupportSpec) -> dict[str, float]:
    scores = {k: _score(img, row, k, t) for k, t in spec.templates.items()}
    if spec.mlb:
        scores["mlb"] = mlb_score(img, row)
    return scores


MLB_THRESHOLD = 0.75  # 實機：滿破 0.88~1.00、沒滿破 0.59、沒裝禮裝 0.05


def row_matches(img, row, spec: SupportSpec) -> bool:
    return all(s >= (MLB_THRESHOLD if k == "mlb" else THRESHOLD)
               for k, s in row_scores(img, row, spec).items())


def tap_point(row) -> tuple[int, int]:
    """點這一列的從者名稱區（點頭像會打開詳細資訊）。"""
    cx, cy = row
    return cx + 150, cy
