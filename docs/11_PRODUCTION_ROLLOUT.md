# 11 — Production'ga chiqarish: aniq ro'yxat va narx

Qaror: **alohida "DUSEL" Supabase Pro tashkiloti**, bitta production loyiha + vaqtinchalik, alohida **staging branch(lar)**. Mavjud `poligrafiya`, `Vectorla` tashkiloti/loyihalariga tegilmaydi.

## A. Narx taxmini (to'lovdan oldin supabase.com/pricing da qayta tekshiring)

| Qism | Hisob | Summa |
|---|---|---|
| Pro tarifi (DUSEL tashkiloti) | oyiga | $25.00 |
| Production kompyut (Micro, 730 soat × $0.01344) | ≈ $9.81, oylik $10 kredit qoplaydi | $0.00 |
| Konsert haftasida production → Small (7 kun) | 562 × 0.01344 + 168 × 0.0206 = $11.01 − $10 kredit | ≈ $1.01 |
| Staging branch (Micro, $0.01344/soat; kredit va spend cap **qoplamaydi**) | 14 kun doimiy = 336 soat | ≈ $4.52 |
| | butun oy doimiy = 730 soat | ≈ $9.81 |
| Disk (8 GB), trafik (250 GB), MAU (100 000) | tarifga kiradi; DUSEL ehtiyoji juda kichik | $0 |
| **Jami 1-oy** | staging 2 hafta | **≈ $30.5** |
| | staging butun oy | **≈ $36** |

Soliq/bank to'lovlari alohida bo'lishi mumkin. Branch soatbay hisoblanadi — sinov tugagach o'chirilsa, to'lov to'xtaydi.

## B. Tasdiq nuqtalari

