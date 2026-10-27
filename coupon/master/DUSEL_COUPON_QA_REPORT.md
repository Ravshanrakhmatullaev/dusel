# DUSEL — GOLD & SILVER kupon tizimi · QA hisoboti

Sana: 2026-10-27 · Natija: **ma'lumot/QR/PDF 62/62 PASS** (barcha 6000 QR PDF ichidan dekod qilindi) · **veb 37/37 PASS**

## URL tuzilmasi

| Tur | URL | Diapazon | Soni |
|---|---|---|---|
| GOLD | `https://dusel.pages.dev/coupon?type=gold&code=NNNN` | 0001–2000 | 2000 |
| SILVER | `https://dusel.pages.dev/coupon?type=silver&code=NNNN` | 0001–4000 | 4000 |
| Bilet (o'zgarmagan) | `https://dusel.pages.dev/?code=NNNNN` | 00001–11222 | 11222 |

Kupon yo'li `/coupon` + 4 xonali raqam + `type`; bilet yo'li `/` + 5 xonali raqam. Kupon QR'i bilet sahifasini ochmaydi, bilet sahifasi 4 xonali kodni rad etadi (`/?code=0001` → "noto'g'ri").

## Tekshiruvlar

| # | Talab | Natija |
|---|---|---|
| 1 | Gold soni = 2000 | PASS (CSV, XLSX, PNG, SVG, ZIP, PDF layout) |
| 2 | Silver soni = 4000 | PASS |
| 3 | Gold raqamlash 0001–2000, 4 xonali | PASS (XLSX'da matn formatida, nollar saqlangan) |
| 4 | Silver raqamlash 0001–4000 | PASS |
| 5 | QR payload takrorlanmaydi | PASS — 6000 noyob URL, Gold ∩ Silver = 0 |
| 6 | Bilet URL'lari bilan konflikt yo'q | PASS — 11222 bilet URL ∩ 6000 kupon URL = 0; bilet master o'zgarmagan |
| 7 | Gold sahifalari ochiladi | PASS — 0001, 1000, 2000 ochiladi; 2001 → "Kupon topilmadi" |
| 8 | Silver sahifalari ochiladi | PASS — 0001, 4000 ochiladi; 4001, 0000, abc, turi yo'q → xato |
| 9 | Mobil layout | PASS — 320, 360, 390, 412, 768, 1366 px: gorizontal siljish yo'q, raqam birinchi ekranda; reduced-motion |
| 10 | Bosma previewlar | PASS — previewlar render qilindi va ko'zdan kechirildi |

### QR
- 6000 PNG (984×984 px, 300 dpi, 41 modul v4-M, 17 mm) — **hammasi** dekod qilindi va kutilgan URL'ga teng.
- SVG — har turdan 62 tadan namuna rasterlab dekod qilindi.
- ZIP: Gold 2000 SVG + 2000 PNG + master CSV; Silver 4000 + 4000 + CSV; `testzip` toza.

### Bosma PDF
- `DUSEL_COUPON_GOLD_PRINT.pdf` — 334 varaq; `DUSEL_COUPON_SILVER_PRINT.pdf` — 667 varaq; har biri 450×320 mm, 6 kupon (200×100 mm).
- Har varaqdagi bosma raqamlar (QR ostidagi "№:" va koreshokdagi "Kupon №:") layout bilan mos — barcha varaqlar.
- PDF ichidagi **barcha 6000 QR** 300 dpi'da render qilinib dekod qilindi — har biri o'z kupon raqamiga mos.
- Oxirgi varaq: Gold — 2 kupon (1999–2000), Silver — 4 kupon (3997–4000); bo'sh slotlar oq.
- Dizayn: o'zgaruvchi zonalardan tashqari proof varaq designer faylining sahifasi bilan pikselma-piksel bir xil (max farq 0).
- Shrift (Montserrat Bold) embed qilingan; OutputIntent: ISO Coated v2 (ECI) — designer faylidan; QR va raqamlar K100; kesish belgilari Registration.

### Veb (`/coupon`)
- 37/37 Playwright testi: Gold/Silver mavzulari, animatsiya (canvas zarrachalar) ishlaydi, bilet bloklari yo'q, xato holatlari, bilet sahifasi 00001/10001/11222 o'zgarmagan.
- Deploy: `main` 31185b6 — faqat `coupon.html`, `assets/coupon/*.webp`, README qo'shildi; `index.html` va `404.html` bayt-bayt o'zgarmagan. Cloudflare Pages: "Deploy successful".

## Ochiq masalalar
1. Designer faylidagi rasmlar RGB, ~200 ppi; fayl PDF/X emas — RGB→CMYK konvertatsiyani bosmaxona RIP'i qiladi. Bleed (vylet) yo'q: kuponlar bir-biriga tutash, kesish chizig'i bo'yicha.
2. Tirajdan oldin 1 varaqni bosib, telefon bilan QR skanerlash va kesishni sinash tavsiya etiladi.
3. Sahifa statik: kupon turi va raqamini ko'rsatadi, haqiqiyligini tasdiqlamaydi.
4. Production sahifani bu muhitdan to'g'ridan-to'g'ri ochib bo'lmadi (tarmoq cheklovi); tekshiruv bir xil fayllarda lokal + Cloudflare deploy statusi orqali.
