# 08 — A tizimi: jismoniy bilet inventari va solishtiruv

Ilova: `/inventory` (alohida sahifa, alohida rol **INVENTORY**). Sinov: `https://feature-checkin.dusel.pages.dev/inventory`.

## 1. Qat'iy ajratish (baza darajasida)

| | Inventar (`/inventory`) | Haqiqiy kirish (`/checkin`) |
|---|---|---|
| Rol | INVENTORY (+ SUPERVISOR, ADMIN) | GATE (+ SUPERVISOR, ADMIN) |
| API | `ci_inventory_*`, `ci_reconciliation*`, `ci_inventory_report` | `ci_lookup`, `ci_admit`, `ci_refer`, … |
| Yozadi | `inventory_scans`, `inventory_batches` | `tickets.status`, `admission_events`, `review_cases`, `replacements` |
| Bir QR ko'p marta | ha — nusxalar sanaladi | faqat bitta muvaffaqiyatli kirish |
| Oflayn | ha — qurilmada navbat (IndexedDB), idempotent | yo'q (faqat nazoratli favqulodda rejim, bitta qurilma) |
| Audit | `INVENTORY_*` | `ADMISSION_*`, `SUPERVISOR_ADMIT`, … |

Himoya qatlamlari:
1. **Rol**: GATE inventar funksiyalarini, INVENTORY kirish funksiyalarini chaqira olmaydi (`ROLE_DENIED`).
2. **Rejim trigger'i** (`checkin._mode_guard`): har funksiya tranzaksiya boshida `checkin.mode` ni belgilaydi. INVENTORY rejimida `tickets`, `admission_events`, `replacements`, `review_cases` ga har qanday yozuv **baza tomonidan rad etiladi**; `inventory_scans` ga esa faqat INVENTORY rejimida yozish mumkin.
3. **Statik tekshiruv** (T10g): inventar funksiyalari matnida kirish jadvallariga yozish kodi yo'qligi testda tekshiriladi.
4. **Supurish testi** (T10j): 11 737 inventar skani (barcha 11 222 bilet + dublikatlar + eski URL formatlari + kupon + almashtirish QR) — kirish holati, hodisalar, holatlar va almashtirishlar xeshi **o'zgarmadi**.

## 2. Ish tartibi

