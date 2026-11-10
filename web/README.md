# TURNIK AI — telefon / brauzer versiyasi

Hech narsa o'rnatilmaydi: telefon brauzerida ochiladi, "Bosh ekranga qo'shish" bilan ilovaga aylanadi.
Video telefondan tashqariga chiqmaydi (AI brauzerning o'zida ishlaydi).

## Ishga tushirish (kamera uchun HTTPS shart!)
Brauzer kamerani faqat HTTPS (yoki localhost) sahifada ochadi. Eng oson yo'llar:
1. **Netlify Drop**: https://app.netlify.com/drop ga shu `web` papkani tashlang -> HTTPS havola beradi.
2. **GitHub Pages**: `web` papka mazmunini repoga yuklab, Pages'ni yoqing.
3. **Kompyuterda sinash**: `python -m http.server 8765` (papkada), keyin http://localhost:8765

Birinchi ochilishda internet kerak (MediaPipe WASM fayllari CDN'dan olinadi), keyin oflayn ishlaydi (service worker).

## Fayllar
index.html, style.css, app.js (kamera, AI, interfeys) · counter.js (qoidalar, Python mantig'ining nusxasi) ·
tests.html (27 ta mantiq testi: brauzerda oching, sarlavha PASS bo'lsin) · models/ · manifest.json, sw.js, icon-*.png

## Telefonni qo'yish
Telefon portret holatda, shtativda, turnikdan 2.5–3 m masofada, kamera ko'krak balandligida,
boshdan oyoqqacha va turnik kadrda. Yaxshi yorug'lik. Tashqi kamera ulansa, Sozlamalar > Kamera ro'yxatida chiqadi.
