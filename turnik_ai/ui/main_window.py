"""Asosiy oyna: kamera, hisoblagichlar, holat, xatolar, boshqaruv, natijalar va tarix."""
import json
from datetime import datetime

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Property
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QProgressBar, QPushButton, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

import settings as S
from camera import list_cameras
from database import Database
from ui import styles as ST
from ui.worker import Worker

STATE_UZ = {"READY": "READY — tayyor", "PULLING": "PULLING — tortilmoqda", "TOP": "TOP — yuqorida",
            "DESCENDING": "DESCENDING — tushmoqda", "BOTTOM": "BOTTOM — pastda",
            "VALIDATION": "VALIDATION — tekshirilmoqda"}
THUMB_UZ = {"ok": "to'g'ri", "wrong": "NOTO'G'RI", "unknown": "tekshirib bo'lmadi"}


class Card(QFrame):
    def __init__(self, title, color=ST.TEXT):
        super().__init__()
        self.setObjectName("card")
        self._color = QColor(color)
        lay = QVBoxLayout(self)
        t = QLabel(title.upper())
        t.setObjectName("cardTitle")
        self.value = QLabel("0")
        self.value.setObjectName("cardValue")
        self.value.setStyleSheet(f"color:{color};")
        lay.addWidget(t)
        lay.addWidget(self.value)
        self._flash = 0.0
        self.anim = QPropertyAnimation(self, b"flash", self)
        self.anim.setDuration(500)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

    def set_value(self, v):
        v = str(v)
        if v != self.value.text():
            self.value.setText(v)
            self.anim.start()                    # raqam o'zgarganda yorug'lik animatsiyasi

    def _get(self):
        return self._flash

    def _set(self, f):
        self._flash = f
        c = self._color
        self.setStyleSheet(f"QFrame#card{{background:{ST.CARD};border-radius:14px;"
                           f"border:1px solid rgba({c.red()},{c.green()},{c.blue()},{int(40 + 215 * f)});}}")

    flash = Property(float, _get, _set)


class ResultsDialog(QDialog):
    def __init__(self, parent, data: dict, duration_s: float):
        super().__init__(parent)
        self.setWindowTitle("Mashg'ulot natijalari")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        total, ok, bad = data["total"], data["correct"], data["wrong"]
        pct = round(100 * ok / total) if total else 0
        mm, ss = divmod(int(duration_s), 60)
        title = QLabel("Natijalar")
        title.setStyleSheet("font-size:24px;font-weight:700;")
        lay.addWidget(title)
        for text in (f"Jami tortilishlar: {total}", f"To'g'ri: {ok}", f"Noto'g'ri: {bad}",
                     f"Muvaffaqiyat: {pct}%", f"Davomiyligi: {mm:02d}:{ss:02d}"):
            lay.addWidget(QLabel(text))
        bar = QProgressBar()
        bar.setValue(pct)
        lay.addWidget(bar)
        lay.addWidget(QLabel("Xatolar statistikasi:"))
        if data["error_stats"]:
            for err, n in sorted(data["error_stats"].items(), key=lambda x: -x[1]):
                lbl = QLabel(f"  • {err}  ×{n}")
                lbl.setWordWrap(True)
                lay.addWidget(lbl)
        else:
            lay.addWidget(QLabel("  Xato qayd etilmadi"))
        notes = {n for r in data["reps"] for n in r["notes"]}
        if notes:
            lay.addWidget(QLabel("Tekshirib bo'lmagan holatlar (xato hisoblanmadi):"))
            for n in sorted(notes):
                lbl = QLabel(f"  • {n}")
                lbl.setObjectName("muted")
                lay.addWidget(lbl)
        b = QPushButton("Yopish")
        b.clicked.connect(self.accept)
        lay.addWidget(b)


