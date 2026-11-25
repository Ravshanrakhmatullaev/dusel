# 07 — Ma'lumotlar bazasi sxemasi va migratsiyalar

Sxema: `checkin` (Supabase Postgres). Barcha jadvallarda RLS yoqilgan, `public`/`anon`/`authenticated` ruxsatlari olib tashlangan. Ilova faqat `public.ci_*` SECURITY DEFINER funksiyalarini chaqiradi (`authenticated` roliga EXECUTE).

## Migratsiyalar

| Fayl | Mazmuni | Qayta qo'llash |
|---|---|---|
| `001_checkin_schema.sql` | jadvallar, cheklovlar, triggerlar, RLS | faqat yangi bazaga |
| `002_checkin_functions.sql` | barcha funksiyalar, ruxsatlar | xavfsiz (`create or replace`) |
| `003_seed_tickets.sql` | 11 222 joy + bilet, `master_sha256` | faqat bir marta |
| `004_settings_seed.sql` | sozlamalar, darvozalar G1–G4, VIP | xavfsiz: mavjud qiymatlarni o'zgartirmaydi (`on conflict do nothing`) |
| `005_print_sheets.sql` | har biletga bosma varaq/o'rin (`duseeeeeel_1.pdf`, 1 871 varaq) | xavfsiz; master bilan mos kelmasa — xato, hech narsa yozilmaydi |
| `local/000_local_supabase_stub.sql` | `auth.users`, `auth.uid()`, `auth.jwt()` o'xshashi | **faqat lokal/CI** |

`003` `tools/gen_seed.py` orqali `production/DUSEL_MASTER_FINAL.csv` dan yaratiladi (sha256 `e50b9a59…31bb`). Zonalar: 2-этаж → 2-qavat, 4-этаж → 4-qavat, Блитчеры → Blitcher (1-qavat).

## Jadvallar

| Jadval | Vazifa | Muhim cheklovlar |
|---|---|---|
| `settings` | `admission_open`, `block_held_stock`, `capacity`, `rate_limit_per_10s`, `event_label`, kontingensiya xeshi | sozlash faqat ADMIN, ro'yxatdagi kalitlar |
| `staff` | `auth.users` ↔ rol (INVENTORY/GATE/SUPERVISOR/ADMIN), `active`, `sessions_valid_after` | sessiya bekor qilinsa Supabase Auth sessiyalari va refresh tokenlar ham bekor |
| `gates` | darvozalar | `^[A-Z0-9_-]{1,20}$` |
| `seats` | `KIND:SECTOR:ROW:SEAT`, origin MASTER/EXTRA, zaxira holati | |
| `tickets` | `ticket_no` (5 xona) → bitta joy, kirish holati, `print_page/print_slot`, `retired_to_spare_at`, `superseded_by_case` | `seat_key` unique; `ADMITTED ⇔ admitted_at not null`; ADMITTED va CANCELLED — yakuniy (trigger); identifikator o'zgarmaydi; o'chirib bo'lmaydi |
| `review_cases` | nazorat holatlari | bilet uchun bitta ochiq holat (partial unique) |
| `replacements` | almashtirish biletlari | faqat `token_hash`; joy uchun bitta faol; trigger: joyda amaldagi asl bilet bo'lsa yoki ruxsatlar sig'imdan oshsa — INSERT rad |
| `capacity_changes` | tasdiqlangan sig'im o'zgarishlari (tashkilotchi qarori havolasi bilan) | o'zgarmas |
| `admission_events` | har bir kirish urinishi va qarori | `request_id` unique; o'zgartirib bo'lmaydi |
| `scan_log` | barcha skanlar (rate-limit uchun ham) | |
| `inventory_batches`, `inventory_scans`, `inventory_voids` | inventar sanash (partiya: sektor/quti/dasta/qurilma; skan: manba, qurilma, mijoz vaqti; noto'g'ri QR ham `ticket_no = null` bilan) | skanlar o'zgarmas, xato skan faqat "void" bilan; faqat INVENTORY rejimida yoziladi |
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

## Himoya triggerlari (funksiyalardagi xatoga qarshi ikkinchi qatlam)

| Trigger | Qoida |
|---|---|
| `settings_guard` | `capacity` faqat `ci_capacity_change`, `admission_open` faqat `ci_admission_set` orqali (tranzaksiya bayrog'i); aks holda `CAPACITY_LOCKED` / `ADMISSION_LOCKED` — superuser SQL ham |
| `tickets_guard` | ADMITTED/CANCELLED dan qaytish yo'q; kirish yozuvi va bilet identifikatori o'zgarmaydi |
| `replacements_guard` | band joyga yoki sig'imdan ortiq almashtirish yo'q; holatlar faqat ACTIVE → ADMITTED/CANCELLED |
| `mode_guard_*` | INVENTORY rejimida `tickets`, `admission_events`, `replacements`, `review_cases` ga yozish yo'q; `inventory_scans` ga faqat INVENTORY rejimida |
| `no_change_*` | `audit_log`, `admission_events`, `inventory_scans`, `inventory_voids`, `distribution_records`, `capacity_changes` — o'zgartirish/o'chirish yo'q |

## Sig'im modeli

`ruxsatlar = amaldagi asl biletlar (bekor qilinmagan) + bekor qilinmagan almashtirishlar ≤ tasdiqlangan sig'im (11 222)`.
- Isbotli zaxira (`ci_spare_from_stock`): asl bilet bekor (−1) → joy zaxirada → almashtirish (+1) = o'zgarmaydi.
- O'rnini bosuvchi almashtirish (`p_supersede = true`, asl hali kiritilmagan): asl bekor (−1), yangi QR o'sha joyda (+1).
- EXTRA joy (masterda yo'q): ruxsat qo'shmaydi; unga almashtirish faqat sig'imda bo'sh o'rin bo'lsa → aks holda `ESCALATED_NO_SEAT`.
- `ci_capacity_status.invariant_ok`: ruxsatlar ≤ sig'im va bir joyga bitta huquq.

## Yangi funksiyalar (2-bosqich)

`ci_admission_set`, `ci_capacity_change`, `ci_capacity_status`, `ci_spare_from_stock`, `ci_issue_replacement(…, p_supersede)`, `ci_inventory_report`, `ci_reconciliation`, `ci_reconciliation_sheets`, `ci_contingency_device_set`, `ci_contingency(p_device)`; yordamchi: `_live_copies`, `_recon_category`, `_pbkdf2_sha256`, `_kill_auth_sessions`.
