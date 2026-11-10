# TURNIK AI

Kamera orqali turnikda tortilishlarni real vaqtda sanaydi va texnikasini tekshiradi.

## O'rnatish (Windows, Python 3.15 da sinalgan)

```powershell
python -m venv C:\Users\<siz>\turnik_venv
C:\Users\<siz>\turnik_venv\Scripts\python -m pip install -r requirements.txt
C:\Users\<siz>\turnik_venv\Scripts\python main.py
```

Modellar (`assets/models/`): `pose_landmarker_full.task`, `hand_landmarker.task` —
https://storage.googleapis.com/mediapipe-models/ (pose_landmarker/pose_landmarker_full/float16/latest va
hand_landmarker/hand_landmarker/float16/latest).

## Tayyor ilova (.exe)
`dist\TurnikAI\TurnikAI.exe` — Python o'rnatmasdan ishlaydi (butun `dist\TurnikAI` papkasini ko'chiring).
Tarix `%LOCALAPPDATA%\TurnikAI` da saqlanadi. Qayta yig'ish:

```powershell
python -m PyInstaller --noconfirm --clean --windowed --name TurnikAI --collect-all mediapipe --add-data "assets\models;assets\models" main.py
```

## Fayllar
| Fayl | Vazifasi |
|---|---|
| `main.py` | Ishga tushirish (`--gpu` ixtiyoriy) |
| `compat.py` | Python 3.15 + PySide6 tuzatmasi (PySide6 dan oldin import) |
| `settings.py` | Barcha chegaralar (burchaklar, vaqt, kadr sonlari) |
| `camera.py` | Kameralar ro'yxati, alohida oqimda o'qish |
| `pose_detection.py` | MediaPipe Pose + silliqlash + skelet |
| `hand_detection.py` | MediaPipe Hands + bosh barmoq baholash |
| `bar.py` | Turnik chizig'ini aniqlash/qulflash |
| `validation.py` | Burchaklar, jag' nuqtasi, xato matnlari |
| `pullup_counter.py` | Holat avtomati va hisoblash |
| `processor.py` | Konveyer: kadr -> AI -> qoidalar -> chizish |
| `database.py` | SQLite tarix |
| `ui/` | PySide6 interfeys (dark mode) |
| `tests_*.py` | Sinovlar |

## Sinovlar
`tests_stage2_camera.py` (kamera), `tests_logic.py` (23 ta qoida testi), `tests_models.py` (modellar, tezlik, DB), `tests_gui.py` (butun dastur).

## Cheklovlar (halol)
- **Turnik** MediaPipe'da yo'q: osilib turganda qo'llar markazi turnik deb olinadi. "Chiziq ↑/↓" bilan sozlang.
- **Jag' pastki nuqtasi** modelda yo'q: og'iz + quloqlar masofasidan *baholanadi* (`chin_offset_ratio`).
- **Bosh barmoq**: frontal kamerada ko'rinmaydi. Dastur faqat ishonchli dalil bo'lsa "noto'g'ri" deydi, aks holda
  "tekshirib bo'lmadi" (xato hisoblanmaydi). Ishonchli tekshiruv uchun **yon tomondan (turnikka perpendikulyar)
  ikkinchi kamera** kerak.
- **Tizza**: 3D (world) burchakdan hisoblanadi; oyoq kadrda ko'rinmasa — "tekshirib bo'lmadi".
- **3 s qoidasi**: takror pastga qaytganda darhol sanaladi; pastda 3 s dan oshsa noto'g'ri deb qayta tuzatiladi.
