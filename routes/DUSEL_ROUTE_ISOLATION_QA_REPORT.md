# DUSEL — yo'llar izolyatsiyasi: tashxis, yechim va QA

Sana: 2026-11-03 · Sayt branchi: `feature/gal-voucher` (PR #2, **merge qilinmagan**) · Production (`main`) o'zgarmagan

## 1. Tashxis — nega noto'g'ri sahifa chiqqan

| Topilma | Dalil |
|---|---|
| **Eng ehtimolli sabab: eski QR'lar eski saytga ishora qiladi.** Birinchi bilet to'plami (22-oktabr, 10 000 ta) va "final" bosqichi QR'lari `https://ravshanrakhmatullaev.github.io/dusel/?code=NNNNN` ga yozilgan. | `QR_00330.png` dekodi: `https://ravshanrakhmatullaev.github.io/dusel/?code=00330` |
| O'sha eski GitHub Pages sayti (`gh-pages` branch) hali ham joy kartalari va **"Joy ma'lumoti hali tasdiqlanmagan"** xabari bilan eski versiyani ko'rsatadi. | `gh-pages:index.html` 198-qator |
| Production `dusel.pages.dev` (`main`) da GAL sahifasi **umuman yo'q** — `https://dusel.pages.dev/?code=NNNNN` bilet QR'i production'da GAL sahifasini ocha olmaydi. GAL faqat preview manzilida. | `main` fayllari: index, coupon, 404 |
| Production `404.html` har qanday noma'lum yo'lni **bilet sahifasiga** (`/?code=invalid`) yuboradi — mahsulotlararo "tushib qolish". | `main:404.html` |
| Branch preview manzillari (`<branch>.dusel.pages.dev`) boshqa versiyalarni ko'rsatadi — test paytida chalkashlik manbai. | Cloudflare preview |

## 2. Yechim — har mahsulot o'z yo'lida

| Tizim | Yakuniy QR URL | Kod | Diapazon | Sahifa |
|---|---|---|---|---|
| Konsert bileti | `https://dusel.pages.dev/ticket?code=00001` | 5 xona | 00001–11222 | `ticket.html` |
| GAL vaucher | `https://dusel.pages.dev/gal?code=000001` | 6 xona | 000001–001000 | `gal.html` |
| GOLD kupon | `https://dusel.pages.dev/gold?code=0001` | 4 xona | 0001–2000 | `gold.html` |
| SILVER kupon | `https://dusel.pages.dev/silver?code=0001` | 4 xona | 0001–4000 | `silver.html` |

Qoidalar (kodda):
- Har sahifa faqat **o'z yo'li + o'z kod uzunligi + o'z diapazonini** qabul qiladi (`/^\d{5}$/` 1–11222; `/^\d{6}$/` 1–1000; `/^\d{4}$/` 1–2000 / 1–4000).
- Noto'g'ri kod → **o'sha sahifaning o'zida** "topilmadi" xabari. Hech qanday sahifa boshqa mahsulotga yo'naltirmaydi.
- `gold.html` va `silver.html` turini yo'ldan oladi; `type` parametri e'tiborga olinmaydi (`/gold?code=0001&type=silver` → GOLD).
- `404.html` — neytral "Sahifa topilmadi". Faqat **o'sha** yo'lning yozilish farqini to'g'rilaydi (`/GAL` → `/gal`, `/ticket/` → `/ticket`), boshqa mahsulotga yubormaydi.
- Bilet sahifasi dizayni o'zgarmagan (TEST NAMUNA / joy kartalari yo'q — production'dagi soddalashtirilgan versiya).

Eski havolalar (avval chop etilgan yoki tarqatilgan bo'lsa ishlashi uchun saqlandi — har biri **faqat o'z mahsuloti**):
- `https://dusel.pages.dev/?code=NNNNN` → faqat bilet (5 xona, 00001–11222)
- `https://dusel.pages.dev/coupon?type=gold|silver&code=NNNN` → faqat GOLD/SILVER
- `https://ravshanrakhmatullaev.github.io/dusel/?code=NNNNN` → **tayyorlandi, hali qo'llanmagan** (branch `fix/githubio-ticket-forward`): faqat bilet raqamini `https://dusel.pages.dev/ticket?code=NNNNN` ga uzatadi; noto'g'ri raqamda "Bilet topilmadi". Tasdiqingizdan keyin `gh-pages` ga qo'llanadi.

## 3. Qayta yaratilgan QR va bosma fayllar

| Tizim | Master | QR arxivi | Bosma | Nima o'zgardi |
|---|---|---|---|---|
| Bilet | `DUSEL_MASTER_FINAL.xlsx/.csv` — QR_URL `/ticket?code=` | `DUSEL_TICKET_QR_11222.zip` (11 222 SVG + PNG) | `DUSEL_FRONT_FINAL_CMYK.pdf` (1 871 varaq), `DUSEL_TEST_6UP.pdf` | faqat QR; dizayn, raqamlar va joy ma'lumotlari V6 bilan aynan bir xil (piksel farqi faqat QR maydonlarida). Orqa tomon (`DUSEL_BACK_6UP_SINGLE_PAGE_CMYK.pdf`) o'zgarmaydi |
| GOLD | `DUSEL_COUPON_GOLD_MASTER` — `/gold?code=` | `DUSEL_COUPON_GOLD_QR.zip` | `DUSEL_COUPON_GOLD_PRINT.pdf` (334 varaq), `_PROOF.pdf` | faqat QR |
| SILVER | `DUSEL_COUPON_SILVER_MASTER` — `/silver?code=` | `DUSEL_COUPON_SILVER_QR.zip` | `DUSEL_COUPON_SILVER_PRINT.pdf` (667 varaq), `_PROOF.pdf` | faqat QR |
| GAL | o'zgarmagan (`/gal?code=`) | o'zgarmagan | 200 × 100 mm 6-up — alohida hisobot `DUSEL_GAL_6UP_QA_REPORT.md` | joylash |

QR texnik: to'g'ridan-to'g'ri `https://dusel.pages.dev/...` havolalar, qisqartirgich yo'q. Bilet QR versiyasi va o'lchami avvalgidek (v3-M, 17 mm).

## 4. Testlar

### Sayt — 38/38 PASS (Playwright, Cloudflare Pages kabi lokal server)
- **To'g'ri:** `/ticket` 00001, 00330, 10000, 11222 + 16 tasodifiy; `/gal` 000001, 000100, 001000 + 12; `/gold` 0001, 2000 + 12; `/silver` 0001, 4000 + 12 → har biri faqat o'z sahifasi, to'g'ri raqam, boshqa mahsulot matni yo'q.
- **Noto'g'ri (o'sha sahifada xato, yo'naltirish yo'q):** `/ticket` 11223, 00000, 000005, 000001, 0001, 1, abcde, bo'sh, 99999, 1e3 · `/gal` 001001, 000000, 00001, 11222, 0001, 0000001, ABCDEF, bo'sh, 1 · `/gold` 2001, 0000, 00001, 000001, 4000, abcd, bo'sh, 1 · `/silver` 4001, 0000, 00001, 000001, 11222, abcd, bo'sh, 1.
- **Kesishuvlar:** `/gal?code=11222` → GAL xato (bilet emas) · `/ticket?code=000001` → bilet xato (GAL emas) · `/gold?code=4000` → GOLD xato · `/silver?code=2000` → SILVER · `/gold?code=0001&type=silver` → GOLD.
- **Eski havolalar:** `/?code=00001`, `/?code=11222` → faqat bilet; `/coupon?type=gold&code=0001`, `/coupon?type=silver&code=4000` → faqat kupon; `/?code=000001`, `/?code=0001` → xato (GAL/kupon ochilmaydi).
- **404:** `/GAL`, `/Ticket/`, `/GOLD`, `/silver/` → o'sha mahsulot; `/xyz`, `/tickets`, `/gal2`, `/coupon/gold`, `/assets/nope` → neytral, yo'naltirishsiz.
- **QR → sahifa:** har tizim arxividan 41–42 ta tasodifiy QR rasmi dekod qilinib, olingan URL ochildi → faqat o'sha mahsulot, raqam QR bilan bir xil.
- JavaScript xatolari yo'q.

### Ma'lumot va QR — 14/14 PASS
- Bilet 11 222 / GAL 1 000 / GOLD 2 000 / SILVER 4 000 — har biri takrorsiz, to'g'ri uzunlikda.
- **18 222 yakuniy URL — hammasi noyob**, tizimlar orasida kesishma 0; har tizim bitta alohida yo'lda.

### Bilet bosmasi — 10/10 PASS
- Master 11 222, 00001–11222, QR_URL `/ticket?code=`; joy ma'lumotlari V6 bilan aynan bir xil.
- QR arxivi: **11 222/11 222 PNG dekod qilindi**, payload aynan `/ticket?code=<raqam>`.
- `DUSEL_FRONT_FINAL_CMYK.pdf`: 1 871 varaq, 450 × 320 mm; **har varaqdagi barcha QR (11 222/11 222) 200 dpi'da dekod qilindi** va shu varaqda bosilgan raqamlarga mos; oxirgi varaqda 11221, 11222.

### GOLD/SILVER bosmasi — 62/62 PASS
- Barcha 6 000 QR PDF ichidan 300 dpi'da dekod qilindi — har biri o'z raqamiga va `/gold` yoki `/silver` yo'liga mos; dizayn designer fayli bilan piksel bo'yicha bir xil (o'zgaruvchi zonalardan tashqari).

### github.io uzatish sahifasi — 7/7 PASS (lokal)
- `?code=00330 / 00001 / 11222` → `https://dusel.pages.dev/ticket?code=…`; `11223 / 000001 / 0001 / bo'sh` → yo'naltirilmaydi.

## 5. Production'dan oldin (tasdiq kutilmoqda)
1. PR #2 → `main` (yangi yo'llar + GAL sahifasi + neytral 404).
2. `fix/githubio-ticket-forward` → `gh-pages` (eski github.io bilet QR'lari uchun).
3. Ommaviy bosish — yangi fayllar bilan, proof tasdiqlangandan keyin.
4. Eslatma: preview manzillarida (`feature-gal-voucher.dusel.pages.dev`) test qiling; production `dusel.pages.dev` da yangi yo'llar faqat merge'dan keyin ishlaydi.