1. Admin INVENTORY rolidagi xodimlarni yaratadi (Supabase Auth → `ci_staff_set`).
2. Xodim `/inventory` → **Partiyalar** → yangi partiya: nomi, **sektor, quti, dasta**, joylashuv. Partiya xodimga biriktiriladi.
3. **Skanerlash**: telefon kamerasi, tashqi USB/Bluetooth 2D skaner (klaviatura rejimi — maydonni bo'sh qoldirib skanerlang) yoki qo'lda raqam.
   - Har skan darhol ko'rsatiladi: bilet, sektor/qator/joy, **bosma varaq raqami**, shu partiyada/jami nusxalar.
   - **Birinchi dublikat** paydo bo'lganda — qizil "BIRINCHI DUBLIKAT! № …" + uzun tebranish/ovoz.
   - Kupon/vaucher va noma'lum QR — alohida "rad etilgan skanlar" ro'yxatiga.
   - Qog'ozdagi joy QR'dagidan farq qilsa — "Joy izohi" ga yozing (joy ziddiyati hisobotiga tushadi).
4. Aloqa uzilsa: skanlar qurilmada saqlanadi ("Yuborilmagan: N"), sahifa yopilsa ham yo'qolmaydi; aloqa qaytgach **aynan bir martadan** yuboriladi (bir xil `request_id`).
5. Dasta tugagach — **Yopish** (yuborilmagan skan bo'lsa yopilmaydi). Faqat **yopilgan** partiyadagi skan "jismonan tasdiqlangan" hisoblanadi.
6. Xato skan — nazoratchi `ci_inventory_void` bilan bekor qiladi (o'chirilmaydi, izi qoladi).

## 2a. Takror skan ≠ ikkinchi qog'oz (operator qarori)

Bitta raqam ikkinchi marta skanerlansa, tizim buni **avtomatik nusxa deb hisoblamaydi** — bu shunchaki o'sha qog'ozni qayta skanerlash bo'lishi mumkin.

1. Ekranda sariq **"TAKROR SKAN № … — Qo'lingizda IKKI xil qog'oz bormi?"**.
2. Operator qog'ozlarni yonma-yon qo'yib tekshiradi:
   - **"YO'Q — o'sha qog'ozni qayta skanerladim"** → `SAME_PAPER`: nusxa hisoblanmaydi;
   - **"HA — qo'limda IKKINCHI qog'oz bor"** → ikkinchi qog'ozni **"DUBLIKAT" konvertiga** soladi va konvert raqamini yozadi → `SECOND_COPY`: tasdiqlangan 2-qog'oz, nazoratchiga **belgi** (`DUPLICATE_PRINT_CONFIRMED`) avtomatik ketadi;
   - **"Keyinroq"** → "Qarorlar" bo'limida qoladi (qarorsiz takror nusxa ham, zaxira ham hisoblanmaydi).
3. Operator faqat **o'z** skaniga va faqat **bir marta** qaror beradi; o'zgartirish faqat nazoratchi orqali, sabab bilan.
4. Hech bir skan o'chirilmaydi: barcha kuzatuvlar, qarorlar (kim, qachon, izoh) va bekor qilingan skanlar saqlanadi.
5. Hisoblash: `tasdiqlangan qog'ozlar = birinchi kuzatuv + SECOND_COPY takrorlar`. Qarorsiz takror bo'lgan varaq `REPEAT_UNVERIFIED`.

## 2b. Nazoratchi belgilari — bilet bekor qilinmaydi

Belgilar (`ticket_flags`) biletning holatini **o'zgartirmaydi**: bilet darvozada kiritilishi mumkin, faqat ogohlantirish ko'rinadi. Turlari:
- `DUPLICATE_PRINT_CONFIRMED` — inventarda ikkinchi qog'oz tasdiqlandi;
- `DISTRIBUTION_DISPUTED` — ikki diler bitta biletni da'vo qiladi yoki turli manbalar zid holat aytadi (bir manbaning o'z yangilanishi nizo emas);
- `DISTRIBUTED_BUT_IN_STOCK` — tarqatilgan deb yozilgan, lekin qog'oz zaxirada;
- `SEAT_MISMATCH`, `OTHER` (qo'lda).
Nazoratchi: ko'radi → "Holat ochish" (dalillar bilan ko'rib chiqish) → "Ko'rildi" / "Hal qilindi" (izoh majburiy). Belgisi bor bilet **zaxira joyga o'tkazilmaydi**.

## 2c. Boshlang'ich zaxira joy = 0
Yangi bazada tasdiqlangan zaxira joy **0**, EXTRA joy 0 (tayyorlik tekshiruvi `spare_pool_zero`). Noma'lum, skanerlanmagan, ortiqcha bosilgan yoki qarorsiz takrori bor qog'ozlar hech qachon avtomatik bo'sh joy bo'lmaydi.

## 3. Toifalar — "ko'rilmagan" ≠ "bosilmagan" ≠ "tarqatilgan"

Har bir bilet aynan bitta toifada:

| Toifa | Ma'nosi |
|---|---|
| `ADMITTED` | Konsertda kirgan |
| `DISTRIBUTED_CONFIRMED` | Tarqatish hujjatida DISTRIBUTED, inventarda yo'q |
| `IN_STOCK_CONFIRMED` | Hujjatda HELD/RETURNED **va** inventarda topilgan |
| `IN_STOCK_NO_RECORD` | Inventarda topilgan, lekin hujjat yo'q — **sotilmagan deb hisoblanmaydi** |
| `CONFLICT_DISTRIBUTED_BUT_IN_STOCK` | Hujjatda tarqatilgan, lekin qog'oz qo'lda — tekshirish kerak |
| `HELD_BUT_NOT_FOUND` | Hujjatda zaxirada, lekin topilmadi — yo'qolgan bo'lishi mumkin |
| `RETIRED_TO_SPARE` | Isbot bilan zaxira joyga o'tkazilgan (asl bilet bekor) |
| `CANCELLED` | Nazoratchi bekor qilgan |
| `UNKNOWN` | Ko'rilmagan va hujjat yo'q — tarqatilgan ham, yo'qolgan ham bo'lishi mumkin |

**Noma'lum (UNKNOWN, IN_STOCK_NO_RECORD) bilet hech qachon zaxira joy bo'lmaydi.** `ci_spare_from_stock` faqat: HELD/RETURNED hujjati + yopilgan partiyada **1** nusxa + varag'ida dublikat yo'q + darvozada hech qachon ko'rilmagan bilet uchun ishlaydi (T13h, T13i).

## 4. Varaq darajasidagi tahlil (6 bilet/varaq)

`duseeeeeel_1.pdf` — 1 871 varaq; har varaqda 6 ta ketma-ket bilet (oxirgisida 2 ta). Varaq/o'rin har bir biletga `005_print_sheets.sql` bilan yozilgan (11 222 qatorning har biri master bilan tekshiriladi).

| Varaq holati | Qoida |
|---|---|
| `REPRINTED_SUSPECTED` | Varaqdagi biror raqam 2+ nusxada topilgan → varaq **ikki marta bosilgan bo'lishi mumkin**. Bu 6 ta nusxaning hammasi mavjud degani EMAS |
| `FULL_SHEET_IN_STOCK` | 6 tasi ham qo'lda |
| `PARTIAL_SHEET_IN_STOCK` | bir qismi qo'lda |
| `SHEET_ACCOUNTED_OUTSIDE` | hammasi tarqatilgan (hujjat) yoki kirgan |
| `SHEET_NOT_FOUND_NO_RECORD` | hech biri ko'rilmagan va hujjat yo'q — **yo'qolgan varaq ehtimoli**, lekin tarqatilgan bo'lishi ham mumkin |
| `SHEET_NOT_FOUND_PARTIAL_RECORD` | ko'rilmagan, qisman hujjat bor |

Hisobotlar (CSV, Excel'da ochiladi — UTF-8 BOM, `;` ajratgich): sektorlar, varaqlar, ko'rilganlar, ko'rilmaganlar (toifasi bilan), dublikatlar, rad etilgan skanlar, barcha skanlar.

## 5. A403 — boshlang'ich hisobot (25.11.2026 holatiga, haqiqiy ma'lumot)

Manba: master (`DUSEL_MASTER_FINAL.csv`), `duseeeeeel_1.pdf` varaq tartibi, siz yuborgan rasmlar. **Inventar skani va tarqatish hujjati hali kiritilmagan**, shuning uchun hamma bilet hozircha `UNKNOWN`.

| Ko'rsatkich | Qiymat |
|---|---|
| Ajratilgan biletlar | **320** (№ 06080 – 06399) |
| Qatorlar | 1–2: 33 tadan · 3–8: 25 tadan · 9–10: 32 tadan · 11: 40 |
| Bosma varaqlar | **54** (1014–1067); 1014 A402 bilan (06079), 1067 A404 bilan (06400–06402) umumiy |
| Tasdiqlangan dublikat | **№ 06114** — 2 ta aynan bir xil nusxa (rasm) → varaq **1019** (06109–06114) `REPRINTED_SUSPECTED` |
| Ko'rilgan nusxalar (rasm) | № 06101 (varaq 1017: 06097–06102), № 06087 (varaq 1015: 06085–06090) |
| Sizning taxminingiz | ~200 tarqatilgan + ~180 qolgan ≈ 380 qog'oz → ~60 ortiqcha ≈ ~10 varaq ikki marta bosilgan (**taxmin, tasdiqlanmagan**) |
| Tarqatish hujjati | yo'q → 320 ta `UNKNOWN` |
| Zaxira joy sifatida ishlatish mumkin | **0** (isbot yo'q) |

Fayllar: `docs/reconciliation/A403_varaqlar_boshlangich.csv` (54 varaq × 6 o'rin, dalil ustuni), `docs/reconciliation/sektorlar_boshlangich.csv` (44 sektor: diapazon, varaqlar, umumiy varaqlar).

### A403 uchun keyingi qadamlar (staging/production tayyor bo'lgach)
1. A403 qoldiq qog'ozlarini dastalar bo'yicha partiyalarga skanerlash (quti/dasta yozilsin), partiyalarni yopish.
2. Distribyutorlarga berilgan A403 biletlar ro'yxatini (raqam bo'yicha) CSV bilan import (`DISTRIBUTED`), tashkilotchida qolganlari (`HELD`). Taxminiy ma'lumot kiritilmaydi.
3. `Solishtiruv` → A403: dublikat raqamlar, `REPRINTED_SUSPECTED` varaqlar, `SHEET_NOT_FOUND_NO_RECORD` varaqlar, `CONFLICT_DISTRIBUTED_BUT_IN_STOCK`.
4. Har bir shubhali varaq bo'yicha bosmaxona bilan solishtirish (bosma jurnali, chiqitga chiqarilgan varaqlar).

Sinov ma'lumotlari bilan to'liq oqim E2E testda (T10, T10o, T21) va baza testida (T21, A405 sintetik) tekshirilgan.
