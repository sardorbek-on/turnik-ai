"""Python 3.15 + PySide6 muvofiqlik tuzatmasi. Iloji boricha PySide6 dan OLDIN import qilinadi.

Aniqlangan muammo: PySide6 yuklangach concurrent.futures.ThreadPoolExecutor yechilmagan
'lazy_import' obyekti bo'lib qolishi mumkin va MediaPipe uni chaqirganda
"TypeError: 'lazy_import' object is not callable" xatosi chiqadi (PyInstaller .exe da ham).
Tuzatma: haqiqiy sinflarni modul lug'atiga to'g'ridan-to'g'ri joylaymiz.
"""
import concurrent.futures
import importlib

_SOURCES = {"ThreadPoolExecutor": "concurrent.futures.thread",
            "ProcessPoolExecutor": "concurrent.futures.process"}

for _name, _module in _SOURCES.items():
    setattr(concurrent.futures, _name, getattr(importlib.import_module(_module), _name))
