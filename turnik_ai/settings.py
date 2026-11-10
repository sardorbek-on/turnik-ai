"""Barcha sozlamalar va chegaraviy qiymatlar (bitta joyda)."""
from dataclasses import dataclass
from pathlib import Path

import os
import sys

FROZEN = getattr(sys, "frozen", False)          # PyInstaller bilan yig'ilgan .exe
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
MODELS_DIR = ROOT / "assets" / "models"
POSE_MODEL = MODELS_DIR / "pose_landmarker_full.task"
HAND_MODEL = MODELS_DIR / "hand_landmarker.task"
# .exe da dastur papkasi yozilmaydi -> tarix foydalanuvchi papkasida saqlanadi
DATA_DIR = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TurnikAI") if FROZEN else ROOT / "data"
DB_PATH = DATA_DIR / "turnik_ai.sqlite3"

# MediaPipe Pose nuqtalari indekslari
NOSE = 0
MOUTH_L, MOUTH_R = 9, 10
EAR_L, EAR_R = 7, 8
SHOULDER_L, SHOULDER_R = 11, 12
ELBOW_L, ELBOW_R = 13, 14
WRIST_L, WRIST_R = 15, 16
PINKY_L, PINKY_R = 17, 18
INDEX_L, INDEX_R = 19, 20
THUMB_L, THUMB_R = 21, 22
HIP_L, HIP_R = 23, 24
KNEE_L, KNEE_R = 25, 26
ANKLE_L, ANKLE_R = 27, 28

SKELETON_EDGES = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (24, 26), (26, 28),
    (15, 19), (16, 20),
]


@dataclass
class Settings:
    # --- kamera ---
    camera_index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30

    # --- ishonchlilik ---
    min_visibility: float = 0.5          # nuqta "ko'rinadi" deb hisoblanishi uchun
    smooth_alpha: float = 0.55           # EMA (1 = silliqlashsiz)

    # --- 1-qoida: jag' ---
    chin_offset_ratio: float = 0.33      # jag' pastki nuqtasi = og'iz + ratio * quloqlar orasidagi masofa
    bar_top_offset: float = 0.10         # turnik yuqori tekisligi = qo'l markazi - offset * yelka kengligi
    top_frames: int = 3                  # TOP uchun ketma-ket kadrlar
    top_hysteresis: float = 0.04         # TOP dan chiqish uchun (yelka kengligi birligida)

    # --- harakat bosqichlari (tirsak burchagi, daraja) ---
    arms_extended_angle: float = 150.0   # qo'llar to'g'ri = READY/BOTTOM
    pull_start_angle: float = 140.0      # shundan kichik bo'lsa tortilish boshlandi
    attempt_angle: float = 115.0         # shundan ko'proq bukilsa "urinish" hisoblanadi
    phase_frames: int = 3                # holat almashinuvi uchun ketma-ket kadrlar

    # --- 2-qoida: tizza ---
    knee_bent_angle: float = 155.0       # shundan kichik -> bukilgan (3D burchak)
    knee_bent_frames: int = 6            # ketma-ket kadrlar (shovqinga qarshi)
    knee_min_coverage: float = 0.5       # sikl davomida kamida shuncha kadrda ko'rinishi kerak

    # --- 3-qoida: pastki holatdagi vaqt ---
    bottom_max_seconds: float = 3.0

    # --- 4-qoida: bosh barmoq ---
    thumb_wrong_frames: int = 5
    thumb_required: bool = False         # True bo'lsa, "Tekshirib bo'lmadi" ham xato hisoblanadi

    # --- yo'qolish ---
    lost_hold_seconds: float = 0.6       # shu vaqtgacha aniqlash yo'qolsa e'tibor berilmaydi
    lost_reset_seconds: float = 2.0      # undan ko'p bo'lsa sikl bekor qilinadi
