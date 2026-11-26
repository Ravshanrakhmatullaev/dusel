# 14 — P1 → P4: aniq ish tartibi (tasdiqlarni kutayotgan holat)

Holat (26.11.2026): hammasi tayyor; **to'lov, production ma'lumoti, merge va kirish ochilishi — faqat egasining tasdig'i bilan.** P5 (merge) va P7 (kirishni ochish) uchun ruxsat **yo'q**.

---

## P1 — Alohida "DUSEL" tashkiloti va Pro tarifi (egasi bajaradi, to'lov)

Supabase ulagichi tashkilot yarata olmaydi va to'lov qila olmaydi — bu qadamlar faqat sizning akkauntingizda:

1. https://supabase.com/dashboard → yuqori chap: tashkilot nomi → **New organization**.
2. Name: `DUSEL`, Type: Company, Plan: **Pro** → to'lov kartasi → **Create organization**.
   - Mavjud tashkilot (poligrafiya, Vectorla turgan) **tanlanmaydi va o'zgartirilmaydi** — u Free bo'lib qoladi.
3. DUSEL → **Billing**: Spend cap = **ON** (kutilmagan ortiqcha xarajat yo'q). Eslatma: branch kompyuti spend cap va oylik $10 kredit bilan qoplanmaydi — branchni sinovdan keyin o'chiramiz.
4. DUSEL → **Team**: faqat zarur odamlar (siz + texnik rahbar), 2FA yoqilgan.
5. Menga yozing: "P1 tayyor". Men **faqat o'qiyman**: `list_organizations` → DUSEL ni topaman, `get_organization` → tarif = Pro ekanini tasdiqlayman; eski tashkilotga tegilmaydi.

Narx (taxmin, 11-hujjat): oyiga $25 + production Micro ($10 kredit qoplaydi) + staging branch ~$0.0134/soat (2 hafta ≈ $4.5) → **1-oy ≈ $30–36**.

## P2 — Production bazasi (tasdiqingiz bilan; kirish YOPIQ, admission = 0, spare = 0)

Men bajaraman (Supabase ulagichi orqali; loyiha yaratishda xarajat tasdig'i so'raladi — siz tasdiqlaysiz):
1. `create_project` — tashkilot: **DUSEL**, nomi `dusel-checkin-prod`, mintaqa `eu-central-1` (Frankfurt). `ACTIVE_HEALTHY` bo'lguncha kutish.
2. Migratsiyalar `apply_migration` bilan, tartibda (hammasi 1 MB chegarasidan kichik):
   | Fayl | Hajm |
   |---|---|
   | `…01_checkin_schema.sql` | 23 KB |
   | `…02_checkin_functions.sql` | ~120 KB |
   | `…03_seed_tickets.sql` | 294 KB (ixcham; avvalgi 1.34 MB bilan natija bir xil — xesh tekshirilgan) |
   | `…04_settings_seed.sql` | <1 KB |
   | `…05_print_sheets.sql` | 437 KB |
3. Bir martalik SQL: `environment = "PRODUCTION"`.
4. `tools/production_verify.sql` → **20/20 OK** shart. Ular orasida: 11 222 bilet va ularning identifikator xeshi (`1cf5c18d…`), master va varaq xeshlari, **hamma bilet NOT_ADMITTED, kirish hodisalari 0, zaxira joy 0, EXTRA 0, kirish YOPIQ**, sig'im 11 222, sinov xodimlari 0, RLS, anon/authenticated jadvallarga kira olmaydi, bootstrap faqat service_role.
   (Bu tekshiruv lokal'da Supabase standart huquqlari taqlid qilingan holda 20/20 o'tgan.)
5. `get_advisors` (security, performance) — natijani sizga yuboraman.
6. Admin akkaunti: siz `tools/create_staff.mjs` ni o'z noutbukingizda service_role kaliti bilan ishga tushirasiz (kalit menga va frontendga berilmaydi). Faqat ADMIN va SUPERVISOR — inventar xodimlari P4 da.
7. Sayt **o'zgarmaydi**: `config.js` dagi `PRODUCTION` hali `null`; `main` ga tegilmaydi.

## P3 — Staging (P2 dan keyin; branch xarajati tasdig'i bilan)

1. `create_branch` (production loyihasidan, nomi `staging`) — **ma'lumotsiz**: migratsiyalardan quriladi, `environment = STAGING`, 0 kirish.
2. `tools/staging_setup.sql` (faqat STAGING'da ishlaydi): darvozalar L1–L32, rate limit 200.
3. Xodimlar: `create_staff.mjs tools/staging/staging_staff.csv` (9 ta) va `tools/staging/load_staff.csv` (32 ta yuklama darvozasi, `LOAD_GATES_OUT=…` → GitHub secret).
4. `config.js` → `STAGING: { url, key }` (branch publishable kaliti) → `feature/checkin` ga push → `https://feature-checkin.dusel.pages.dev`.
5. GitHub secrets/variables: `STAGING_URL`, `STAGING_ANON_KEY`, `STAGING_ACCOUNTS`, `LOAD_GATES`, `LOAD_ADMIN`; `RUN_STAGING_SMOKE=1`, `RUN_CLOUD_LOAD=1`.
6. Sinovlar:
   | # | Sinov | O'tish mezoni |
   |---|---|---|
   | S | `staging-smoke` (HTTPS, 4 rol) | 7/7 |
   | L1 | Bulut yuklama, haqiqiy sur'at (`LOAD_PACE_MS=3000`, 32 darvoza) | p95 `ci_admit` < 1 s, xato < 0.5%, ikki marta kirish 0 |
   | L2 | Eng og'ir payt ×3 (`1000`) | p95 < 1.5 s, xato < 1% |
   | L4 | Poyga (20 mijoz) | aynan 1 |
   | F1–F13 | Telefonlar (`DUSEL_sinov_varaqasi.pdf`, 12-hujjat): kamera ruxsati, tezlik, 4 telefon bir vaqtda, aloqa uzilishi, tashqi skaner, inventar takrori/konvert, oflayn navbat | har biri o'tdi, bayonnoma imzolangan |
   | N | Zalda tarmoq (09-hujjat F1–F10): failover, UPS | o'tdi |
7. Har sinov to'plamidan keyin `tools/staging_reset.sh` (faqat STAGING). Sinovlar tugagach — branch o'chiriladi.

## P4 — Haqiqiy inventar (faqat P3 muvaffaqiyatli + sizning tasdig'ingiz)

**Ochish sharti (hammasi bajarilishi kerak):**
- [ ] P3 jadvalidagi barcha sinovlar o'tdi va natijalar sizga yuborildi.
- [ ] Production `production_verify.sql` qayta 20/20 OK.
- [ ] Siz yozma ravishda "P4 ruxsat" dedingiz.

Keyin:
1. INVENTORY rolidagi haqiqiy xodimlar (`create_staff.mjs`, production; sinov akkauntlari rad etiladi).
2. `config.js` → `PRODUCTION: { url, key }` faqat `inventory-live` git branch'ida → `https://inventory-live.dusel.pages.dev/inventory`. Bu manzilda **`/checkin` o'chirilgan**; `main` va `dusel.pages.dev` o'zgarmaydi.
3. Kirish YOPIQ qoladi (`admission_open = false` qulflangan).
4. Birinchi kun: A403 dan boshlab, partiyalar sektor/quti/dasta bo'yicha.

## Dublikat qog'ozlar — alohida konvertlarda, raqamlari tizimda

1. Takror skan → operator qog'ozlarni solishtiradi. Ikkinchi qog'oz bo'lsa → **"HA"** → ilova ochiq konvertni ko'rsatadi (yo'q bo'lsa yangisini ochadi: **D-001, D-002 …**) → qog'oz shu konvertga solinadi.
2. Tizim har konvertdagi **bilet raqamlari, sektor, qator, joy, varaq, kim va qachon** solganini saqlaydi (`ci_envelope_contents`, CSV "envelopes").
3. **Muhrlash**: qog'ozlar qo'lda sanaladi; son tizimdagi bilan teng bo'lmasa muhrlanmaydi. Muhrdan keyin konvertga qo'shib bo'lmaydi va ichidagi qarorlarni o'zgartirib bo'lmaydi.
4. **Yorliq** chop etiladi (kod, son, raqamlar ro'yxati, imzo joylari) va konvertga yopishtiriladi.
5. **Topshirish** (faqat nazoratchi/admin): kimga (ism, lavozim, seyf) — tizimda yoziladi.
6. Har bir ikkinchi qog'oz nazoratchiga **belgi** sifatida tushadi; asl bilet **bekor qilinmaydi**.

## O'zgarmaydigan narsalar
- 11 222 ta eski QR (`/?code=`, `/ticket?code=`, `github.io/dusel/?code=`) va GOLD/SILVER/GAL sahifalari — CI har push'da `main` bilan bayt-ma-bayt solishtiradi va production'ni faqat o'qib tekshiradi (27/27).
