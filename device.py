import subprocess, random, time
import numpy as np, cv2

class Device:
    def __init__(self, serial="127.0.0.1:16384"):  # MuMu 預設 port，雷電是 5555
        self.serial = serial
        subprocess.run(["adb", "connect", serial], capture_output=True)

    def _adb(self, *args):
        return subprocess.run(["adb", "-s", self.serial, *args], capture_output=True).stdout

    def screenshot(self):
        raw = self._adb("exec-out", "screencap")
        w, h = np.frombuffer(raw[:8], dtype=np.uint32)
        offset = len(raw) - w * h * 4  # header 長度依 Android 版本不同（12 或 16 bytes），從尾端回推
        img = np.frombuffer(raw[offset:], dtype=np.uint8).reshape(h, w, 4)
        return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)

    def tap(self, x, y, jitter=5):
        # 加隨機偏移和延遲，比較像人在點
        x += random.randint(-jitter, jitter)
        y += random.randint(-jitter, jitter)
        self._adb("shell", "input", "tap", str(x), str(y))
        time.sleep(random.uniform(0.3, 0.6))

    def swipe(self, x1, y1, x2, y2, duration_ms=500):
        self._adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))
        time.sleep(random.uniform(0.8, 1.2))  # 等列表慣性停下來

if __name__ == "__main__":
    d = Device()
    t = time.time()
    cv2.imwrite("screen.png", d.screenshot())
    print(f"screenshot: {time.time() - t:.2f}s")