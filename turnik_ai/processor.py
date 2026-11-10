"""Kadr konveyeri: kamera kadri -> pose -> qo'l -> qoidalar -> chizilgan kadr + holat (UI'dan mustaqil)."""
from typing import Optional

import cv2
import numpy as np

import settings as S
import validation as V
from hand_detection import HandDetector, analyze_thumb, draw_hands, match_hand_to_wrist
from pose_detection import PoseDetector, draw_skeleton
from pullup_counter import PullUpCounter

CYAN, VIOLET, GREEN, RED = (255, 220, 80), (255, 90, 160), (120, 230, 120), (90, 90, 255)


class Processor:
    def __init__(self, cfg: Optional[S.Settings] = None, use_gpu: bool = False, on_event=None):
        self.cfg = cfg or S.Settings()
        self.pose = PoseDetector(self.cfg, use_gpu)
        self.hands = HandDetector(use_gpu)
        self.counter = PullUpCounter(self.cfg, on_event=on_event)
        self.counting = False       # START bosilgandan keyin True
        self._frame_no = 0
        self._thumb = {"r": V.UNKNOWN, "l": V.UNKNOWN}
        self._thumb_age = {"r": 99, "l": 99}
        self.last_metrics = None
        self.last_hands = []

    def set_counting(self, on: bool):
        if on and not self.counting:
            self.counter.reset(keep_bar=True)
        self.counting = on

    def process(self, frame: np.ndarray, t: float) -> tuple[np.ndarray, dict]:
        self._frame_no += 1
        ts_ms = int(t * 1000)
        pr = self.pose.detect(frame, ts_ms)
        m = V.compute_metrics(pr.img, pr.world, t, self.cfg)
        bar = self.counter.bar

        # Bosh barmoq: har 2-kadrda, faqat turnik aniq bo'lganda
        if m.tracked and bar.ready and self._frame_no % 2 == 0:
            self.last_hands = self.hands.detect(frame, ts_ms)
            for side, wr in (("l", S.WRIST_L), ("r", S.WRIST_R)):
                h = match_hand_to_wrist(self.last_hands, pr.img[wr][:2])
                st = analyze_thumb(h, bar.top_y, bar.center_y)
                self._thumb[side], self._thumb_age[side] = st, 0
        else:
            for s in "lr":
                self._thumb_age[s] += 1
        for s in "lr":
            if self._thumb_age[s] > 4:
                self._thumb[s] = V.UNKNOWN
        m.thumb_l, m.thumb_r = self._thumb["l"], self._thumb["r"]
        self.last_metrics = m

        if self.counting:
            self.counter.update(m)
        else:                                  # START dan oldin turnik chizig'ini kalibrlash
            bar.update(m.hands_y, m.elbow_angle, m.scale)

        out = frame
        self._draw(out, pr, m)
        return out, self._info(m)

    def _draw(self, frame, pr, m):
        h, w = frame.shape[:2]
        bar = self.counter.bar
        if pr.img is not None:
            draw_skeleton(frame, pr.img, VIOLET, self.cfg.min_visibility)
            if m.chin_y is not None:
                cx = int((pr.img[S.MOUTH_L][0] + pr.img[S.MOUTH_R][0]) / 2 * w)
                over = self.counter.chin_rel is not None and self.counter.chin_rel >= 0
                cv2.circle(frame, (cx, int(m.chin_y * h)), 7, GREEN if over else CYAN, -1, cv2.LINE_AA)
            draw_hands(frame, self.last_hands)
        if bar.top_y is not None:
            y = int(bar.top_y * h)
            col = CYAN if bar.ready else (160, 160, 160)
            for x in range(0, w, 28):           # punktir chiziq
                cv2.line(frame, (x, y), (min(x + 16, w), y), col, 2, cv2.LINE_AA)
            cv2.putText(frame, "TURNIK" if bar.ready else "TURNIK (aniqlanmoqda)", (12, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 1, cv2.LINE_AA)

    def _info(self, m) -> dict:
        c = self.counter
        return {
            "tracked": m.tracked, "state": c.state if self.counting else "READY",
            "counting": self.counting, "total": c.total, "correct": c.correct, "wrong": c.wrong,
            "bottom_seconds": c.bottom_seconds if c.state == "BOTTOM" else 0.0,
            "errors": list(c.last_errors), "bar_ready": c.bar.ready,
            "chin_rel": c.chin_rel, "elbow": m.elbow_angle, "knee_r": m.knee_r, "knee_l": m.knee_l,
            "thumb_r": m.thumb_r, "thumb_l": m.thumb_l,
            "notes": list(c.verdicts[-1].notes) if c.verdicts else [],
        }

    def close(self):
        self.pose.close()
        self.hands.close()