class MainWindow(QMainWindow):
    def __init__(self, cfg: S.Settings, use_gpu=False):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("TURNIK AI")
        self.resize(1360, 820)
        self.db = Database()
        self.worker = Worker(cfg, use_gpu)
        self.worker.frame_ready.connect(self.on_frame)
        self.worker.rep_event.connect(self.on_rep_event)
        self.worker.status.connect(self.on_status)
        self.session_start = None
        self.session_tick = None
        self.running = False
        self._build()
        self.worker.start()
        QTimer.singleShot(200, self._fill_cameras)

    # ------------------------------------------------------------------ UI qurish
    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        tabs = QTabWidget()
        outer.addWidget(tabs)
        live = QWidget()
        tabs.addTab(live, "Mashg'ulot")
        h = QHBoxLayout(live)
        h.setSpacing(16)

        self.video = QLabel("Kamerani yoqing")
        self.video.setObjectName("video")
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setMinimumSize(720, 480)
        h.addWidget(self.video, 3)

        panel = QWidget()
        panel.setObjectName("panel")
        panel.setFixedWidth(400)
        p = QVBoxLayout(panel)
        h.addWidget(panel)

        grid = QGridLayout()
        self.c_total, self.c_ok, self.c_bad = Card("Jami"), Card("To'g'ri", ST.OK), Card("Noto'g'ri", ST.BAD)
        grid.addWidget(self.c_total, 0, 0)
        grid.addWidget(self.c_ok, 0, 1)
        grid.addWidget(self.c_bad, 0, 2)
        p.addLayout(grid)

        self.state = QLabel(STATE_UZ["READY"])
        self.state.setObjectName("state")
        self.state.setAlignment(Qt.AlignCenter)
        p.addWidget(self.state)

        trow = QHBoxLayout()
        t1 = QLabel("Pastki holatda:")
        t1.setObjectName("muted")
        self.timer_lbl = QLabel("0.0 s")
        self.timer_lbl.setObjectName("timer")
        trow.addWidget(t1)
        trow.addStretch()
        trow.addWidget(self.timer_lbl)
        p.addLayout(trow)

        self.bar_lbl = QLabel("Turnik: aniqlanmadi — osilib, qo'llarni to'g'rilab 1–2 s turing")
        self.bar_lbl.setObjectName("muted")
        self.bar_lbl.setWordWrap(True)
        p.addWidget(self.bar_lbl)
        self.detail = QLabel("")
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        p.addWidget(self.detail)

        e = QLabel("TEXNIK XATOLAR")
        e.setObjectName("cardTitle")
        p.addWidget(e)
        self.errors = QLabel("—")
        self.errors.setObjectName("errors")
        self.errors.setWordWrap(True)
        self.errors.setMinimumHeight(90)
        self.errors.setAlignment(Qt.AlignTop)
        p.addWidget(self.errors)
        p.addStretch()

        row = QHBoxLayout()
        self.cam_combo = QComboBox()
        self.res_combo = QComboBox()
        for txt, v in (("1280×720", (1280, 720)), ("640×480", (640, 480)), ("1920×1080", (1920, 1080))):
            self.res_combo.addItem(txt, v)
        self.fps_combo = QComboBox()
        for f in (30, 60, 24, 15):
            self.fps_combo.addItem(f"{f} FPS", f)
        for w in (self.cam_combo, self.res_combo, self.fps_combo):
            row.addWidget(w)
        p.addLayout(row)
        row2 = QHBoxLayout()
        self.btn_cam = QPushButton("Kamerani yoqish")
        self.btn_cam.clicked.connect(self.toggle_camera)
        self.btn_cal = QPushButton("Turnikni qayta aniqlash")
        self.btn_cal.clicked.connect(lambda: self.worker.command("recalibrate"))
        row2.addWidget(self.btn_cam)
        row2.addWidget(self.btn_cal)
        p.addLayout(row2)
        row3 = QHBoxLayout()
        up = QPushButton("Chiziq ↑")
        down = QPushButton("Chiziq ↓")
        up.clicked.connect(lambda: self.worker.command("nudge", 0.05))
        down.clicked.connect(lambda: self.worker.command("nudge", -0.05))
        row3.addWidget(up)
        row3.addWidget(down)
        p.addLayout(row3)

        row4 = QHBoxLayout()
        self.btn_start = QPushButton("START")
        self.btn_start.setObjectName("start")
        self.btn_pause = QPushButton("PAUSE")
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setObjectName("stop")
        self.btn_start.clicked.connect(self.start)
        self.btn_pause.clicked.connect(self.pause)
        self.btn_stop.clicked.connect(self.stop)
        for b in (self.btn_start, self.btn_pause, self.btn_stop):
            row4.addWidget(b)
        p.addLayout(row4)
        self.fps_lbl = QLabel("FPS: —   |   Kamera o'chiq")
        self.fps_lbl.setObjectName("muted")
        p.addWidget(self.fps_lbl)
        self._set_buttons(False)

        # --- Tarix ---
        hist = QWidget()
        tabs.addTab(hist, "Tarix")
        tabs.currentChanged.connect(lambda i: self.refresh_history() if i == 1 else None)
        hl = QVBoxLayout(hist)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Sana", "Davomiyligi", "Jami", "To'g'ri", "Noto'g'ri", "Foiz"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        hl.addWidget(self.table)
        d = QPushButton("Tanlanganini o'chirish")
        d.clicked.connect(self.delete_selected)
        hl.addWidget(d)

    def _set_buttons(self, cam_on):
        self.btn_start.setEnabled(cam_on and not self.running)
        self.btn_pause.setEnabled(cam_on and self.running)
        self.btn_stop.setEnabled(cam_on and self.running)
        self.btn_cal.setEnabled(cam_on)

    def _fill_cameras(self):
        self.cam_combo.clear()
        for c in list_cameras():
            self.cam_combo.addItem(f"Kamera {c['index']}", c["index"])
        if self.cam_combo.count() == 0:
            self.cam_combo.addItem("Kamera topilmadi", -1)

    # ------------------------------------------------------------------ boshqaruv
    def toggle_camera(self):
        if self.worker.camera_on:
            if self.running:
                self.stop()
            self.worker.command("camera_off")
            self.btn_cam.setText("Kamerani yoqish")
            self._set_buttons(False)
            self.video.clear()
            self.video.setText("Kamerani yoqing")
        else:
            idx = self.cam_combo.currentData()
            if idx is None or idx < 0:
                QMessageBox.warning(self, "Kamera", "Kamera topilmadi.")
                return
            w, h = self.res_combo.currentData()
            self.worker.command("camera_on", idx, w, h, self.fps_combo.currentData())
            self.btn_cam.setText("Kamerani o'chirish")
            self._set_buttons(True)

    def start(self):
        self.running = True
        self.session_start = datetime.now()
        self.session_tick = datetime.now()
        self.worker.command("start")
        self._set_buttons(True)
        self.btn_pause.setText("PAUSE")

    def pause(self):
        self.worker.command("pause")
        self.btn_pause.setText("DAVOM ETISH" if self.btn_pause.text() == "PAUSE" else "PAUSE")

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.worker.command("stop")
        self._set_buttons(self.worker.camera_on)
        self.btn_pause.setText("PAUSE")

    # ------------------------------------------------------------------ signallar
    def on_frame(self, img, info):
        pm = QPixmap.fromImage(img).scaled(self.video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video.setPixmap(pm)
        self.c_total.set_value(info["total"])
        self.c_ok.set_value(info["correct"])
        self.c_bad.set_value(info["wrong"])
        self.state.setText(STATE_UZ.get(info["state"], info["state"]))
        secs = info["bottom_seconds"]
        self.timer_lbl.setText(f"{secs:.1f} s")
        self.timer_lbl.setStyleSheet(f"color:{ST.BAD if secs > self.cfg.bottom_max_seconds else ST.TEXT};")
        if info["bar_ready"]:
            self.bar_lbl.setText("Turnik: aniqlandi ✓")
        elif not info["tracked"]:
            self.bar_lbl.setText("Odam to'liq ko'rinmayapti — qo'llar, tirsaklar va yelkalar kadrda bo'lsin")
        else:
            self.bar_lbl.setText("Turnik: aniqlanmoqda — osilib, qo'llarni to'g'rilab 1–2 s turing")
        parts = []
        if info["elbow"] is not None:
            parts.append(f"Tirsak: {info['elbow']:.0f}°")
        parts.append("O'ng tizza: " + (f"{info['knee_r']:.0f}°" if info["knee_r"] else "ko'rinmaydi"))
        parts.append("Chap tizza: " + (f"{info['knee_l']:.0f}°" if info["knee_l"] else "ko'rinmaydi"))
        parts.append(f"Bosh barmoq: {THUMB_UZ[info['thumb_r']]} / {THUMB_UZ[info['thumb_l']]}")
        self.detail.setText("   ".join(parts))
        errs = info["errors"]
        self.errors.setText("\n".join("✗ " + e for e in errs) if errs else
                            ("\n".join("• " + n for n in info["notes"]) if info["notes"] else "—"))
        self.errors.setStyleSheet(f"color:{ST.BAD if errs else ST.MUTED};")
        self.fps_lbl.setText(f"FPS: {info['fps']:.0f}   |   {'MASHG`ULOT' if info['counting'] else 'KUZATUV'}")

    def on_rep_event(self, kind, data):
        if kind != "session_end":
            return
        dur = (datetime.now() - self.session_start).total_seconds() if self.session_start else 0
        if data["total"] > 0:
            class _C:                              # database.save_session counter interfeysi
                total, correct, wrong = data["total"], data["correct"], data["wrong"]
                error_stats = data["error_stats"]
                verdicts = [type("V", (), {"to_dict": lambda s, d=d: d})() for d in data["reps"]]
            self.db.save_session(self.session_start, dur, _C)
        ResultsDialog(self, data, dur).exec()

    def on_status(self, msg):
        self.fps_lbl.setText(msg)
        if "yuklab bo'lmadi" in msg or "ochib bo'lmadi" in msg:
            QMessageBox.critical(self, "Xato", msg)
            self.btn_cam.setText("Kamerani yoqish")
            self._set_buttons(False)

    # ------------------------------------------------------------------ tarix
    def refresh_history(self):
        rows = self.db.list_sessions()
        self.table.setRowCount(len(rows))
        self._row_ids = []
        for r, s in enumerate(rows):
            mm, ss = divmod(int(s["duration_s"]), 60)
            pct = round(100 * s["correct"] / s["total"]) if s["total"] else 0
            vals = [s["started_at"].replace("T", " "), f"{mm:02d}:{ss:02d}", s["total"], s["correct"],
                    s["wrong"], f"{pct}%"]
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))
            self._row_ids.append(s["id"])

    def delete_selected(self):
        r = self.table.currentRow()
        if r >= 0 and QMessageBox.question(self, "O'chirish", "Tanlangan mashg'ulotni o'chirasizmi?") == QMessageBox.Yes:
            self.db.delete_session(self._row_ids[r])
            self.refresh_history()

    def closeEvent(self, e):
        self.worker.stop_thread()
        self.db.close()
        super().closeEvent(e)
