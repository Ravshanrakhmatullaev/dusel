# 07 — Ma'lumotlar bazasi sxemasi va migratsiyalar

Sxema: `checkin` (Supabase Postgres). Barcha jadvallarda RLS yoqilgan, `public`/`anon`/`authenticated` ruxsatlari olib tashlangan. Ilova faqat `public.ci_*` SECURITY DEFINER funksiyalarini chaqiradi (`authenticated` roliga EXECUTE).

## Migratsiyalar

| Fayl | Mazmuni | Qayta qo'llash |
|---|---|---|
| `001_checkin_schema.sql` | jadvallar, cheklovlar, triggerlar, RLS | faqat yangi bazaga |
| `002_checkin_functions.sql` | barcha funksiyalar, ruxsatlar | xavfsiz (`create or replace`) |
| `003_seed_tickets.sql` | 11 222 joy + bilet, `master_sha256` | faqat bir marta |
| `004_settings_seed.sql` | sozlamalar, darvozalar G1–G4, VIP | sozlamalarni qayta yozadi — production'da ehtiyot bo'ling |
| `local/000_local_supabase_stub.sql` | `auth.users`, `auth.uid()`, `auth.jwt()` o'xshashi | **faqat lokal/CI** |

`003` `tools/gen_seed.py` orqali `production/DUSEL_MASTER_FINAL.csv` dan yaratiladi (sha256 `e50b9a59…31bb`). Zonalar: 2-этаж → 2-qavat, 4-этаж → 4-qavat, Блитчеры → Blitcher (1-qavat).

## Jadvallar

| Jadval | Vazifa | Muhim cheklovlar |
|---|---|---|
| `settings` | `admission_open`, `block_held_stock`, `capacity`, `rate_limit_per_10s`, `event_label`, kontingensiya xeshi | sozlash faqat ADMIN, ro'yxatdagi kalitlar |
| `staff` | `auth.users` ↔ rol (GATE/SUPERVISOR/ADMIN), `active`, `sessions_valid_after` | |
| `gates` | darvozalar | `^[A-Z0-9_-]{1,20}$` |
| `seats` | `KIND:SECTOR:ROW:SEAT`, origin MASTER/EXTRA, zaxira holati | |
| `tickets` | `ticket_no` (5 xona) → bitta joy, kirish holati | `seat_key` unique; `ADMITTED ⇔ admitted_at not null` |
| `review_cases` | nazorat holatlari | bilet uchun bitta ochiq holat (partial unique) |
| `replacements` | almashtirish biletlari | faqat `token_hash`; joy uchun bitta faol |
| `admission_events` | har bir kirish urinishi va qarori | `request_id` unique; o'zgartirib bo'lmaydi |
| `scan_log` | barcha skanlar (rate-limit uchun ham) | |
| `inventory_batches`, `inventory_scans`, `inventory_voids` | inventar sanash | skanlar o'zgarmas, xato skan faqat "void" bilan |
| `distribution_records` | tarqatish ro'yxati (DISTRIBUTED/HELD/RETURNED) | o'zgarmas, import hammasi-yoki-hech narsa |
| `audit_log` | barcha amallar, sha256 xesh-zanjir | UPDATE/DELETE/TRUNCATE bloklangan |

## Atomar kirish

```sql
update checkin.tickets set status = 'ADMITTED', admitted_at = now(), ..., admit_request = p_request
 where ticket_no = $1 and status = 'NOT_ADMITTED' [and held-stock sharti]
returning *;
```
"O'qib, keyin yozish" ishlatilmaydi. Qator topilmasa — sabab aniqlanadi (allaqachon kiritilgan / to'xtatilgan / bekor). Bir xil `request_id` qayta kelsa — saqlangan natija qaytadi (`replay`).

## QR tahlili (`checkin._parse`)

Qabul qilinadi: `https?://dusel.pages.dev/[ticket|ticket.html|index.html]?code=NNNNN`, `https?://ravshanrakhmatullaev.github.io/dusel/[index.html]?code=NNNNN`, 5 xonali raqam (00001–11222), `DUSELR1:<24 belgi>` almashtirish tokeni. GOLD/SILVER/GAL/coupon → `FOREIGN`. Qolgan hammasi → `INVALID`.

## Audit zanjiri

`hash = sha256(prev_hash | id | at(UTC) | actor | action | entity | entity_id | details)`, `pg_advisory_xact_lock` bilan ketma-ket. `ci_audit_verify()` butun zanjirni qayta hisoblaydi va birinchi buzilgan yozuvni ko'rsatadi.
