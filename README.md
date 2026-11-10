# TURNIK AI

Kamera orqali turnikda tortilishlarni real vaqtda sanaydigan va texnikasini tekshiradigan AI dastur.
Har bir tortilish qoidalar bo'yicha tekshiriladi, aniqlab bo'lmagan holatlarda taxminiy hukm chiqarilmaydi
("Tekshirib bo'lmadi" deb belgilanadi).

## Qoidalar
1. Jag' turnikning yuqori tekisligidan to'liq o'tishi kerak.
2. Tizzalar bukilmasligi kerak (3D burchak, son–tizza–to'piq).
3. Pastki holatda 3 soniyadan ortiq turmaslik.
4. Bosh barmoq turnikni pastdan o'rashi kerak (frontal kamerada faqat ishonchli dalil bo'lsa "noto'g'ri" deyiladi).

Holatlar: READY → PULLING → TOP → DESCENDING → BOTTOM (+ VALIDATION).

## Ikki versiya
| Papka | Nima | Qanday ishga tushiriladi |
|---|---|---|
| [`web/`](web/) | Telefon/brauzer versiyasi (PWA, JavaScript + MediaPipe Tasks) | HTTPS saytga joylang (GitHub Pages, Netlify) yoki `python -m http.server` bilan localhost |
| [`turnik_ai/`](turnik_ai/) | Windows desktop dastur (Python, OpenCV, MediaPipe, PySide6) | `pip install -r requirements.txt`, `python main.py` |

Ikkala versiyada ham qoidalar mantig'i bir xil. Batafsil: [`web/README.md`](web/README.md), [`turnik_ai/README.md`](turnik_ai/README.md).

## Holati (halol)
- Qoidalar mantig'i sintetik ketma-ketliklar bilan sinalgan (Python: 23, JavaScript: 27 test).
- Haqiqiy odam va haqiqiy turnikda aniqlik hali to'liq sinalmagan: bu sinov versiyasi.
- Turnik chizig'i qo'llar markazidan, jag' nuqtasi esa og'iz va quloqlar masofasidan baholanadi.
- Bosh barmoq holatini frontal kameradan ishonchli aniqlab bo'lmaydi; aniq tekshiruv uchun yon kamera kerak.

## Modellar
`pose_landmarker_full.task` va `hand_landmarker.task` — Google MediaPipe modellari
(https://ai.google.dev/edge/mediapipe), Apache 2.0 litsenziyasi.