| # | Amal | Tasdiq |
|---|---|---|
| **P1** | Yangi "DUSEL" tashkiloti + Pro tarifi | Egasi (to'lov) |
| **P2** | Production loyihasi + migratsiyalar (kirish YOPIQ, 0 kirish, 0 zaxira) | Egasi |
| **P3** | Staging branch (sinov ma'lumoti) | P1 dan keyin |
| **P4** | Inventarni boshlash (haqiqiy qog'ozlar) — production bazasida, `inventory-live` manzili orqali | Egasi |
| **P5** | `feature/checkin` → `main` merge | Egasi |
| **P6** | Haqiqiy xodim akkauntlari | Egasi / Admin |
| **P7** | **Kirishni ochish** — faqat 23.12.2026 | Egasi + Admin (ikki kishi) |

## C. Aniq ro'yxat

### C1. Tashkilot va loyiha (P1, P2)
- [ ] supabase.com → New organization "DUSEL" → **Pro** (eski tashkilotni o'zgartirmang).
- [ ] Spend cap: **yoqilgan** (branch kompyuti cap bilan qoplanmaydi — branchlarni qo'lda nazorat qiling).
- [ ] New project "dusel-checkin-prod", mintaqa: Toshkentga eng yaqin (Yevropa markaziy), kuchli DB paroli → parol menejeriga.
- [ ] Authentication → Sign In / Providers → Email: **Allow new users to sign up = O'CHIQ**; Confirm email = yoqilgan.
- [ ] Authentication → Policies: parol ≥ 12, harf+raqam (`supabase/config.jsonc` bilan bir xil).
- [ ] API → Exposed schemas: faqat `public` (`checkin` **ochilmaydi**).

### C2. Migratsiyalar (P2) — faqat `supabase/migrations` (= `sql/001–005`)
- [ ] SQL editor yoki `supabase db push` bilan tartibda: `…01_checkin_schema` → `…02_checkin_functions` → `…03_seed_tickets` → `…04_settings_seed` → `…05_print_sheets`.
- [ ] **Qo'llanmaydi**: `sql/local/*`, `e2e/seed_*.sql`, `tests/*` (sinov xodimlari/kirishlari).
- [ ] Bir marta (migratsiya emas): `update checkin.settings set value='"PRODUCTION"' where key='environment';`
- [ ] `tools/production_verify.sql` → **20 qatorning hammasi `OK`** (11 222 bilet va identifikator xeshi, 0 kirish, 0 hodisa, 0 almashtirish, 0 holat, **0 zaxira joy**, 0 EXTRA, sig'im 11 222, kirish YOPIQ, sinov xodimlari 0, RLS, anon huquqsiz, bootstrap faqat service_role, master va varaq sha256).
- [ ] Advisors → Security va Performance: ogohlantirishlar yo'q yoki izohlangan.

### C3. Xodimlar (P6)
- [ ] Admin noutbukida: `SUPABASE_URL=… SERVICE_ROLE_KEY=… node tools/create_staff.mjs staff.csv parollar.csv` (service_role kaliti faqat shu noutbukda; frontendga hech qachon).
- [ ] Production baza `@dusel.test`, `@test.local`, `load-…` akkauntlarini rad etadi (`TEST_ACCOUNT_IN_PRODUCTION`).
- [ ] Parollar shaxsan topshiriladi, `parollar.csv` o'chiriladi.
- [ ] Admin → **Tayyorlik tekshiruvi** → `TAYYOR`.

### C4. Staging branch (P3) — sinov uchun, production ma'lumotisiz
- [ ] Branch yaratish (Dashboard → Branches yoki MCP `create_branch`). **"Include data" O'CHIQ** — production ma'lumoti nusxalanmaydi; branch migratsiyalardan quriladi va `environment = STAGING` bo'ladi.
- [ ] `assets/checkin/config.js` → `STAGING: { url, key }` (branch publishable kaliti) → `feature/checkin` ga push → `https://feature-checkin.dusel.pages.dev`.
- [ ] Sinov xodimlari: `create_staff.mjs` (branch URL va branch service kaliti bilan).
- [ ] Bulut yuklama: repo secrets `STAGING_URL`, `STAGING_ANON_KEY`, `LOAD_GATES`, `LOAD_ADMIN` + variable `RUN_CLOUD_LOAD=1` → `checkin-backend` ga push → CI `cloud-load` job (natija artifact `cloud-load`).
- [ ] Jismoniy qurilma sinovi (12-hujjat, `docs/field_test/DUSEL_sinov_varaqasi.pdf`).
- [ ] Sinovlar tugagach: branch **o'chiriladi** (to'lov to'xtaydi). Branch ma'lumoti production'ga hech qachon ko'chirilmaydi.

### C5. Inventarni boshlash (P4) — kirish baribir YOPIQ
- [ ] `config.js` → `PRODUCTION: { url, key }`; Cloudflare'da `inventory-live` git branch (faqat shu commit) → `https://inventory-live.dusel.pages.dev/inventory` — bu manzilda **faqat inventar** ishlaydi (`/checkin` o'chirilgan); `main` o'zgarmaydi.
- [ ] Ilova sayt↔baza muhitini tekshiradi: production bazaga faqat production manzillari ulanadi (staging sayt production bazaga ulansa — "MUHIT MOS EMAS").
- [ ] Inventar xodimlari (INVENTORY roli) — 08-hujjat tartibi.

### C6. Saytga chiqarish (P5) — kirish YOPIQ
- [ ] PR `feature/checkin` → `main`; CI yashil: ommaviy sahifalar `main` bilan **bayt-ma-bayt bir xil** (CI tekshiradi), `production-compat` 27/27.
- [ ] Merge'dan keyin: `production-compat` qayta; eski QR'lar (`/?code=`, `/ticket?code=`, `github.io/dusel/?code=`), GOLD/SILVER/GAL o'zgarmagan.
- [ ] Production `/checkin` ochiladi, lekin **kirish YOPIQ** (migratsiya, deploy, sahifa yangilanishi uni ochmaydi — T20, T22).

### C7. Konsert kuni (P7)
- [ ] T−3 soat: `tools/monitor.mjs`; darvoza telefonlari login; `/scan-test`; favqulodda qurilma belgilangan.
- [ ] T−2 soat: `tools/backup_encrypted.sh`; Panel: kirgan 0, ruxsatlar 11 222 / 11 222; tayyorlik tekshiruvi (`no_admission_events` = OK).
- [ ] T−30 daq: Egasi + Admin → **KIRISHNI OCHISH**.
- [ ] Yakunda: kirishni yopish → backup → hisobotlar → audit zanjiri.

Manbalar: https://supabase.com/pricing · https://supabase.com/docs/guides/platform/manage-your-usage/compute · https://supabase.com/docs/guides/platform/manage-your-usage/branching · https://supabase.com/docs/guides/deployment/branching
