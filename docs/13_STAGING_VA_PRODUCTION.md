# 13 — Staging va production qat'iy ajratilgan

| | Staging (branch) | Production |
|---|---|---|
| Baza | Supabase branch, **ma'lumotsiz** yaratiladi ("Include data" o'chiq), migratsiyalardan quriladi | alohida loyiha, migratsiyalardan quriladi |
| `environment` | `STAGING` (004 standarti) | `PRODUCTION` (bir martalik qo'lda SQL) |
| Sayt | `feature-checkin.dusel.pages.dev` | `dusel.pages.dev` (+ ixtiyoriy `inventory-live.dusel.pages.dev` — faqat inventar) |
| Sinov QR (`&t=SINOV`, `DUSELTEST:`) | bilet sifatida ishlaydi | **yaroqsiz** (kirishda ham, inventarda ham) |
| Sinov xodimlari | mumkin | baza rad etadi (`TEST_ACCOUNT_IN_PRODUCTION`) |
| Sinov kirishlari | mumkin; `tools/staging_reset.sh` bilan tozalanadi | yo'q (tayyorlik tekshiruvi `no_admission_events`) |
| Ko'chirish | — | staging'dan production'ga **hech qanday ma'lumot ko'chirilmaydi**; faqat migratsiya fayllari |

Himoyalar:
1. **Sayt ↔ baza muhiti**: ilova serverning `environment` qiymatini tekshiradi; sayt manzili kutgan muhit bilan mos kelmasa — "MUHIT MOS EMAS", ilova to'xtaydi (E2E T27). Masalan, staging branch xato bilan production ma'lumoti bilan yaratilsa ham staging sayt unga yozmaydi.
2. **Tayyorlik tekshiruvi** (`ci_readiness`, `tools/production_verify.sql`): 0 kirish/hodisa/almashtirish/holat, 0 zaxira, sinov xodimlari yo'q, kirish yopiq, sig'im 11 222, master va varaq xeshlari, RLS va huquqlar.
3. **Migratsiyalar** faqat `supabase/migrations` (= `sql/001–005`, CI bir xilligini tekshiradi); sinov fayllari (`sql/local`, `e2e/seed_*`) u yerga hech qachon tushmaydi.
4. Production'da `environment`, `admission_open`, `capacity` qo'lda emas: kirish va sig'im qulflangan (trigger).
