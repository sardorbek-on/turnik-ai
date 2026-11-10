"""Turnik chizig'ini aniqlash.

MediaPipe turnikni o'zi ko'rmaydi. Odam osilib turganda (qo'llar to'g'ri) qo'llari turnikda bo'ladi,
shuning uchun qo'llar markazining y koordinatasi turnik chizig'i sifatida olinadi va barqaror bo'lgach
qulflanadi. Qo'lda sozlash (nudge) va qayta kalibrlash ham mumkin.
"""
from collections import deque
from typing import Optional

import numpy as np

import settings as S


class BarTracker:
    def __init__(self, cfg: S.Settings):
        self.cfg = cfg
        self._samples = deque(maxlen=45)
        self.center_y: Optional[float] = None   # qulflangan qo'l markazi
        self.locked = False
        self.manual_shift = 0.0                 # yelka kengligi birligida
        self.scale = 0.2

    def reset(self):
        self._samples.clear()
        self.center_y, self.locked, self.manual_shift = None, False, 0.0

    def unlock(self):
        self._samples.clear()
        self.locked = False

    def update(self, hands_y, elbow_angle, scale):
        if scale:
            self.scale = scale
        if self.locked or hands_y is None or elbow_angle is None:
            return
        if elbow_angle < self.cfg.arms_extended_angle:      # faqat osilib turganda o'rganiladi
            self._samples.clear()
            return
        self._samples.append(hands_y)
        if len(self._samples) >= 20:
            arr = np.array(self._samples)
            self.center_y = float(np.median(arr))
            if arr.std() < 0.01:                            # barqaror -> qulflash
                self.locked = True

    @property
    def ready(self) -> bool:
        return self.center_y is not None and self.locked

    @property
    def top_y(self) -> Optional[float]:
        """Turnikning yuqori tekisligi (normallashgan y). Jag' shundan kichik y ga o'tishi kerak."""
        if self.center_y is None:
            return None
        return self.center_y - (self.cfg.bar_top_offset + self.manual_shift) * self.scale

    def nudge(self, delta_scale_units: float):
        self.manual_shift += delta_scale_units
