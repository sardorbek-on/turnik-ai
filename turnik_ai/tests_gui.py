"""9/10-bosqich: butun dastur (GUI + kamera + AI) ~8 soniya ishlatiladi, START/STOP sinaladi, skrinshot saqlanadi."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import compat  # noqa: F401
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import settings as S
from ui import main_window as MW
from ui.styles import QSS

errors, infos, dialogs = [], [], []
MW.ResultsDialog.exec = lambda self: dialogs.append(self) or 0     # modal oynani bloklamaymiz
MW.QMessageBox.critical = staticmethod(lambda *a: errors.append(a[2]))

app = QApplication(sys.argv)
app.setStyleSheet(QSS)
win = MW.MainWindow(S.Settings())
win.worker.frame_ready.connect(lambda img, info: infos.append(info))
win.worker.status.connect(lambda m: print("  status:", m))
win.resize(1360, 820)
win.show()
out = Path(__file__).parent / "data"
out.mkdir(exist_ok=True)


def step(n):
    if n == 0:
        win.toggle_camera()
    elif n == 1:
        win.start()
    elif n == 6:
        win.grab().save(str(out / "gui_screenshot.png"))
    elif n == 7:
        win.stop()
    elif n == 8:
        app.quit()


for i in range(9):
    QTimer.singleShot(1000 + i * 1000, lambda i=i: step(i))
app.exec()
win.close()

n = len(infos)
fps = [x["fps"] for x in infos if x["fps"] > 0]
print(f"Kadrlar: {n}; oxirgi FPS (to'liq konveyer, GUI bilan): {fps[-1] if fps else 0:.1f}")
print("Holatlar:", sorted({x['state'] for x in infos}), "| counting:", any(x["counting"] for x in infos))
print("Dialoglar (STOP natijasi):", len(dialogs), "| xatolar:", errors)
assert not errors, errors
assert n > 30, "kadrlar deyarli kelmadi"
assert fps and fps[-1] >= 20, "FPS past"
assert len(dialogs) == 1, "STOP natija oynasini ko'rsatmadi"
print("GUI SINOVI: OK (texnik ishlash). Aniqlik uchun odam kerak — kamera hozir qora.")
