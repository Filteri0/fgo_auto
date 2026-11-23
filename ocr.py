"""文字辨識（RapidOCR，模型附在套件裡，不用連網）。

支援列表的欄位已經切好了，所以只跑「辨識」不跑「找文字位置」：每個欄位約 10~25 ms。
小字（例如 Lv.120/120 只有 26 像素高）先放大兩倍、加一點邊框，辨識率才會穩。
"""
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache

import cv2
import numpy as np

SCALE = 2
PAD = 8


@lru_cache(maxsize=1)
def _engine():
    import logging

    from rapidocr import RapidOCR
    log = logging.getLogger("RapidOCR")
    log.setLevel(logging.WARNING)  # 不要每次啟動都印 INFO
    eng = RapidOCR()
    log.setLevel(logging.WARNING)  # 它建立時會把等級設回 INFO，再設一次
    for h in log.handlers:
        h.setLevel(logging.WARNING)
    return eng


def read(img: np.ndarray) -> str:
    """辨識一行文字（已經切好的欄位）。"""
    if img is None or img.size == 0:
        return ""
    big = cv2.resize(img, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
    big = cv2.copyMakeBorder(big, PAD, PAD, PAD, PAD, cv2.BORDER_REPLICATE)
    res = _engine()(big, use_det=False, use_cls=False, use_rec=True)
    return "".join(res.txts) if res.txts else ""


def norm(s: str) -> str:
    """比對用：全形轉半形、去掉空白和標點、英文轉小寫。「呼噗噗，」→「呼噗噗」。"""
    s = unicodedata.normalize("NFKC", s or "")
    return "".join(ch for ch in s if ch.isalnum()).lower()


def same_name(a: str, b: str, ratio: float = 0.8) -> bool:
    """名字比對：容許 OCR 偶爾讀錯一個字（相似度 >= 0.8）。"""
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    return a == b or SequenceMatcher(None, a, b).ratio() >= ratio


_LEVEL = re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})")
_NP_LV = re.compile(r"lv\D{0,2}(\d)", re.IGNORECASE)


def parse_level(text: str) -> int | None:
    """「Lv.120/120」「Lv100/100」「Lv.,83/90」→ 目前等級（120、100、83）。"""
    m = _LEVEL.search(unicodedata.normalize("NFKC", text or ""))
    return int(m.group(1)) if m else None


def parse_np_level(text: str) -> int | None:
    """寶具那一行「早已無法抵達的理想鄉 Lv.5」→ 5（取最後一個 Lv）。"""
    found = _NP_LV.findall(unicodedata.normalize("NFKC", text or ""))
    return int(found[-1]) if found else None
