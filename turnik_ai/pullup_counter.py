"""Tortilish holat avtomati: READY -> PULLING -> TOP -> DESCENDING -> BOTTOM (+VALIDATION).

Sof mantiq (MediaPipe'siz) — shuning uchun sintetik ketma-ketliklar bilan sinab ko'rish mumkin.
Har bir holat almashinuvi bir necha ketma-ket kadr bilan tasdiqlanadi (shovqinga qarshi),
bitta sikl faqat bir marta hisoblanadi.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

import settings as S
import validation as V
from bar import BarTracker
from validation import FrameMetrics, RepVerdict

READY, PULLING, TOP, DESCENDING, BOTTOM, VALIDATION = (
    "READY", "PULLING", "TOP", "DESCENDING", "BOTTOM", "VALIDATION")


@dataclass
class _Cycle:
    min_elbow: float = 999.0
    reached_top: bool = False
    knee_total: dict = field(default_factory=lambda: {"r": 0, "l": 0})
    knee_seen: dict = field(default_factory=lambda: {"r": 0, "l": 0})
    knee_run: dict = field(default_factory=lambda: {"r": 0, "l": 0})
    knee_bent: dict = field(default_factory=lambda: {"r": False, "l": False})
    thumb_wrong: dict = field(default_factory=lambda: {"r": 0, "l": 0})
    thumb_seen: dict = field(default_factory=lambda: {"r": 0, "l": 0})
    frames: int = 0


class PullUpCounter:
    def __init__(self, cfg: Optional[S.Settings] = None, on_event: Optional[Callable] = None):
        self.cfg = cfg or S.Settings()
        self.on_event = on_event or (lambda kind, payload: None)
        self.bar = BarTracker(self.cfg)
        self.reset()

    # ------------------------------------------------------------------ holat
    def reset(self, keep_bar: bool = False):
        self.state = READY
        self.total = self.correct = self.wrong = 0
        self.verdicts: list[RepVerdict] = []
        self.error_stats: dict[str, int] = {}
        self.bottom_since: Optional[float] = None
        self.bottom_seconds = 0.0
        self.pending: Optional[RepVerdict] = None   # BOTTOM da 3 s qoidasi hali hal bo'lmagan takror
        self._cycle = _Cycle()
        self._counts = {"pull": 0, "top": 0, "down": 0, "ext": 0}
        self._last_good_t: Optional[float] = None
        self.chin_rel: Optional[float] = None
        self.last_errors: list[str] = []
        if not keep_bar:
            self.bar.reset()

    def _bump(self, key, cond):
        self._counts[key] = self._counts[key] + 1 if cond else 0
        return self._counts[key]

    def _emit(self, kind, payload=None):
        self.on_event(kind, payload)

    # ------------------------------------------------------------------ asosiy
    def update(self, m: FrameMetrics) -> str:
        cfg = self.cfg
        # Aniqlash yo'qolishi
        if not m.tracked or m.elbow_angle is None:
            if self._last_good_t is not None and m.t - self._last_good_t > cfg.lost_reset_seconds:
                self._abort_cycle()
            self._tick_bottom(m.t)
            return self.state
        self._last_good_t = m.t

        self.bar.update(m.hands_y, m.elbow_angle, m.scale)
        top_y = self.bar.top_y
        if self.bar.ready and m.chin_y is not None and m.scale:
            self.chin_rel = (top_y - m.chin_y) / m.scale      # >= 0 -> jag' turnikdan yuqorida
        else:
            self.chin_rel = None
        elbow = m.elbow_angle
        n = cfg.phase_frames
        cyc = self._cycle
        cyc.frames += 1
        cyc.min_elbow = min(cyc.min_elbow, elbow)
        self._track_knees(m)
        self._track_thumbs(m)

        extended = self._bump("ext", elbow >= cfg.arms_extended_angle)
        top_now = self._bump("top", self.chin_rel is not None and self.chin_rel >= 0)
        down_now = self._bump("down", self.chin_rel is not None and self.chin_rel < -cfg.top_hysteresis)
        pull_now = self._bump("pull", elbow < cfg.pull_start_angle)

        if self.state in (READY, BOTTOM):
            if not self.bar.ready:
                pass                                          # turnik hali aniqlanmadi — hukm yo'q
            elif pull_now >= n:
                self._begin_pull(m.t)
        elif self.state == PULLING:
            if top_now >= n:
                self.state = TOP
                cyc.reached_top = True
            elif extended >= n + 2:
                # pastga qaytdi, jag' o'tmadi: jiddiy urinish bo'lsa — xato takror
                if cyc.min_elbow < cfg.attempt_angle:
                    self._finalize(m.t, reached_top=False, descent_complete=True)
                else:
                    self._cycle = _Cycle()
                self.state = READY
        elif self.state == TOP:
            if down_now >= n:
                self.state = DESCENDING
        elif self.state == DESCENDING:
            if extended >= n:
                self._enter_bottom(m.t)
            elif top_now >= n:
                # qo'llar to'liq cho'zilmasdan yana tortildi -> avvalgi sikl to'liq emas
                self._finalize(m.t, reached_top=True, descent_complete=False)
                self.state = TOP
                self._cycle = _Cycle(reached_top=True, min_elbow=elbow)
        self._tick_bottom(m.t)
        return self.state

    # ------------------------------------------------------------------ yordamchi
    def _begin_pull(self, t):
        if self.state == BOTTOM:
            self._resolve_pending(t)
        self.bottom_since = None
        self.bottom_seconds = 0.0
        self._cycle = _Cycle(min_elbow=999.0)
        self.state = PULLING

    def _track_knees(self, m):
        cyc, cfg = self._cycle, self.cfg
        for side, ang in (("r", m.knee_r), ("l", m.knee_l)):
            cyc.knee_total[side] += 1
            if ang is None:
                cyc.knee_run[side] = 0
                continue
            cyc.knee_seen[side] += 1
            if ang < cfg.knee_bent_angle:
                cyc.knee_run[side] += 1
                if cyc.knee_run[side] >= cfg.knee_bent_frames:
                    cyc.knee_bent[side] = True
            else:
                cyc.knee_run[side] = 0

    def _track_thumbs(self, m):
        cyc = self._cycle
        for side, st in (("r", m.thumb_r), ("l", m.thumb_l)):
            if st == V.UNKNOWN:
                continue
            cyc.thumb_seen[side] += 1
            if st == V.WRONG:
                cyc.thumb_wrong[side] += 1

    def _enter_bottom(self, t):
        self.state = BOTTOM
        self.bottom_since = t
        self.bottom_seconds = 0.0
        verdict = self._finalize(t, reached_top=True, descent_complete=True)
        self.pending = verdict

    def _tick_bottom(self, t):
        if self.state == BOTTOM and self.bottom_since is not None:
            self.bottom_seconds = t - self.bottom_since
            if self.pending is not None and self.bottom_seconds > self.cfg.bottom_max_seconds:
                self._revise_for_bottom_timeout(self.pending, self.bottom_seconds)
                self.pending = None

    def _resolve_pending(self, t):
        if self.pending is not None:
            self.pending.bottom_seconds = max(0.0, t - (self.bottom_since or t))
            self.pending = None

    def _revise_for_bottom_timeout(self, verdict: RepVerdict, secs: float):
        verdict.bottom, verdict.bottom_seconds = V.WRONG, secs
        if V.ERR_BOTTOM not in verdict.errors:
            was_valid = verdict.valid
            verdict.errors.append(V.ERR_BOTTOM)
            self.error_stats[V.ERR_BOTTOM] = self.error_stats.get(V.ERR_BOTTOM, 0) + 1
            if was_valid:
                self.correct -= 1
                self.wrong += 1
        self.last_errors = list(verdict.errors)
        self._emit("rep_revised", verdict)

    def _abort_cycle(self):
        self._cycle = _Cycle()
        self.pending = None
        self.bottom_since = None
        self.state = READY

    def _knee_status(self, side):
        cyc = self._cycle
        if cyc.knee_bent[side]:
            return V.WRONG
        if cyc.knee_total[side] and cyc.knee_seen[side] / cyc.knee_total[side] >= self.cfg.knee_min_coverage:
            return V.OK
        return V.UNKNOWN

    def _thumb_status(self):
        cyc, cfg = self._cycle, self.cfg
        if any(cyc.thumb_wrong[s] >= cfg.thumb_wrong_frames for s in "rl"):
            return V.WRONG
        return V.UNKNOWN   # frontal kamerada "to'g'ri" deb tasdiqlab bo'lmaydi (README'ga qarang)

    def _finalize(self, t, reached_top, descent_complete) -> RepVerdict:
        cyc, cfg = self._cycle, self.cfg
        v = RepVerdict(index=self.total + 1, min_elbow=cyc.min_elbow if cyc.min_elbow < 999 else None)
        v.chin = V.OK if reached_top else V.WRONG
        v.knee_r, v.knee_l = self._knee_status("r"), self._knee_status("l")
        v.thumb = self._thumb_status()
        v.complete = descent_complete
        if not reached_top:
            v.errors.append(V.ERR_CHIN)
        if v.knee_r == V.WRONG:
            v.errors.append(V.ERR_KNEE_R)
        if v.knee_l == V.WRONG:
            v.errors.append(V.ERR_KNEE_L)
        if v.thumb == V.WRONG:
            v.errors.append(V.ERR_THUMB)
        if not descent_complete:
            v.errors.append(V.ERR_CYCLE)
        # "Tekshirib bo'lmadi" — xato emas, faqat eslatma (taxmin qilib hukm chiqarilmaydi)
        if v.knee_r == V.UNKNOWN:
            v.notes.append("O'ng tizza tekshirib bo'lmadi")
        if v.knee_l == V.UNKNOWN:
            v.notes.append("Chap tizza tekshirib bo'lmadi")
        if v.thumb == V.UNKNOWN:
            v.notes.append(V.ERR_THUMB_UNKNOWN)
            if cfg.thumb_required:
                v.errors.append(V.ERR_THUMB_UNKNOWN)
        self.total += 1
        if v.valid:
            self.correct += 1
        else:
            self.wrong += 1
        for e in v.errors:
            self.error_stats[e] = self.error_stats.get(e, 0) + 1
        self.verdicts.append(v)
        self.last_errors = list(v.errors)
        self._cycle = _Cycle()
        self._emit("rep", v)
        return v

    def finish(self, t: Optional[float] = None):
        """Mashg'ulot tugadi: kutilayotgan takrorni yakunlaydi (3 s qoidasi shu vaqtgacha buzilmagan bo'lsa to'g'ri)."""
        if self.pending is not None:
            self._resolve_pending(t if t is not None else (self.bottom_since or 0.0))
