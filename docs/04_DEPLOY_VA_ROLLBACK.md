# 04 — Deploy va rollback

## 0. Tasdiq nuqtalari (egasining aniq ruxsatisiz bajarilmaydi)

| # | Amal | Holat |
|---|---|---|
| A1 | Supabase loyihasini tanlash (Pro / mavjud loyihani pauza / Cloudflare D1) | **kutilmoqda** — bepul tarifda 2 ta faol loyiha limiti to'lgan |
| A2 | Staging bazaga migratsiya + sinov xodimlari | A1 dan keyin, ruxsat shart emas (sinov ma'lumoti) |
| A3 | Production baza yaratish + 11 222 bilet seed | **ruxsat kerak** |
| A4 | `feature/checkin` → `main` merge (production `/checkin` paydo bo'ladi) | **ruxsat kerak** |
| A5 | `admission_open = true` (haqiqiy kirish) | **ruxsat kerak**, faqat konsert kuni |
| A6 | github.io bo'yicha o'zgarish (`fix/githubio-ticket-forward` yoki gh-pages yangilash) | **ruxsat kerak** |

Mijoz sahifalari (`index.html`, `ticket.html`, `404.html`), GOLD/SILVER/GAL sahifalari va ularning QR fayllari **hech qaysi bosqichda o'zgartirilmaydi**. `_headers` faqat `/checkin*` va `/assets/checkin/*` yo'llariga qo'llanadi.

## 1. Baza (Supabase)

1. Loyiha yaratish (mintaqa: Yevropa — Toshkentga yaqin), `pgcrypto` mavjud.
2. Migratsiyalar tartibda (SQL editor yoki MCP `apply_migration`):
   `sql/001_checkin_schema.sql` → `sql/002_checkin_functions.sql` → `sql/003_seed_tickets.sql` → `sql/004_settings_seed.sql`.
   `sql/local/*` **qo'llanmaydi** (u faqat lokal Supabase auth o'xshashi).
3. Tekshiruv:
   ```sql
   select count(*) from checkin.tickets;                          -- 11222
   select count(*) from checkin.tickets where status<>'NOT_ADMITTED'; -- 0
   select value from checkin.settings where key='master_sha256';  -- e50b9a59…31bb
   select value from checkin.settings where key='admission_open'; -- false
   ```
4. Production uchun `004` dagi `environment` qiymatini `PRODUCTION` ga o'zgartiring.
5. Auth → Settings: **ommaviy ro'yxatdan o'tishni o'chiring** (Disable signups). Xodimlar Auth → Users orqali qo'lda yaratiladi.
6. Birinchi Admin (SQL editorda, bir marta):
   ```sql
   insert into checkin.staff(user_id, username, display_name, role)
   select id, email, 'Bosh admin', 'ADMIN' from auth.users where email = '<admin email>';
   ```
   Qolgan xodimlar — ilovadagi Admin bo'limidan (`ci_staff_set`).
7. Advisors (Security) tekshiruvi: `checkin` sxemasidagi barcha jadvallarda RLS yoqilgan, `anon`/`authenticated` ga to'g'ridan-to'g'ri ruxsat yo'q; faqat `public.ci_*` funksiyalari `authenticated` uchun.

## 2. Frontend sozlamasi

`assets/checkin/config.js` ga faqat **publishable (anon) kalit** va URL yoziladi — bu kalit ochiq bo'lishi xavfsiz, chunki barcha ruxsatlar baza funksiyalarida tekshiriladi. `service_role` kaliti **hech qachon** frontendga qo'yilmaydi.

```js
var ENVS = {
  PRODUCTION: null,                                                   // A3/A4 dan keyin
  STAGING: { url: 'https://<staging-ref>.supabase.co', key: '<publishable key>' }
};
```
Qiymat `null` bo'lsa sahifa "faollashtirilmagan" deb ko'rsatadi — hech qanday so'rov yubormaydi.

## 3. Sayt

- Staging: `feature/checkin` ga push → Cloudflare avtomatik `https://feature-checkin.dusel.pages.dev/checkin` ni yangilaydi.
- Production (A4): PR `feature/checkin` → `main`. Merge'dan oldin CI (`checkin-ci.yml`) yashil bo'lishi, `production-compat` 27/27 bo'lishi shart. Merge'dan keyin yana `production-compat` ishga tushiriladi.

## 4. Zaxira nusxa (backup)

- Har migratsiya va konsert kunidan oldin/keyin:
  ```bash
  pg_dump "$DB_URL" -n checkin -Fc -f dusel_checkin_$(date +%Y%m%d_%H%M).dump
  ```
- Bepul Supabase tarifida avtomatik backup **yo'q**; Pro tarifida 7 kunlik kundalik backup bor. Konsert uchun Pro tavsiya etiladi.
- `audit_log`, `admission_events`, `inventory_scans` o'zgartirib/o'chirib bo'lmaydi (trigger) — dump ularni to'liq saqlaydi.

## 5. Rollback

| Muammo | Rollback |
|---|---|
| `/checkin` sahifasida xato (merge'dan keyin) | Cloudflare Pages → Deployments → oldingi deploy → "Rollback". Mijoz sahifalari o'zgarmagani uchun ta'sir yo'q |
| Frontendni butunlay o'chirish | `config.js` da `PRODUCTION: null` → sahifa so'rov yubormaydi |
| Kirishni zudlik bilan to'xtatish | Admin → "Kirishni yopish" (`admission_open=false`) |
| Funksiyada xato | `002` ning oldingi versiyasini qayta qo'llash (`create or replace` — ma'lumot o'chmaydi) |
| Ma'lumot buzildi | `pg_restore` bilan oxirgi dump'dan **alohida** bazaga tiklash, solishtirish, keyin qaror. Kirish yozuvlarini qo'lda o'chirish taqiqlanadi |

## 6. Sinov ma'lumotlari ajratilgani

- Haqiqiy biletlar hech qachon testda kiritilmaydi: barcha testlar lokal yoki CI'dagi **alohida** Postgres bazalarida (`ci_test`, `ci_load`, `ci_e2e`) ishlaydi va har safar noldan yaratiladi.
- Staging bazasi ham alohida loyiha; production bazasiga sinov skanlari yuborilmaydi.
- `production-compat` testi production saytni **faqat o'qiydi** (GET so'rovlar) — hech narsa yozmaydi.
