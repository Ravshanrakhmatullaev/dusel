# 04 — Deploy va rollback

## 0. Tasdiq nuqtalari va narx

To'liq ro'yxat, narx va production tartibi: **`11_PRODUCTION_ROLLOUT.md`** (P1–P7). Qisqasi: to'lov, production baza, `main`ga merge va kirishni ochish — faqat egasining aniq ruxsati bilan.

Mijoz sahifalari (`index.html`, `ticket.html`, `404.html`), GOLD/SILVER/GAL sahifalari va ularning QR fayllari **hech qaysi bosqichda o'zgartirilmaydi**. `_headers` faqat `/checkin*`, `/inventory*`, `/scan-test*`, `/assets/checkin|inventory|common/*` yo'llariga qo'llanadi.

## 1. Baza (Supabase)

1. Loyiha yaratish (mintaqa: Yevropa — Toshkentga yaqin), `pgcrypto` mavjud.
2. Migratsiyalar tartibda (SQL editor yoki MCP `apply_migration`):
   `sql/001_checkin_schema.sql` → `sql/002_checkin_functions.sql` → `sql/003_seed_tickets.sql` → `sql/004_settings_seed.sql` → `sql/005_print_sheets.sql`.
   `sql/local/*` **qo'llanmaydi** (u faqat lokal Supabase auth o'xshashi).
3. Tekshiruv:
   ```sql
   select count(*) from checkin.tickets;                          -- 11222
   select count(*) from checkin.tickets where status<>'NOT_ADMITTED'; -- 0
   select value from checkin.settings where key='master_sha256';  -- e50b9a59…31bb
   select value from checkin.settings where key='admission_open'; -- false
   ```
4. Production uchun `environment` = `PRODUCTION` (11-hujjat, 2.4). Kirish `false`, sig'im `11222` — ular qulflangan: faqat `ci_admission_set` va `ci_capacity_change` (tashkilotchining yozma qarori) o'zgartiradi.
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

- Har migratsiya va konsert kunidan oldin/keyin — **shifrlangan** (AES-256) va tekshirilgan:
  ```bash
  DB_URL='postgresql://…' PASSFILE=~/dusel_backup.pass ./tools/backup_encrypted.sh backups/
  ```
  Parol fayli ofline, 2 nusxa (tashkilotchi + texnik rahbar). Tiklash faqat alohida bazaga.
- Bepul Supabase tarifida avtomatik backup **yo'q**; Pro tarifida 7 kunlik kundalik backup bor. Konsert uchun Pro tavsiya etiladi.
- `audit_log`, `admission_events`, `inventory_scans` o'zgartirib/o'chirib bo'lmaydi (trigger) — dump ularni to'liq saqlaydi.

## 5. Rollback

| Muammo | Rollback |
|---|---|
| `/checkin` sahifasida xato (merge'dan keyin) | Cloudflare Pages → Deployments → oldingi deploy → "Rollback". Mijoz sahifalari o'zgarmagani uchun ta'sir yo'q |
| Frontendni butunlay o'chirish | `config.js` da `PRODUCTION: null` → sahifa so'rov yubormaydi |
| Kirishni zudlik bilan to'xtatish | Admin → "Kirishni yopish" (`admission_open=false`) |
| Funksiyada xato | `002` ning oldingi versiyasini qayta qo'llash (`create or replace` — ma'lumot o'chmaydi; qayta qo'llash xavfsizligi T22 testida) |
| Ma'lumot buzildi | `pg_restore` bilan oxirgi dump'dan **alohida** bazaga tiklash, solishtirish, keyin qaror. Kirish yozuvlarini qo'lda o'chirish taqiqlanadi |

## 6. Sinov ma'lumotlari ajratilgani

- Haqiqiy biletlar hech qachon testda kiritilmaydi: barcha testlar lokal yoki CI'dagi **alohida** Postgres bazalarida (`ci_test`, `ci_load`, `ci_e2e`) ishlaydi va har safar noldan yaratiladi.
- Staging bazasi ham alohida loyiha; production bazasiga sinov skanlari yuborilmaydi.
- `production-compat` testi production saytni **faqat o'qiydi** (GET so'rovlar) — hech narsa yozmaydi.

## 7. Tasdiqlangan sig'imni o'zgartirish (faqat tashkilotchining yozma qarori bilan)

Almashtirish bileti uchun sig'im **hech qachon** oshirilmaydi. Zalda haqiqatan qo'shimcha joy tasdiqlansa (masalan, arena ma'muriyatining yozma xati):
```sql
select public.ci_capacity_change(11224, 'Humo Arena xati №…, sana, imzolagan: …', 'SIGIM 11224');  -- Admin sessiyasidan (RPC)
```
Har o'zgarish `capacity_changes` (o'zgarmas) va audit jurnaliga yoziladi, Panelda ko'rinadi. Mavjud ruxsatlardan pastga tushirib bo'lmaydi.

## 8. Staging'ni tozalash
`CONFIRM=STAGING_RESET DB_URL=… ./tools/staging_reset.sh` — faqat `environment = STAGING` bazada ishlaydi (production'da o'zini to'xtatadi), xodimlar saqlanadi.
