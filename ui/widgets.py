"""共用元件：OpenCV 圖轉 Qt、可點選的截圖檢視、背景執行 Bot。"""
import threading
import time

import cv2
import numpy as np
from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from . import theme


def to_pixmap(bgr: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy())


class ScreenView(QWidget):
    """顯示 1280x720 截圖（等比例縮放），可以疊框，點擊時回傳原圖座標。"""

    clicked = Signal(int, int)

    def __init__(self, placeholder: str = "尚無畫面", parent=None):
        super().__init__(parent)
        self._pix: QPixmap | None = None
        self._size = (1280, 720)
        self.overlays: list[tuple[tuple[int, int, int, int], str, int, str]] = []  # (框, 顏色, 線寬, 文字)
        self.placeholder = placeholder
        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_image(self, bgr: np.ndarray | None):
        if bgr is None:
            self._pix = None
        else:
            self._pix = to_pixmap(bgr)
            self._size = (bgr.shape[1], bgr.shape[0])
        self.update()

    def set_overlays(self, overlays):
        self.overlays = list(overlays)
        self.update()

    def sizeHint(self):
        return QSize(640, 360)

    def _geometry(self):
        iw, ih = self._size
        s = min(self.width() / iw, self.height() / ih)
        dw, dh = iw * s, ih * s
        return (self.width() - dw) / 2, (self.height() - dh) / 2, s

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#0b0e14"))
        p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        if self._pix is None:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.placeholder)
            return
        x0, y0, s = self._geometry()
        iw, ih = self._size
        p.drawPixmap(QRectF(x0, y0, iw * s, ih * s), self._pix, QRectF(0, 0, iw, ih))
        for (x1, y1, x2, y2), color, width, label in self.overlays:
            r = QRectF(x0 + x1 * s, y0 + y1 * s, (x2 - x1) * s, (y2 - y1) * s)
            p.setPen(QPen(QColor(color), width))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, 4, 4)
            if label:
                p.setPen(QColor(color))
                p.drawText(r.adjusted(6, 2, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, label)

    def mousePressEvent(self, e):
        if self._pix is None:
            return
        x0, y0, s = self._geometry()
        pos: QPointF = e.position()
        x, y = (pos.x() - x0) / s, (pos.y() - y0) / s
        if 0 <= x < self._size[0] and 0 <= y < self._size[1]:
            self.clicked.emit(int(x), int(y))


class Thumb(QLabel):
    """小縮圖（助戰欄位用）。"""

    def __init__(self, w=150, h=34):
        super().__init__()
        self.setObjectName("thumb")
        self.setFixedSize(w, h)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clear_thumb()

    def clear_thumb(self, text="—"):
        self.setPixmap(QPixmap())
        self.setText(text)

    def set_bgr(self, bgr):
        if bgr is None or bgr.size == 0:
            self.clear_thumb()
            return
        pix = to_pixmap(bgr).scaled(self.width() - 6, self.height() - 6, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
        self.setText("")
        self.setPixmap(pix)


def stat_card(label: str) -> tuple[QFrame, QLabel]:
    card = QFrame()
    card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(2)
    value = QLabel("—")
    value.setObjectName("statValue")
    cap = QLabel(label)
    cap.setObjectName("statLabel")
    lay.addWidget(value)
    lay.addWidget(cap)
    return card, value


class BotRunner(QObject):
    """在背景執行緒跑 Bot；log 和結束透過 signal 回到介面執行緒。"""

    log = Signal(str)
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.bot = None
        self._thread: threading.Thread | None = None
        self.started_at = 0.0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, config, serial: str):
        if self.running:
            return
        self.started_at = time.monotonic()
        self._thread = threading.Thread(target=self._run, args=(config, serial), daemon=True)
        self._thread.start()

    def _emit(self, msg: str):
        self.log.emit(f"{time.strftime('%H:%M:%S')}  {msg}")

    def _run(self, config, serial):
        from bot import Bot
        from device import Device
        try:
            self._emit(f"連線模擬器 {serial} …")
            dev = Device(serial)
            dev.screenshot()  # 先試一張，連不上就早點報錯
            self.bot = Bot(dev, config, logger=self._emit)
            self.bot.run()
        except Exception as e:  # 不讓背景執行緒的錯誤默默消失
            self._emit(f"錯誤：{type(e).__name__}: {e}")
        finally:
            self.finished.emit()

    def stop(self):
        if self.bot is not None:
            self.bot.stop()
