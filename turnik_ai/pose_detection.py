"""MediaPipe Pose (Tasks API) o'rovchisi: nuqtalar + EMA silliqlash + skelet chizish."""
from dataclasses import dataclass
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

import settings as S


@dataclass
class PoseResult:
    img: Optional[np.ndarray] = None     # (33,4) x,y,z,visibility — normallashgan
    world: Optional[np.ndarray] = None   # (33,3) metr, 3D


def make_base_options(model_path, use_gpu: bool):
    delegate = mp_python.BaseOptions.Delegate.GPU if use_gpu else mp_python.BaseOptions.Delegate.CPU
    return mp_python.BaseOptions(model_asset_path=str(model_path), delegate=delegate)


class PoseDetector:
    def __init__(self, cfg: S.Settings, use_gpu: bool = False):
        self.cfg = cfg
        self.gpu_active = use_gpu
        try:
            self._lm = self._create(use_gpu)
        except Exception:
            if not use_gpu:
                raise
            self.gpu_active = False                       # GPU bo'lmasa CPU'ga qaytamiz
            self._lm = self._create(False)
        self._prev: Optional[np.ndarray] = None
        self._last_ts = -1

    def _create(self, use_gpu):
        opts = vision.PoseLandmarkerOptions(
            base_options=make_base_options(S.POSE_MODEL, use_gpu),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        return vision.PoseLandmarker.create_from_options(opts)

    def detect(self, bgr: np.ndarray, ts_ms: int) -> PoseResult:
        ts_ms = max(ts_ms, self._last_ts + 1)             # VIDEO rejimi qat'iy o'suvchi vaqt talab qiladi
        self._last_ts = ts_ms
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        res = self._lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts_ms)
        if not res.pose_landmarks:
            self._prev = None
            return PoseResult()
        lm = np.array([[p.x, p.y, p.z, p.visibility] for p in res.pose_landmarks[0]], dtype=np.float32)
        world = np.array([[p.x, p.y, p.z] for p in res.pose_world_landmarks[0]], dtype=np.float32)
        a = self.cfg.smooth_alpha
        if self._prev is not None:
            lm[:, :3] = a * lm[:, :3] + (1 - a) * self._prev[:, :3]
        self._prev = lm.copy()
        return PoseResult(img=lm, world=world)

    def close(self):
        self._lm.close()


def draw_skeleton(frame, img_lm, color=(255, 140, 90), thr=0.5):
    h, w = frame.shape[:2]
    pts = {}
    for i, p in enumerate(img_lm):
        if p[3] >= thr:
            pts[i] = (int(p[0] * w), int(p[1] * h))
    for a, b in S.SKELETON_EDGES:
        if a in pts and b in pts:
            cv2.line(frame, pts[a], pts[b], color, 3, cv2.LINE_AA)
    for i, pt in pts.items():
        if i >= 11:
            cv2.circle(frame, pt, 5, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, pt, 5, color, 1, cv2.LINE_AA)
