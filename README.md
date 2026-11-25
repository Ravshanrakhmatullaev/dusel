# DUSEL — bilet check-in tizimi (backend, testlar, hujjatlar)

Bu branch **saytga chiqarilmaydi** (Cloudflare Pages faqat `main`ni production qiladi). Xodim ilovasi — `feature/checkin` branchidagi `/checkin`.

- `sql/` — Supabase (Postgres) migratsiyalari: `001` sxema, `002` funksiyalar, `003` 11 222 bilet, `004` sozlamalar, `005` bosma varaqlar. `sql/local/` — faqat lokal/CI uchun Supabase auth o'xshashi.
- `tests/` — baza testlari, yuklama testi, production'ni faqat o'qish tekshiruvi.
- `e2e/` — brauzer testlari (lokal Supabase taqlidi bilan).
- `tools/` — `gen_seed.py`, `gen_print_sheets.py`, `staging_reset.sh` (faqat STAGING), `backup_encrypted.sh` (AES-256 + tekshiruv), `monitor.mjs` (konsert kuni).
- `data/` — `duseeeeeel_1.pdf` varaq tartibi (11 222 qator).
- `docs/` — 01 arxitektura/moslik · 02 xodimlar · 03 insident · 04 deploy/rollback · 05 yuklama · 06 QA · 07 baza · 08 inventar/solishtiruv (A403) · 09 ishonchlilik/tarmoq · 10 bulut yuklama rejasi · 11 production rollout va narx · 12 qurilma sinovi · `reconciliation/` boshlang'ich CSV.

Ilovalar (`feature/checkin` branchi): `/checkin` (haqiqiy kirish), `/inventory` (inventar, kirishga ta'sir qilmaydi), `/scan-test` (qurilma sinovi, serverga ulanmaydi).
