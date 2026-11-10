"""Geometriya va texnik qoidalar: burchaklar, jag' nuqtasi, kadr o'lchamlari, xato matnlari."""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

import settings as S

# Xato matnlari (foydalanuvchiga ko'rsatiladi)
ERR_CHIN = "Jag'ingiz turnikdan to'liq o'tmadi."
ERR_KNEE_R = "O'ng tizzangiz bukildi."
ERR_KNEE_L = "Chap tizzangiz bukildi."
ERR_BOTTOM = "Pastki holatda 3 sekunddan ortiq turdingiz."
ERR_THUMB = "Bosh barmoq holati noto'g'ri."
ERR_THUMB_UNKNOWN = "Bosh barmoq holatini aniqlab bo'lmadi."
ERR_CYCLE = "To'liq tortilish sikli bajarilmadi (qo'llar to'liq cho'zilmadi)."

OK, WRONG, UNKNOWN = "ok", "wrong", "unknown"


def angle_3pts(a, b, c) -> Optional[float]:
    """b nuqtadagi burchak (daraja). Nuqtalar 2D yoki 3D."""
    a, b, c = (np.asarray(p, dtype=float) for p in (a, b, c))
    v1, v2 = a - b, c - b
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 < 1e-6 or n2 < 1e-6:
        return None
    cosang = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
    return float(np.degrees(np.arccos(cosang)))


@dataclass
class FrameMetrics:
    """Bitta kadrdan olingan, qoidalar uchun kerakli o'lchamlar."""
    t: float = 0.0
    tracked: bool = False                # tana yetarli ishonch bilan topildi
    elbow_angle: Optional[float] = None  # ikki tirsak o'rtachasi
    chin_y: Optional[float] = None       # jag' pastki nuqtasi (normallashgan y, kichik = yuqori)
    hands_y: Optional[float] = None      # qo'llar markazi y (turnik chizig'ini topish uchun)
    scale: Optional[float] = None        # yelka kengligi (normallashgan birlik)
    knee_r: Optional[float] = None       # None = ko'rinmadi
    knee_l: Optional[float] = None
    thumb_r: str = UNKNOWN
    thumb_l: str = UNKNOWN


def _vis_ok(lm, idx, thr):
    return all(lm[i][3] >= thr for i in idx)


def compute_metrics(img_lm: Optional[np.ndarray], world_lm: Optional[np.ndarray], t: float,
                    cfg: S.Settings) -> FrameMetrics:
    """img_lm: (33,4) [x,y,z,vis] normallashgan; world_lm: (33,3) metr."""
    m = FrameMetrics(t=t)
    if img_lm is None:
        return m
    thr = cfg.min_visibility
    upper = (S.SHOULDER_L, S.SHOULDER_R, S.ELBOW_L, S.ELBOW_R, S.WRIST_L, S.WRIST_R)
    if not _vis_ok(img_lm, upper, thr):
        return m
    m.tracked = True

    m.scale = float(np.linalg.norm(img_lm[S.SHOULDER_L][:2] - img_lm[S.SHOULDER_R][:2]))

    src = world_lm if world_lm is not None else img_lm[:, :3]
    angs = []
    for sh, el, wr in ((S.SHOULDER_L, S.ELBOW_L, S.WRIST_L), (S.SHOULDER_R, S.ELBOW_R, S.WRIST_R)):
        a = angle_3pts(src[sh], src[el], src[wr])
        if a is not None:
            angs.append(a)
    m.elbow_angle = float(np.mean(angs)) if angs else None

    # qo'llar markazi: bilak + ko'rsatkich + jimjiloq + bosh barmoq (ko'rinsa)
    hand_pts = [img_lm[i][1] for i in (S.WRIST_L, S.WRIST_R, S.INDEX_L, S.INDEX_R,
                                       S.PINKY_L, S.PINKY_R) if img_lm[i][3] >= thr]
    if hand_pts:
        m.hands_y = float(np.mean(hand_pts))

    m.chin_y = chin_y_estimate(img_lm, thr, cfg.chin_offset_ratio)

    m.knee_r = _knee(src, img_lm, S.HIP_R, S.KNEE_R, S.ANKLE_R, thr)
    m.knee_l = _knee(src, img_lm, S.HIP_L, S.KNEE_L, S.ANKLE_L, thr)
    return m


def _knee(src, img_lm, hip, knee, ankle, thr):
    if not _vis_ok(img_lm, (hip, knee, ankle), thr):
        return None
    return angle_3pts(src[hip], src[knee], src[ankle])


def chin_y_estimate(img_lm, thr, ratio: float = S.Settings.chin_offset_ratio) -> Optional[float]:
    """Jag' pastki nuqtasi MediaPipe Pose'da yo'q -> og'iz chizig'idan pastga
    'quloqlar orasidagi masofa * ratio' qadar surib baholanadi (bu TAXMINIY qiymat)."""
    if not _vis_ok(img_lm, (S.MOUTH_L, S.MOUTH_R, S.EAR_L, S.EAR_R), thr * 0.8):
        return None
    mouth_y = (img_lm[S.MOUTH_L][1] + img_lm[S.MOUTH_R][1]) / 2
    ear_d = float(np.linalg.norm(img_lm[S.EAR_L][:2] - img_lm[S.EAR_R][:2]))
    return float(mouth_y + ratio * ear_d)


@dataclass
class RepVerdict:
    index: int
    chin: str = UNKNOWN
    knee_r: str = UNKNOWN
    knee_l: str = UNKNOWN
    bottom: str = OK
    thumb: str = UNKNOWN
    complete: bool = True
    bottom_seconds: float = 0.0
    min_elbow: Optional[float] = None
    errors: list = field(default_factory=list)
    notes: list = field(default_factory=list)   # xato emas, ogohlantirish ("tekshirib bo'lmadi")

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self):
        return {"index": self.index, "valid": self.valid, "chin": self.chin, "knee_r": self.knee_r,
                "knee_l": self.knee_l, "bottom": self.bottom, "thumb": self.thumb,
                "complete": self.complete, "bottom_seconds": round(self.bottom_seconds, 2),
                "errors": list(self.errors), "notes": list(self.notes)}
