# 11 — Nazoratli production rollout (kirish YOPIQ holatda) va narx

## 0. Narx (Supabase, 25.11.2026 holatiga — to'lovdan oldin supabase.com/pricing da qayta tekshiring)

Supabase hisob-kitobi **tashkilot (organization) bo'yicha**: tarif butun tashkilotga qo'llanadi, kompyut esa har bir loyiha uchun alohida, soatbay. Pro tarifida oyiga $10 kompyut krediti bor — u bitta Micro loyihani qoplaydi.

**Muhim:** mavjud tashkilotni (poligrafiya, Vectorla) Pro'ga o'tkazmang — u holda ularning ham kompyuti hisobga qo'shiladi. DUSEL uchun **yangi alohida tashkilot** oching; eski tashkilot Free bo'lib qoladi va loyihalarga tegilmaydi.

| Variant | Tarkib | Oyiga (taxminan) |
|---|---|---|
| **A (tavsiya)** | Yangi "DUSEL" Pro tashkiloti: production (Micro) + staging (Micro) — ikkalasi doimiy | $25 + $10 + $10 − $10 kredit = **$35** |
| B | Production (Micro) + staging Supabase *branch* sifatida faqat sinov kunlari | $25 + branch soatlari (Micro ≈ $0.01344/soat; masalan 15 kun ≈ $4.8) ≈ **$30** |
| Konsert kuni zaxira quvvat | Production'ni 1–2 kunga Small'ga ko'tarish | + ≈ $0.007/soat farq (juda kichik) |

Qo'shimcha: 8 GB disk, 250 GB trafik, 100 000 MAU tarifga kiradi — DUSEL (≈50 xodim, kichik baza) buning juda oz qismini ishlatadi. Pro: kundalik zaxira nusxa (7 kun), loyiha pauza qilinmaydi. Branch kompyuti kredit va spend cap bilan qoplanmaydi.

**Hech qanday to'lov yoki tarif o'zgarishi egasining aniq ruxsatisiz qilinmaydi.**

## 1. Tasdiq nuqtalari

| # | Amal | Kim tasdiqlaydi |
|---|---|---|
| P1 | Yangi Supabase tashkiloti + Pro tarifi (to'lov) | Egasi |
| P2 | Staging loyihasi (sinov ma'lumoti) — P1 dan keyin avtomatik | — |
| P3 | Staging'da barcha testlar + bulut yuklama + failover mashqi o'tdi | Texnik rahbar (hisobot) |
| P4 | Production loyihasi yaratish va **haqiqiy 11 222 bilet** yozish | Egasi |
| P5 | `feature/checkin` → `main` (production'da `/checkin`, `/inventory`, `/scan-test` paydo bo'ladi) | Egasi |
| P6 | Haqiqiy xodim akkauntlari | Egasi / Admin |
| P7 | **Kirishni ochish** — faqat 23.12.2026, darvozalar ochilishidan oldin | Egasi + Admin (ikki kishi) |

## 2. Production'ni tayyorlash (P4) — kirish YOPIQ

1. Loyiha: yangi tashkilotda, mintaqa — Toshkentga eng yaqin (Frankfurt yoki shunga o'xshash), Postgres 15+.
2. Auth: **Sign-ups o'chirilgan**, parol siyosati ≥ 12 belgi, email tasdiqlash yoqilgan; xodimlar Admin tomonidan qo'lda yaratiladi.
3. Migratsiyalar, tartib bilan (Supabase SQL editor yoki CLI; `sql/local/*` **qo'llanmaydi**):
   `001_checkin_schema` → `002_checkin_functions` → `003_seed_tickets` → `004_settings_seed` → `005_print_sheets`.
4. `004` dan keyin bir marta: `update checkin.settings set value='"PRODUCTION"' where key='environment';` (bu kalit qulflanmagan).
5. Tekshiruv SQL (natija aynan shunday bo'lishi shart):
   ```sql
   select count(*) from checkin.tickets;                                    -- 11222
   select count(*) from checkin.tickets where status <> 'NOT_ADMITTED';     -- 0
   select count(*) from checkin.admission_events;                           -- 0
   select count(*) from checkin.inventory_scans;                            -- 0
   select value from checkin.settings where key in ('admission_open','capacity','environment','master_sha256','print_layout_sha256');
   -- false, 11222, "PRODUCTION", e50b9a59…31bb, 3e35be16…13d4
   ```
6. Supabase Advisors (Security + Performance) — ogohlantirishlar yo'q yoki izohlangan.
7. Birinchi Admin (SQL editorda bir marta), qolgan xodimlar ilovadan.
8. Zaxira nusxa: `tools/backup_encrypted.sh` (shifrlangan, tekshiriladi) + Supabase kundalik backup.

## 3. Saytga chiqarish (P5) — kirish baribir YOPIQ

1. `assets/checkin/config.js` → `PRODUCTION: { url, key }` (faqat publishable kalit; `service_role` hech qachon).
2. PR `feature/checkin` → `main`; CI yashil; `production-compat` 27/27.
3. Merge'dan keyin darhol: `production-compat` qayta; `/checkin`, `/inventory`, `/scan-test` ochiladi; eski bilet QR'lari, GOLD/SILVER/GAL o'zgarmagan.
4. **Kirish avtomatik ochilmaydi**:
   - `004` kirishni `false` bilan yaratadi va mavjud qiymatni **o'zgartirmaydi** (`on conflict do nothing`);
   - `admission_open` ni faqat `ci_admission_set(true, 'KIRISHNI OCHISH')` o'zgartiradi (Admin, aniq tasdiq matni); boshqa funksiya, migratsiya yoki to'g'ridan-to'g'ri SQL o'zgartira olmaydi (trigger `ADMISSION_LOCKED`) — T20, T22 testlari;
   - deploy, migratsiyani qayta qo'llash, sahifa yangilanishi kirishni ochmaydi.

## 4. Konsert kuni (P7)

| Vaqt | Amal |
|---|---|
| T−3 soat | `monitor.mjs` ishga tushadi; darvoza telefonlari login; `/scan-test` tezkor tekshiruv; favqulodda qurilma belgilangan |
| T−2 soat | Shifrlangan backup; Panel: kiritilgan 0, ochiq holat 0, ruxsatlar 11 222 / 11 222 |
| T−30 daq | Egasi + Admin: **Kirishni ochish** (KIRISHNI OCHISH) |
| Konsert davomida | Panel va monitor; holatlar nazorat stolida |
| Darvozalar yopilgach | Kirishni yopish → backup → hisobotlar CSV → audit zanjiri tekshiruvi |

## 5. Orqaga qaytarish

- Sahifa xatosi: Cloudflare Pages → oldingi deploy (mijoz sahifalari o'zgarmagani uchun ta'sir yo'q).
- Kirishni zudlik bilan to'xtatish: Admin → "Kirishni yopish".
- Baza: kirish yozuvlari o'chirilmaydi/o'zgartirilmaydi; muammo bo'lsa — zaxiradan **alohida** bazaga tiklab solishtirish.
- Favqulodda SQL (faqat texnik rahbar, audit izi bilan): `begin; select set_config('checkin.admission_change','approved',true); update checkin.settings set value='false' where key='admission_open'; commit;`

Manbalar: https://supabase.com/pricing · https://supabase.com/docs/guides/platform/billing-on-supabase · https://supabase.com/docs/guides/platform/manage-your-usage/compute · https://supabase.com/docs/guides/platform/manage-your-usage/branching
