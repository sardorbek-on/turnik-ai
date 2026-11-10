"""3 va 7-bosqich: modellar yuklanadi, ishlaydi, tezlik o'lchanadi; DB sinovi; geometriya birlik testlari.
Odamsiz (qora) kadrda 'odam topilmadi' qaytishi KUTILADI. Haqiqiy odam bilan aniqlik alohida sinovda
(tests_live.py) tekshiriladi.
"""
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import settings as S
import validation as V
from database import Database
from hand_detection import Hand, HandDetector, analyze_thumb
from pose_detection import PoseDetector
from pullup_counter import PullUpCounter

ok_all = True


def check(name, cond, info=""):
    global ok_all
    ok_all &= bool(cond)
    print(("  OK   " if cond else "  XATO ") + name + (f"  [{info}]" if info else ""))


# --- geometriya ---
check("burchak 90", abs(V.angle_3pts((1, 0, 0), (0, 0, 0), (0, 1, 0)) - 90) < 1e-6)
check("burchak 180 (to'g'ri oyoq)", abs(V.angle_3pts((0, 1, 0), (0, 0, 0), (0, -1, 0)) - 180) < 1e-6)
check("burchak: nuqtalar ustma-ust -> None", V.angle_3pts((0, 0), (0, 0), (1, 1)) is None)

# --- modellar ---
rng = np.random.default_rng(0)
img = (rng.random((720, 1280, 3)) * 12).astype(np.uint8)
pd = PoseDetector(S.Settings())
hd = HandDetector()
check("Pose modeli yuklandi (CPU)", True, f"gpu={pd.gpu_active}")
r = pd.detect(img, 0)
check("Odamsiz kadr: pose None (yolg'on odam chiqarmaydi)", r.img is None)
check("Odamsiz kadr: qo'l topilmadi", hd.detect(img, 0) == [])
t0 = time.perf_counter()
N = 60
for i in range(1, N + 1):
    pd.detect(img, i * 33)
    hd.detect(img, i * 33)
dt = (time.perf_counter() - t0) / N * 1000
check("Pose+Hands bitta kadrga <= 40 ms (>=25 FPS)", dt <= 40, f"{dt:.1f} ms/kadr -> {1000 / dt:.0f} FPS (odamsiz kadr!)")

# --- bosh barmoq mantiqi (sintetik qo'l) ---
lm = np.zeros((21, 3), dtype=np.float32)
lm[0] = (0.5, 0.40, 0)
lm[9] = (0.5, 0.30, 0)           # hand_size = 0.10
lm[5] = (0.52, 0.31, 0)
lm[3] = (0.54, 0.20, 0)
lm[4] = (0.54, 0.15, 0)          # bosh barmoq turnik tepasidan (0.28) yuqorida
check("Bosh barmoq tepada ochiq -> WRONG", analyze_thumb(Hand(lm, 0.95, "Left"), 0.28, 0.30) == V.WRONG)
lm[4] = (0.54, 0.33, 0)
lm[3] = (0.54, 0.32, 0)
check("Bosh barmoq ko'rinmaydi/pastda -> UNKNOWN", analyze_thumb(Hand(lm, 0.95, "Left"), 0.28, 0.30) == V.UNKNOWN)
check("Qo'l topilmadi -> UNKNOWN", analyze_thumb(None, 0.28, 0.30) == V.UNKNOWN)
check("Ishonch past -> UNKNOWN", analyze_thumb(Hand(lm, 0.4, "Left"), 0.28, 0.30) == V.UNKNOWN)
pd.close()
hd.close()

# --- baza ---
with tempfile.TemporaryDirectory() as d:
    db = Database(Path(d) / "t.sqlite3")
    c = PullUpCounter()
    c.total, c.correct, c.wrong = 3, 2, 1
    c.error_stats = {V.ERR_CHIN: 1}
    sid = db.save_session(datetime.now(), 61.5, c)
    rows = db.list_sessions()
    check("DB: saqlash va o'qish", len(rows) == 1 and rows[0]["total"] == 3 and rows[0]["id"] == sid)
    db.delete_session(sid)
    check("DB: o'chirish", db.list_sessions() == [])
    db.close()

print("\n3/7-BOSQICH:", "OK" if ok_all else "MUAMMO BOR")
sys.exit(0 if ok_all else 1)
