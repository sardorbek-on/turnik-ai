"""MediaPipe Hands o'rovchisi va bosh barmoq (thumb) holatini baholash.

MUHIM: frontal kamerada bosh barmoq turnikning orqasida/pastida qolib ko'rinmaydi. Shu sababli
analyze_thumb() faqat ISHONCHLI dalil bo'lganda WRONG qaytaradi (bosh barmoq turnik tepasida,
boshqa barmoqlar yonida ochiq ko'rinib turibdi). Aks holda UNKNOWN ("Tekshirib bo'lmadi").
Frontal kameradan "to'g'ri" (OK) deb tasdiqlash uchun yetarli ma'lumot yo'q.
"""
from dataclasses import dataclass
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision

import settings as S
import validation as V
from pose_detection import make_base_options

WRIST, THUMB_IP, THUMB_TIP, INDEX_MCP, MIDDLE_MCP, PINKY_MCP = 0, 3, 4, 5, 9, 17


@dataclass
class Hand:
    lm: np.ndarray        # (21,3) normallashgan x,y,z
    score: float
    label: str


class HandDetector:
    def __init__(self, use_gpu: bool = False):
        opts = vision.HandLandmarkerOptions(
            base_options=make_base_options(S.HAND_MODEL, use_gpu),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._lm = vision.HandLandmarker.create_from_options(opts)
        self._last_ts = -1

    def detect(self, bgr: np.ndarray, ts_ms: int) -> list[Hand]:
        ts_ms = max(ts_ms, self._last_ts + 1)
        self._last_ts = ts_ms
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        res = self._lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts_ms)
        hands = []
        for pts, hd in zip(res.hand_landmarks, res.handedness):
            hands.append(Hand(np.array([[p.x, p.y, p.z] for p in pts], dtype=np.float32),
                              hd[0].score, hd[0].category_name))
        return hands

    def close(self):
        self._lm.close()


def match_hand_to_wrist(hands: list[Hand], wrist_xy, max_dist=0.12) -> Optional[Hand]:
    """Pose bilagiga eng yaqin qo'lni tanlaydi (Left/Right yorlig'iga tayanmaymiz)."""
    best, bd = None, max_dist
    for h in hands:
        d = float(np.linalg.norm(h.lm[WRIST][:2] - np.asarray(wrist_xy)))
        if d < bd:
            best, bd = h, d
    return best


def analyze_thumb(hand: Optional[Hand], bar_top_y: Optional[float], bar_center_y: Optional[float]) -> str:
    """OK / WRONG / UNKNOWN. Faqat ishonchli dalil bo'lsa WRONG."""
    if hand is None or bar_top_y is None or bar_center_y is None or hand.score < 0.7:
        return V.UNKNOWN
    lm = hand.lm
    hand_size = float(np.linalg.norm(lm[WRIST][:2] - lm[MIDDLE_MCP][:2]))
    if hand_size < 1e-3:
        return V.UNKNOWN
    tip, ip, idx = lm[THUMB_TIP], lm[THUMB_IP], lm[INDEX_MCP]
    margin = 0.25 * hand_size
    # Bosh barmoq uchi va bo'g'imi turnik tepasidan aniq yuqorida ochiq turibdi,
    # va barmoqlar bilan bir tomonda (turnikning pastidan o'ramayapti) -> noto'g'ri
    thumb_above = tip[1] < bar_top_y - margin and ip[1] < bar_top_y - margin
    near_index = abs(tip[0] - idx[0]) < 0.9 * hand_size
    if thumb_above and near_index:
        return V.WRONG
    return V.UNKNOWN


def draw_hands(frame, hands: list[Hand], color=(255, 200, 120)):
    h, w = frame.shape[:2]
    for hd in hands:
        for i in (THUMB_IP, THUMB_TIP):
            cv2.circle(frame, (int(hd.lm[i][0] * w), int(hd.lm[i][1] * h)), 6, color, -1, cv2.LINE_AA)
        cv2.circle(frame, (int(hd.lm[WRIST][0] * w), int(hd.lm[WRIST][1] * h)), 4, color, 1, cv2.LINE_AA)
