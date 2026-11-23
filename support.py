"""支援列表：找出每一列，切出各欄位，依條件比對（文字用 OCR，禮裝用圖片）。

每一列用「從者」這個固定標籤定位，其他欄位是相對於標籤中心的偏移。
一列有兩種版型：玩家有寫個人簡介時，名字下面多一行簡介；沒寫的列名字會往下 26 像素、
頭像區（等級、禮裝、滿破）往下 14 像素。版型用名字右邊的玩家「Lv.」位置判斷。
欄位（1280x720，相對「從者」標籤中心，以「有簡介」版型為準）：
    player   玩家名稱
    servant  從者名稱
    np       寶具那一行（寶具名稱 + 寶具等級，所以也隱含了從者）
    level    從者等級（例如 Lv.120/120）
    ce       禮裝圖示
    mlb      禮裝右下角的滿破標記
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

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

# 版型判斷：名字右邊玩家「Lv.」相對標籤的 y（實機量測：有簡介 -98、沒簡介 -72）
MASTER_LV_X = (720, 775)
MASTER_LV_Y = (-115, -45)   # 「Lv.」高 18 像素，沒簡介時頂端在 -72，要包到 -54 以下
NO_COMMENT_SPLIT = -85              # 比這個低（數值大）= 沒有簡介
PLAYER_SHIFT, PORTRAIT_SHIFT = 26, 14
PORTRAIT_FIELDS = ("level", "ce", "mlb")


class Row(NamedTuple):
    """一列助戰：「從者」標籤中心 + 版型造成的偏移。可以當 (x, y) 用：row[0]、row[1]。"""
    x: int
    y: int
    player_dy: int = 0     # 沒有簡介時名字往下移
    portrait_dy: int = 0   # 沒有簡介時頭像區往下移

    @property
    def has_comment(self) -> bool:
        return self.player_dy == 0


def field_box(row, name: str) -> tuple[int, int, int, int]:
    cx, cy = row[0], row[1]
    dy = 0
    if isinstance(row, Row):
        dy = row.player_dy if name == "player" else row.portrait_dy if name in PORTRAIT_FIELDS else 0
    x1, y1, x2, y2 = FIELDS[name]
    return cx + x1, cy + y1 + dy, cx + x2, cy + y2 + dy


def _layout(img, cx: int, cy: int) -> Row:
    x1, x2 = MASTER_LV_X
    y1, y2 = max(0, cy + MASTER_LV_Y[0]), cy + MASTER_LV_Y[1]
    region = img[y1:y2, x1:x2]
    # 用彩色比對：金色「Lv.」在淺色底上，轉灰階後幾乎沒有對比（實機灰階只有 0.47 分）
    tpl = template("support_master_lv", color=True)
    if region.shape[0] < tpl.shape[0]:
        return Row(cx, cy)
    res = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, (_, ly) = cv2.minMaxLoc(res)
    rel = y1 + ly - cy
    if score >= 0.8 and rel > NO_COMMENT_SPLIT:
        return Row(cx, cy, PLAYER_SHIFT, PORTRAIT_SHIFT)
    return Row(cx, cy)


def crop_field(img, row, name) -> np.ndarray:
    x1, y1, x2, y2 = field_box(row, name)
    return img[y1:y2, x1:x2].copy()


def find_rows(img, fully_visible: bool = True) -> list[Row]:
    """回傳每一列（「從者」標籤中心 + 版型），由上到下。fully_visible = 只要整列都在畫面內的。"""
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
    return [_layout(img, cx, cy) for cx, cy in sorted(rows, key=lambda r: r[1])]


def any_row_cut_off(img) -> bool:
    """畫面最下面有沒有只露出一半的列（還要再捲）。"""
    return len(find_rows(img, fully_visible=False)) > len(find_rows(img))


@dataclass
class SupportSpec:
    """指定助戰的條件。文字類用 OCR 讀（不受頭像背景影響），禮裝用圖片比對（禮裝圖上沒有字）。

    空字串 / 0 / None = 不限這個條件。
    """
    player: str = ""                  # 玩家名稱
    servant: str = ""                 # 從者名稱
    min_level: int = 0                # 從者等級至少
    min_np: int = 0                   # 寶具等級至少
    ce: np.ndarray | None = None      # 禮裝圖（從支援列表切下來的）
    mlb: bool = False                 # 禮裝要滿破
    class_tab: str | None = "berserker"

    def describe(self) -> str:
        parts = []
        if self.player:
            parts.append(f"玩家 {self.player}")
        if self.servant:
            parts.append(f"從者 {self.servant}")
        if self.min_level:
            parts.append(f"等級 ≥ {self.min_level}")
        if self.min_np:
            parts.append(f"寶具 ≥ Lv.{self.min_np}")
        if self.ce is not None:
            parts.append("指定禮裝")
        if self.mlb:
            parts.append("禮裝滿破")
        return "、".join(parts) or "（沒有條件：選第一個）"

    # ---- 存讀 ----
    def save(self, folder: Path) -> dict:
        folder.mkdir(parents=True, exist_ok=True)
        ce_file = ""
        if self.ce is not None:
            ce_file = "support_ce.png"
            imwrite(folder / ce_file, self.ce)
        return {"player": self.player, "servant": self.servant, "min_level": self.min_level,
                "min_np": self.min_np, "ce": ce_file, "mlb": self.mlb, "class_tab": self.class_tab or ""}

    @classmethod
    def load(cls, folder: Path, data: dict) -> "SupportSpec":
        spec = cls(
            player=str(data.get("player", "")), servant=str(data.get("servant", "")),
            min_level=int(data.get("min_level", 0) or 0), min_np=int(data.get("min_np", 0) or 0),
            ce=imread(folder / data["ce"]) if data.get("ce") else None,
            mlb=bool(data.get("mlb", False)), class_tab=data.get("class_tab") or None,
        )
        old = data.get("fields")  # 舊格式：每個欄位存一張圖 → 用 OCR 讀成文字 / 數字
        if old:
            import ocr

            def img(k):
                return imread(folder / old[k])
            if "player" in old:
                spec.player = ocr.read(img("player")).strip(" ，,")
            if "servant" in old:
                spec.servant = ocr.read(img("servant")).strip()
            if "level" in old:
                spec.min_level = ocr.parse_level(ocr.read(img("level"))) or 0
            if "np" in old:
                spec.min_np = ocr.parse_np_level(ocr.read(img("np"))) or 0
            if "ce" in old:
                spec.ce = img("ce")
        return spec


def _score(img, row, name, tpl) -> float:
    x1, y1, x2, y2 = field_box(row, name)
    m = MATCH_MARGIN
    region = img[max(0, y1 - m):y2 + m, max(0, x1 - m):x2 + m]
    if region.shape[0] < tpl.shape[0] or region.shape[1] < tpl.shape[1]:
        return 0.0
    res = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
    return float(np.nan_to_num(res).max())


def _star_mask(bgr) -> np.ndarray:
    """滿破星星是黃（上半）到綠（下半）的亮色：只留這些像素，背景的禮裝圖案就不會干擾比對。"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return (((h >= 18) & (h <= 95) & (s >= 80) & (v >= 190)) * 255).astype(np.uint8)


