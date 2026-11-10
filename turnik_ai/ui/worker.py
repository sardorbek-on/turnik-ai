"""Kamera + AI ishlov berish oqimi (UI muzlamasligi uchun alohida QThread)."""
import time

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

import settings as S
from camera import Camera
from processor import Processor


class Worker(QThread):
    frame_ready = Signal(QImage, dict)
    rep_event = Signal(str, dict)          # "rep" | "rep_revised"
    status = Signal(str)                   # xabar (xatolar, kamera holati)

    def __init__(self, cfg: S.Settings, use_gpu=False):
        super().__init__()
        self.cfg, self.use_gpu = cfg, use_gpu
        self._run = True
        self._paused = False
        self._cmds: list[tuple] = []
        self.cam = Camera()
        self.camera_on = False
        # MediaPipe'ning lazy-import mexanizmi ikkinchi oqimda xato beradi ('lazy_import' object is not
        # callable), shuning uchun modellar ASOSIY oqimda yaratiladi, ishlatilishi esa worker oqimida.
        self.proc = Processor(cfg, use_gpu, on_event=self._on_event)

    # --- UI oqimidan chaqiriladi (xavfsiz: faqat navbatga qo'yadi) ---
    def command(self, *cmd):
        self._cmds.append(cmd)

    def stop_thread(self):
        self._run = False
        self.wait(5000)

    def _on_event(self, kind, verdict):
        self.rep_event.emit(kind, verdict.to_dict())

    def run(self):
        proc = self.proc
        seq, t_start, fps_n, fps_t0, fps = -1, None, 0, time.perf_counter(), 0.0
        while self._run:
            while self._cmds:
                self._handle(proc, self._cmds.pop(0))
            if not self.camera_on or self._paused:
                time.sleep(0.02)
                continue
            r = self.cam.read(seq)
            if r is None:
                if not self.cam.is_open:
                    self.camera_on = False
                    self.status.emit("Kamera uzildi.")
                time.sleep(0.003)
                continue
            frame, ts, seq = r
            if t_start is None:
                t_start = ts
            try:
                out, info = proc.process(frame, ts - t_start)
            except Exception as e:                      # xatoni yashirmaymiz, lekin dastur qulamasin
                self.status.emit(f"Ishlov berishda xato: {e}")
                continue
            fps_n += 1
            now = time.perf_counter()
            if now - fps_t0 >= 0.5:
                fps, fps_n, fps_t0 = fps_n / (now - fps_t0), 0, now
            info["fps"] = fps
            rgb = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            self.frame_ready.emit(QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy(), info)
        self.cam.stop()
        proc.close()

    def _handle(self, proc: Processor, cmd):
        name = cmd[0]
        if name == "camera_on":
            idx, w, h, fps = cmd[1:]
            ok = self.cam.start(idx, w, h, fps)
            self.camera_on = ok
            self.status.emit("Kamera yoqildi." if ok else "Kamerani ochib bo'lmadi.")
        elif name == "camera_off":
            self.camera_on = False
            self.cam.stop()
            self.status.emit("Kamera o'chirildi.")
        elif name == "start":
            self._paused = False
            proc.set_counting(True)
        elif name == "pause":
            self._paused = not self._paused
        elif name == "stop":
            proc.counter.finish(proc.last_metrics.t if proc.last_metrics else None)
            proc.set_counting(False)
            self._paused = False
            self.rep_event.emit("session_end", {
                "total": proc.counter.total, "correct": proc.counter.correct, "wrong": proc.counter.wrong,
                "error_stats": dict(proc.counter.error_stats),
                "reps": [v.to_dict() for v in proc.counter.verdicts]})
        elif name == "recalibrate":
            proc.counter.bar.unlock()
        elif name == "nudge":
            proc.counter.bar.nudge(cmd[1])
