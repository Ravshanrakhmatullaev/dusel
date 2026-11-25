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

## 2. Qo'lda (har bir telefon va skaner, T−7 kun)

Sahifa: `https://feature-checkin.dusel.pages.dev/scan-test` (server yo'q, hech narsa yozilmaydi). Konsertdan oldin production'da `/scan-test` ham mavjud bo'ladi.

| # | Tekshiruv | iPhone Safari | Android Chrome | Izoh |
|---|---|---|---|---|
| D1 | Sahifa ochiladi, "HTTPS: ha", "Ilova ichidagi brauzer: yo'q" | | | Telegram ichida ochilsa — Safari/Chrome'da oching |
| D2 | Kamera so'rovi → "Ruxsat" → kamera ishlaydi | | | |
| D3 | Asl qog'oz bilet (yorug' zal, 20–30 sm) → "KONSERT BILETI № …" ≤ 1 s | | | |
| D4 | Xira yorug' / burchak ostida | | | |
| D5 | GOLD/SILVER/GAL kupon → "KUPON/VAUCHER" | | | |
| D6 | Ruxsatni rad etish → yo'riqnoma → sozlamadan yoqish → «Kamerani qayta yoqish» | | | |
| D7 | Bluetooth/USB skaner: 10 bilet ketma-ket → 10 natija | | | |
| D8 | Telefon klaviaturasi rus tartibida + skaner → baribir to'g'ri | | | |
| D9 | Qo'lda 5 raqam → to'g'ri | | | |
| D10 | Ekran qulfi → qaytish → kamera qayta ishlaydi | | | |
| D11 | «Hisobotni nusxalash» → natijani nazoratchiga yuborish | | | |

Tashqi skaner sozlamasi: HID klaviatura, US tartib, suffiks Enter. iPhone + Bluetooth skaner: skaner ulanganda ekran klaviaturasi yashiriladi — bu normal.

## 3. Ma'lum platforma xususiyatlari

- iOS: kamera faqat Safari (yoki iOS 14.3+ dagi boshqa brauzerlar) va HTTPS'da; ilova ichidagi brauzerlar (Telegram, Instagram) kamera bermaydi — ilova aniqlab, ko'rsatma beradi.
- iOS'da `BarcodeDetector` yo'q → jsQR ishlaydi (biroz sekinroq, lekin sinovda yetarli).
- Android Chrome: `BarcodeDetector` bor (tez).
- Kamera boshqa ilovada band bo'lsa (`NotReadableError`) — ilova shuni aytadi.
