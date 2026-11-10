"""Mantiq testlari (4-8 bosqichlar): sintetik 30 FPS ketma-ketliklar bilan har bir qoida alohida tekshiriladi.
Ishga tushirish:  python tests_logic.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import settings as S
import validation as V
from pullup_counter import PullUpCounter
from validation import FrameMetrics

FPS = 30
HANDS_Y, SCALE = 0.30, 0.20
BAR_TOP = HANDS_Y - S.Settings().bar_top_offset * SCALE


class Sim:
    """Odamni modellashtiradigan generator: har bir kadr uchun FrameMetrics beradi."""

    def __init__(self, noise=0.0, seed=1, knee=(175.0, 175.0), thumb=(V.UNKNOWN, V.UNKNOWN)):
        self.c = PullUpCounter()
        self.t = 0.0
        self.noise = noise
        self.rng = random.Random(seed)
        self.knee = knee
        self.thumb = thumb
        self.events = []
        self.c.on_event = lambda k, p: self.events.append((k, p))

    def frame(self, elbow, chin_rel, knee=None, thumb=None, tracked=True):
        n = self.rng.gauss(0, self.noise) if self.noise else 0
        k = knee or self.knee
        th = thumb or self.thumb
        m = FrameMetrics(t=self.t, tracked=tracked, elbow_angle=elbow + n * 40 if tracked else None,
                         chin_y=(BAR_TOP - chin_rel * SCALE + n * 0.02) if tracked else None,
                         hands_y=HANDS_Y + n * 0.005, scale=SCALE,
                         knee_r=k[0], knee_l=k[1], thumb_r=th[0], thumb_l=th[1])
        self.t += 1 / FPS
        return self.c.update(m)

    def hold(self, sec, elbow, chin_rel, **kw):
        for _ in range(int(sec * FPS)):
            self.frame(elbow, chin_rel, **kw)

    def move(self, sec, e0, e1, c0, c1, **kw):
        n = max(1, int(sec * FPS))
        for i in range(n):
            f = (i + 1) / n
            self.frame(e0 + (e1 - e0) * f, c0 + (c1 - c0) * f, **kw)

    def hang(self, sec=1.5):
        self.hold(sec, 172, -1.2)

    def rep(self, top_rel=0.25, elbow_top=60, bottom_hold=1.0, pull_kw=None, down_full=True):
        pk = pull_kw or {}
        self.move(1.0, 172, elbow_top, -1.2, top_rel, **pk)
        self.hold(0.3, elbow_top, top_rel, **pk)
        self.move(1.0, elbow_top, 172 if down_full else 120, top_rel, -1.2 if down_full else -0.3, **pk)
        self.hold(bottom_hold, 172 if down_full else 120, -1.2 if down_full else -0.3, **pk)


results = []


def check(name, cond, info=""):
    results.append((name, bool(cond)))
    print(("  OK   " if cond else "  XATO ") + name + (f"  [{info}]" if info else ""))


def t_valid_reps():
    s = Sim()
    s.hang()
    for _ in range(5):
        s.rep()
    s.finish = s.c.finish(s.t)
    c = s.c
    check("5 ta toza tortilish -> 5 to'g'ri, 0 noto'g'ri", (c.total, c.correct, c.wrong) == (5, 5, 0),
          f"{c.total}/{c.correct}/{c.wrong}")


def t_chin():
    s = Sim()
    s.hang()
    s.rep(top_rel=-0.1, elbow_top=70)          # jag' turnikka yetmadi
    s.rep(top_rel=0.01, elbow_top=60)          # jag' ozgina o'tdi -> to'g'ri
    c = s.c
    check("1-qoida: jag' o'tmadi -> ERR_CHIN", c.verdicts and V.ERR_CHIN in c.verdicts[0].errors,
          str([v.errors for v in c.verdicts]))
    check("1-qoida: jag' o'tdi -> to'g'ri", len(c.verdicts) > 1 and c.verdicts[1].valid)
    s2 = Sim()
    s2.hang()
    s2.move(1, 172, 130, -1.2, -0.6)           # kichik harakat (tebranish), takror emas
    s2.move(1, 130, 172, -0.6, -1.2)
    s2.hold(1, 172, -1.2)
    check("Kichik tebranish takror emas", s2.c.total == 0, f"total={s2.c.total}")


def t_knee():
    s = Sim()
    s.hang()
    s.rep()
    s.rep(pull_kw={"knee": (120.0, 175.0)})    # o'ng tizza bukildi
    s.rep(pull_kw={"knee": (175.0, 130.0)})    # chap tizza bukildi
    v = s.c.verdicts
    check("2-qoida: o'ng tizza", len(v) == 3 and V.ERR_KNEE_R in v[1].errors and V.ERR_KNEE_L not in v[1].errors)
    check("2-qoida: chap tizza", len(v) == 3 and V.ERR_KNEE_L in v[2].errors and V.ERR_KNEE_R not in v[2].errors)
    s2 = Sim(knee=(None, None))
    s2.hang()
    s2.rep()
    v2 = s2.c.verdicts[0]
    check("Tizza ko'rinmasa: xato EMAS, 'tekshirib bo'lmadi'", v2.valid and v2.knee_r == V.UNKNOWN and v2.notes,
          str(v2.notes))
    s3 = Sim()
    s3.hang()
    s3.rep(pull_kw={"knee": (120.0, 175.0)} if False else None)
    # qisqa (3 kadr) shovqin tizzani xato qilmasligi kerak
    s3.move(1.0, 172, 60, -1.2, 0.25)
    for i in range(3):
        s3.frame(60, 0.25, knee=(120.0, 175.0))
    s3.hold(0.3, 60, 0.25)
    s3.move(1.0, 60, 172, 0.25, -1.2)
    s3.hold(1, 172, -1.2)
    check("Tizza bir lahzalik shovqini xato emas", all(V.ERR_KNEE_R not in v.errors for v in s3.c.verdicts))


def t_bottom_time():
    s = Sim()
    s.hang()
    s.rep(bottom_hold=2.5)
    s.rep(bottom_hold=4.0)
    s.rep(bottom_hold=1.0)
    s.c.finish(s.t)
    v = s.c.verdicts
    check("3-qoida: 2.5 s -> ruxsat", len(v) == 3 and v[0].valid)
    check("3-qoida: 4 s -> ERR_BOTTOM", len(v) == 3 and V.ERR_BOTTOM in v[1].errors)
    check("3-qoida: hisoblagich qayta tuzatildi (2 to'g'ri, 1 noto'g'ri)",
          (s.c.total, s.c.correct, s.c.wrong) == (3, 2, 1), f"{s.c.total}/{s.c.correct}/{s.c.wrong}")
    kinds = [k for k, _ in s.events]
    check("3-qoida: 'rep_revised' hodisasi", kinds.count("rep_revised") == 1)


def t_thumb():
    s = Sim(thumb=(V.UNKNOWN, V.UNKNOWN))
    s.hang()
    s.rep()
    v = s.c.verdicts[0]
    check("4-qoida: aniqlab bo'lmasa -> xato emas, eslatma", v.valid and v.thumb == V.UNKNOWN
          and V.ERR_THUMB_UNKNOWN in v.notes)
    s.rep(pull_kw={"thumb": (V.WRONG, V.UNKNOWN)})
    v = s.c.verdicts[1]
    check("4-qoida: bosh barmoq noto'g'ri (ishonchli) -> ERR_THUMB", V.ERR_THUMB in v.errors)
    s.rep(pull_kw={"thumb": (V.OK, V.OK)})
    check("4-qoida: ishonchli OK -> xato yo'q", s.c.verdicts[2].valid)


def t_cycle():
    s = Sim()
    s.hang()
    s.rep(down_full=False)                      # to'liq tushmadi, yana tortildi
    s.move(1.0, 120, 60, -0.3, 0.25)
    s.hold(0.3, 60, 0.25)
    s.move(1.0, 60, 172, 0.25, -1.2)
    s.hold(1, 172, -1.2)
    v = s.c.verdicts
    check("To'liq sikl: yarim tushish -> ERR_CYCLE", v and V.ERR_CYCLE in v[0].errors, str([x.errors for x in v]))
    check("Ikki marta sanalmaydi (jami 2 ta urinish)", s.c.total == 2, f"total={s.c.total}")


def t_noise():
    s = Sim(noise=0.35, seed=7)
    s.hang(2.0)
    for _ in range(6):
        s.rep()
    s.c.finish(s.t)
    check("Shovqin (sigma~14 daraja) bilan 6 takror aniq sanaladi", s.c.total == 6,
          f"total={s.c.total} correct={s.c.correct}")
    # aniqlash vaqtincha yo'qolishi (0.3 s) -> ta'sir qilmasligi kerak
    s2 = Sim()
    s2.hang()
    s2.move(1.0, 172, 60, -1.2, 0.25)
    for _ in range(9):
        s2.frame(0, 0, tracked=False)
    s2.hold(0.3, 60, 0.25)
    s2.move(1.0, 60, 172, 0.25, -1.2)
    s2.hold(1, 172, -1.2)
    check("0.3 s aniqlash uzilishi: takror saqlanadi", s2.c.total == 1 and s2.c.correct == 1,
          f"total={s2.c.total}")
    s3 = Sim()
    s3.hang()
    s3.move(1.0, 172, 60, -1.2, 0.25)
    for _ in range(90):                          # 3 s yo'qolish -> sikl bekor
        s3.frame(0, 0, tracked=False)
    check("3 s yo'qolish: sikl bekor, sanalmaydi", s3.c.total == 0 and s3.c.state == "READY")


def t_no_bar():
    s = Sim()
    for _ in range(5):                           # qo'llar hech cho'zilmaydi -> turnik noma'lum
        s.move(1.0, 130, 60, -1.2, 0.25)
        s.move(1.0, 60, 130, 0.25, -1.2)
    check("Turnik aniqlanmaguncha hukm chiqarilmaydi", s.c.total == 0 and not s.c.bar.ready,
          f"total={s.c.total}")
    s2 = Sim()
    s2.rep()                                     # 1-takror: turnik hali qulflanmagan
    s2.rep()
    check("Turnik qulflangach sanash boshlanadi (1-takror o'tib ketadi)", s2.c.bar.ready and s2.c.total == 1,
          f"total={s2.c.total}")


def t_states():
    s = Sim()
    s.hang()
    seen = []
    s.c.on_event = lambda k, p: None
    for e, c in [(172, -1.2)] * 10 + [(120, -0.8)] * 6 + [(60, 0.3)] * 8 + [(80, -0.3)] * 6 + [(172, -1.2)] * 6:
        seen.append(s.frame(e, c))
    order = [x for i, x in enumerate(seen) if i == 0 or x != seen[i - 1]]
    check("Holatlar ketma-ketligi", order == ["READY", "PULLING", "TOP", "DESCENDING", "BOTTOM"], str(order))


if __name__ == "__main__":
    for fn in (t_valid_reps, t_chin, t_knee, t_bottom_time, t_thumb, t_cycle, t_noise, t_no_bar, t_states):
        print(fn.__name__)
        try:
            fn()
        except Exception as e:  # test xatosini yashirmaymiz
            import traceback
            traceback.print_exc()
            results.append((fn.__name__ + " (istisno)", False))
    bad = [n for n, ok in results if not ok]
    print(f"\nJami: {len(results)} tekshiruv, muvaffaqiyatsiz: {len(bad)}")
    for b in bad:
        print("  -", b)
    sys.exit(1 if bad else 0)