MLB_MARGIN = 10       # 不同列的星星位置會差幾個像素
MLB_MARGIN_DOWN = 10  # 星星低 14 像素其實是「沒有簡介」版型，已由 Row.portrait_dy 處理


def mlb_score(img, row) -> float:
    x1, y1, x2, y2 = field_box(row, "mlb")
    # 右邊不擴張：禮裝的金色外框就在右側，也是黃色
    region = _star_mask(img[y1 - MLB_MARGIN:y2 + MLB_MARGIN_DOWN, x1 - MLB_MARGIN:x2 + 2])
    tpl = _star_mask(template("support_mlb_star", color=True))
    if region.max() == 0:
        return 0.0
    res = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
    return float(np.nan_to_num(res).max())


MLB_THRESHOLD = 0.45  # 實機（版型修正後）：滿破 0.66~1.00、沒滿破 0.14、沒裝禮裝 0.05


def read_row(img, row) -> dict:
    """OCR 讀出一列的文字欄位（介面點選一列時用來自動填條件）。"""
    import ocr
    np_text = ocr.read(crop_field(img, row, "np"))
    level_text = ocr.read(crop_field(img, row, "level"))
    return {
        "player": ocr.read(crop_field(img, row, "player")).strip(" ，,"),
        "servant": ocr.read(crop_field(img, row, "servant")).strip(),
        "level": ocr.parse_level(level_text), "np": ocr.parse_np_level(np_text),
        "np_text": np_text, "level_text": level_text,
    }


def check_row(img, row, spec: SupportSpec, stop_early: bool = True) -> list[tuple[str, bool, str]]:
    """逐項檢查條件，回傳 [(條件名稱, 是否符合, 讀到的值)]。

    stop_early：遇到第一個不符就停（Bot 用，省 OCR 時間）；介面要看全部就傳 False。
    便宜的圖片比對先做，OCR 後做。
    """
    import ocr
    out: list[tuple[str, bool, str]] = []

    def add(name, ok, shown):
        out.append((name, ok, shown))
        return not ok and stop_early

    if spec.ce is not None:
        s = _score(img, row, "ce", spec.ce)
        if add("禮裝", s >= THRESHOLD, f"{s:.2f}"):
            return out
    if spec.mlb:
        s = mlb_score(img, row)
        if add("禮裝滿破", s >= MLB_THRESHOLD, "滿破" if s >= MLB_THRESHOLD else "沒滿破"):
            return out
    if spec.servant:
        t = ocr.read(crop_field(img, row, "servant"))
        if add("從者", ocr.same_name(t, spec.servant), t or "（讀不到）"):
            return out
    if spec.player:
        t = ocr.read(crop_field(img, row, "player"))
        if add("玩家", ocr.same_name(t, spec.player), t or "（讀不到）"):
            return out
    if spec.min_level:
        lv = ocr.parse_level(ocr.read(crop_field(img, row, "level")))
        if add("等級", lv is not None and lv >= spec.min_level, f"Lv.{lv}" if lv else "（讀不到）"):
            return out
    if spec.min_np:
        lv = ocr.parse_np_level(ocr.read(crop_field(img, row, "np")))
        if add("寶具", lv is not None and lv >= spec.min_np, f"Lv.{lv}" if lv else "（讀不到）"):
            return out
    return out


def row_matches(img, row, spec: SupportSpec) -> bool:
    return all(ok for _, ok, _ in check_row(img, row, spec))


def tap_point(row) -> tuple[int, int]:
    """點這一列的從者名稱區（點頭像會打開詳細資訊）。"""
    cx, cy = row[0], row[1]
    return cx + 150, cy
