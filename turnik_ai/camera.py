"""Kamera bilan ishlash: ro'yxat, tanlash, alohida oqimda o'qish (kechikishsiz)."""
import threading
import time
from typing import Optional

import cv2

BACKEND = cv2.CAP_MSMF  # sinovda DSHOW qorong'i sahnada 4-5 FPS berdi, MSMF ~28 FPS


def list_cameras(max_index: int = 5) -> list[dict]:
    """Mavjud kameralarni tekshiradi. Natija: [{'index', 'width', 'height'}]."""
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, BACKEND)
        if cap.isOpened():
            ok, frame = cap.read()
            if ok:
                found.append({"index": i, "width": frame.shape[1], "height": frame.shape[0]})
        cap.release()
    return found


class Camera:
    def __init__(self):
        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._frame = None
        self._ts = 0.0
        self._seq = 0
        self._running = False
        self.capture_fps = 0.0

    @property
    def is_open(self) -> bool:
        return self._running and self._cap is not None and self._cap.isOpened()

    def start(self, index=0, width=1280, height=720, fps=30) -> bool:
        self.stop()
        cap = cv2.VideoCapture(index, BACKEND)
        if not cap.isOpened():
            return False
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ok, _ = cap.read()
        if not ok:
            cap.release()
            return False
        self._cap = cap
        self._running = True
        self._seq = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def _loop(self):
        n, t0 = 0, time.perf_counter()
        fails = 0
        while self._running:
            ok, frame = self._cap.read()
            if not ok:
                fails += 1
                if fails > 30:
                    break
                time.sleep(0.01)
                continue
            fails = 0
            with self._lock:
                self._frame, self._ts = frame, time.perf_counter()
                self._seq += 1
            n += 1
            dt = time.perf_counter() - t0
            if dt >= 1.0:
                self.capture_fps, n, t0 = n / dt, 0, time.perf_counter()
        self._running = False

    def read(self, last_seq: int = -1):
        """Yangi kadr bo'lsa (frame, timestamp, seq), bo'lmasa None."""
        with self._lock:
            if self._frame is None or self._seq == last_seq:
                return None
            return self._frame.copy(), self._ts, self._seq

    def actual_size(self):
        if self._cap is None:
            return (0, 0, 0.0)
        return (int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                self._cap.get(cv2.CAP_PROP_FPS))

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._frame = None
