"""TURNIK AI — ishga tushirish:  python main.py [--gpu]"""
import sys

import compat  # noqa: F401  (PySide6 dan oldin bo'lishi shart)
from PySide6.QtWidgets import QApplication

import settings as S
from ui.main_window import MainWindow
from ui.styles import QSS


def main():
    missing = [p for p in (S.POSE_MODEL, S.HAND_MODEL) if not p.exists()]
    if missing:
        print("Model fayllari topilmadi:", *missing, sep="\n  ")
        print("README.md dagi 'Modellarni yuklash' bo'limiga qarang.")
        return 1
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = MainWindow(S.Settings(), use_gpu="--gpu" in sys.argv)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
