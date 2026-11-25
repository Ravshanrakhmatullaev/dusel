# 1–2. Production arxitekturasi va tarixiy QR moslik auditi

Sana: 2026-11-25 · Muallif: Claude (DUSEL check-in loyihasi)

## 1. Hozirgi production holati (tekshirildi)

| Qism | Holat |
|---|---|
| Sayt | Cloudflare Pages loyihasi `dusel`, production branch `main` (`d4f5576`), statik HTML, server kodi yo'q |
| Domen | `https://dusel.pages.dev` |
| Ommaviy yo'llar | `/` va `/ticket` (bilet), `/gold`, `/silver`, `/gal`, `/coupon` (eski kupon), neytral `404.html` |
| GitHub Pages | `gh-pages` branchi — `https://ravshanrakhmatullaev.github.io/dusel/` (eski bilet sahifasi, MAX=11222) |
| Repo | `Ravshanrakhmatullaev/dusel` — **ochiq (public)** |
| Monitoring | `.github/workflows/qr-uptime.yml` — kuniga 2 marta production yo'llarini tekshiradi |
| Server / baza | **Yo'q.** Hozirgacha hech qanday kirish nazorati yoki baza bo'lmagan |

Cloudflare Workers/D1 uchun API kaliti va hisob huquqi bu muhitda yo'q; D1 ni ishlatish uchun tashkilotchi Cloudflare'da baza yaratib, ulashi kerak bo'lardi.
Supabase (Postgres) esa hisobingizga ulangan — shuning uchun backend **Supabase Postgres + Auth** asosida qurildi:
transaksion, atomik `UPDATE … WHERE status='NOT_ADMITTED'`, qatorlarni qulflash, rol tekshiruvi serverda.
Mijoz bilet sahifalari Cloudflare'da qoladi va check-in serveri ishlamay qolsa ham ishlayveradi.

**To'siq:** Supabase hisobi bepul tarifda va 2 ta faol loyiha chegarasida (`poligrafiya`, `Vectorla`). Yangi loyiha yaratib bo'lmadi — tashkilotchi qarori kerak (Pro tarifi yoki bitta loyihani pauza qilish).

## 2. Tarixiy QR formatlari — qaysilari jismonan tarqatilgan

| # | QR ichidagi URL | Qayerda ishlatilgan | Dalil | Holat |
|---|---|---|---|---|
| A | `https://ravshanrakhmatullaev.github.io/dusel/?code=NNNNN` | 22-oktabr birinchi to'plam (10 000) va "final" bosqichi | git tarixi: 6 commit, birinchisi `5c3a544`; avvalgi tekshiruvda `QR_00330.png` dekodi | github.io'da ochiladi, raqam to'g'ri ko'rinadi; 25.11.2026 CI tekshiruvida (production-compat, 27/27) "tasdiqlanmagan" matni **topilmadi** |
| B | `https://dusel.pages.dev/?code=NNNNN` | V4–V6 bosmalar; **siz yuborgan `duseeeeeel_1.pdf` (1 871 varaq)** | PDF'dagi **11 222 / 11 222 QR dekod qilindi — hammasi shu format** | Production'da ishlaydi |
| C | `https://dusel.pages.dev/ticket?code=NNNNN` | V7 (3-noyabr) qayta yaratilgan fayllar | git `6d2b85d` | Production'da ishlaydi |

**Jismonan tarqatilgan biletlar** (fotosuratdagilar ham) — `duseeeeeel_1.pdf` dagi B formati. Ehtiyot uchun A va C ham to'liq qo'llab-quvvatlanadi.

Hammasi **bitta bilet yozuviga** tushadi: check-in serveri URL'dan faqat 5 xonali raqamni oladi (`00330`) — `/?code=00330`, `/ticket?code=00330`, `github.io/dusel/?code=00330` uchun **bitta holat** (testlarda T06, T17a tasdiqlangan).

### Ma'lumotlar mosligi
- Repo'dagi master (`production/DUSEL_MASTER_FINAL.csv`, sha256 `e50b9a…31bb`) va bosilgan `duseeeeeel_1.pdf` matnidagi **barcha 11 222 bilet** (raqam, BLITCHER/SEKTOR, sektor, qator, joy) **aynan bir xil — 0 farq**.
- PDF'da takroriy raqam ham, takroriy joy ham, takroriy QR ham yo'q (11 222 noyob QR).

## 3. Fotosuratdagi biletlar tahlili

| Biletda | Master bo'yicha | Xulosa |
|---|---|---|
| № 06114 · A403 · 2-qator · 2-joy — **2 ta bir xil** | 06114 = A403/2/2 | **Aynan nusxa** (raqam va QR bir xil) |
| № 06101 · A403 · 1-qator · 22-joy | 06101 = A403/1/22 | to'g'ri; bir nechta nusxa dastada |
| № 06087 · A403 · 1-qator · 8-joy | 06087 = A403/1/8 | to'g'ri |

PDF'da har varaqda 6 ta ketma-ket bilet bor → bosmaxona varaqni ikki marta bossa, **6 ta ketma-ket raqam** birga dublikat bo'ladi:
06114 → 1019-varaq (06109–06114), 06101 → 1017-varaq (06097–06102), 06087 → 1015-varaq (06085–06090).
"Turli raqam — bitta joy" holati fotosuratlarda **ko'rinmadi** va bosma faylda bunday holat yo'q.

A403 misoli: ajratilgan 320; tarqatilgan ~200 + qolgan ~180 = ~380 → ~60 ortiqcha qog'oz ≈ 10 ta varaq ikki marta bosilgan. Bu taxmin — aniq raqamni **inventar skaneri** beradi.

**Muhim:** bosilmay qolgan varaqlardagi raqamlar egasiz bo'lishi mumkin — lekin "inventarda yo'q" ≠ "bosilmagan" (tarqatilgan bo'lishi mumkin). Bunday joylar faqat tarqatish yozuvlari bilan tasdiqlangandan keyin zaxira joyga aylantiriladi.

## 4. Qilingan va qilinmagan ishlar (production'ga ta'sir)

- `main`, Cloudflare production, `gh-pages` — **o'zgartirilmagan**.
- Xodim ilovasi — `feature/checkin` (Cloudflare preview), backend — `checkin-backend` (saytga chiqmaydi).
- github.io uchun ikki variant tayyorlangan, **tasdiqsiz qo'llanmaydi**:
  1. `fix/githubio-ticket-forward` — github.io bilet raqamini `dusel.pages.dev/ticket?code=` ga uzatadi;
  2. tavsiya: `gh-pages` ga hozirgi soddalashtirilgan bilet sahifasini qo'yish (ikkala sayt bir xil ko'rinadi, github.io mustaqil ishlayveradi; CI bo'yicha hozir ham "tasdiqlanmagan" matni chiqmaydi).

## 5. Xavflar
- Repo ochiq: master (raqam → joy) ham ochiq. Soxta bilet chop etish osonlashadi; check-in baribir bitta raqamni bir marta kiritadi. Repo'ni yopish github.io (bepul GitHub Pages) ni o'chirib qo'yadi — A formatidagi QR'lar ishlamay qoladi. Shuning uchun hozir yopilmadi.
- Mavjud QR'lar ketma-ket va taxmin qilinadigan raqamlar — QR'dagi to'g'ri raqam biletning haqiqiyligini **isbotlamaydi**. Himoya: bir raqam — bir kirish, xodim logini, takror ogohlantirishi, inventar, tarqatish yozuvlari, audit.
