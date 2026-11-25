# 12 — Haqiqiy qurilmalarda skaner sinovi

## 1. Avtomatik (CI, haqiqiy HTTPS)

`e2e/test_devices.mjs` — GitHub Actions'da `https://feature-checkin.dusel.pages.dev` (Cloudflare) ga qarshi:
- **WebKit + iPhone 15 profili** (Safari dvigateli) va **Chromium + Pixel 7 profili** (Android Chrome);
- eski QR'lar production'da shu qurilmada (faqat o'qish): `/?code=00330`, `/ticket?code=06114`, `github.io/dusel/?code=11222`;
- `/scan-test`: xavfsiz kontekst (HTTPS), Android'da soxta kamera orqali QR o'qish (05000), tashqi skaner (klaviatura) — kupon rad, kirill tartibidagi URL tiklanadi, 11223 rad;
- kamera ruxsati rad etilganda — iPhone uchun «aA → Veb-sayt sozlamalari → Kamera», Android uchun «qulf → Ruxsatlar → Kamera» yo'riqnomasi va «Kamerani qayta yoqish»;
- `/checkin`, `/inventory` haqiqiy Cloudflare CSP ostida JS xatosiz;
- HTTPS sarlavhalari: CSP, `Permissions-Policy: camera=(self)`, `Cache-Control: no-store`.

**Cheklov (halol):** emulyatsiya haqiqiy telefon emas — iOS Safari'ning kamera ruxsat oynasi, haqiqiy linza fokusi, yorug'lik va Bluetooth skaner juftlashuvi faqat qo'lda sinaladi.

## 2. Haqiqiy telefonlarda (staging tayyor bo'lgach) — protokol

**Material:** `docs/field_test/DUSEL_sinov_varaqasi.pdf` (A4, 4 varaq). Undagi bilet QR'lari **faqat STAGING'da** bilet (`&t=SINOV` / `DUSELTEST:`); production'da "YAROQSIZ QR" — chop etilgan varaq haqiqiy kirish bera olmaydi (baza testi T25). Kupon namunalari diapazondan tashqari (9999).

**Qurilmalar (kamida):** 2 × iPhone (iOS 17+, Safari), 2 × Android (Chrome), 1 × USB 2D skaner (OTG), 1 × Bluetooth 2D skaner. Hammasi `https://feature-checkin.dusel.pages.dev`.

| # | Sinov | Qadamlar | O'tish mezoni |
|---|---|---|---|
| F1 | Kamera ruxsati — birinchi marta | `/scan-test` ochish → so'rovga "Ruxsat" | kamera ishlaydi; "HTTPS: ha" |
| F2 | Ruxsat rad etilgan | sozlamadan kamerani o'chirib, sahifani qayta ochish | yo'riqnoma (iPhone: «aA»; Android: «Ruxsatlar») + «Kamerani qayta yoqish» ishlaydi |
| F3 | Ilova ichidagi brauzer | havolani Telegram'da ochish | "Safari/Chrome'da oching" ko'rsatmasi |
| F4 | Formatlar | 1-varaq, 9 ta QR | har biri "Kutilgan" bilan mos |
| F5 | Tezlik | 2-varaq, 24 bilet, tezkor rejim, taymer | ≥ 15 bilet/daqiqa (kamera), ≥ 30 (skaner); har biri bir marta yashil |
| F6 | **Bir vaqtda kiritish** | 3-varaq: 4 telefon bir biletni "3-2-1" bilan | har raqam uchun **aynan 1** yashil, 3 qizil "ALLAQACHON" |
| F7 | Aloqa uzilishi | KIRITISH bosilishi bilan samolyot rejimi | "NATIJA NOMA'LUM — KIRITMANG", yashil yo'q; qayta ulangach "Qayta urinish" → bitta yozuv |
| F8 | Wi-Fi ↔ mobil | skan paytida Wi-Fi o'chirish | ≤ 10 s ichida ishlashda davom etadi |
| F9 | Ekran qulfi | qulf → 1 daqiqa → ochish | kamera qayta ishlaydi (yoki «Kamerani qayta yoqish») |
| F10 | Tashqi skaner | USB va Bluetooth: 1–2-varaq | har skan bitta natija; telefon klaviaturasi kirill bo'lsa ham to'g'ri |
| F11 | Inventar takrori | 4-varaq (A, A, B) | A×2 → "o'sha qog'oz"; B → "ikkinchi qog'oz" → TASDIQLANGAN DUBLIKAT; Nazoratda belgi |
| F12 | Inventar oflayn | samolyot rejimida 10 skan → ilovani yopish → ulanish → ochish | 10 ta aynan bir martadan yuborildi |
| F13 | Batareya | 30 daqiqa uzluksiz skan | batareya sarfi yozib olinadi (powerbank rejasi uchun) |

Har sinovdan keyin `/scan-test` → «Hisobotni nusxalash» va natija jadvaliga: qurilma modeli, OS versiyasi, brauzer, natija, vaqt. Natija hisoboti: `docs/12_QURILMA_SINOVI_NATIJALARI.md` (staging'dan keyin to'ldiriladi).

## 3. Ma'lum platforma xususiyatlari

- iOS: kamera faqat Safari (yoki iOS 14.3+ dagi boshqa brauzerlar) va HTTPS'da; ilova ichidagi brauzerlar (Telegram, Instagram) kamera bermaydi — ilova aniqlab, ko'rsatma beradi.
- iOS'da `BarcodeDetector` yo'q → jsQR ishlaydi (biroz sekinroq, lekin sinovda yetarli).
- Android Chrome: `BarcodeDetector` bor (tez).
- Kamera boshqa ilovada band bo'lsa (`NotReadableError`) — ilova shuni aytadi.
