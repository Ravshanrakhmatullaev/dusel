# DUSEL — bilet check-in tizimi (backend, testlar, hujjatlar)

Bu branch **saytga chiqarilmaydi** (Cloudflare Pages faqat `main`ni production qiladi). Xodim ilovasi — `feature/checkin` branchidagi `/checkin`.

- `sql/` — Supabase (Postgres) migratsiyalari: `001` sxema, `002` funksiyalar, `003` 11 222 bilet, `004` sozlamalar. `sql/local/` — faqat lokal/CI uchun Supabase auth o'xshashi.
- `tests/` — baza testlari, yuklama testi, production'ni faqat o'qish tekshiruvi.
- `e2e/` — brauzer testlari (lokal Supabase taqlidi bilan).
- `docs/` — arxitektura, moslik auditi, xodimlar qo'llanmasi, favqulodda reja, deploy/rollback.
