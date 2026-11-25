# 05 — Yuklama testi hisoboti

Skript: `tests/load_test.py`. Baza: Postgres 16, haqiqiy migratsiyalar (`001–004`), **alohida sinov bazasi** (`ci_load`, har safar noldan).

## Ssenariy

- 16 parallel ishchi (16 darvoza telefoni o'rnida), har biri o'z xodim tokeni bilan.
- Barcha **11 222** bilet: avval `ci_lookup` (ko'rish), keyin `ci_admit` (kiritish).
- Aralash yuk: 10% takroriy skan (boshqa darvozadan), 2% GOLD/SILVER/GAL QR, 1% tarmoq qayta yuborishi (bir xil `request_id`).
- Oxirida tekshiruv: har biletga aynan 1 ta `ADMITTED` hodisa, xatolar 0.

## Natijalar

| Ko'rsatkich | Lokal (2 yadro) | GitHub Actions (25.11.2026, run 45622458572) |
|---|---|---|
| Amallar | 25 400 | 25 400 |
| Vaqt | 28.5 s | 14.0 s |
| Amal/s | 891 | 1 812 |
| Kiritish/s | 394 | 801 |
| `ci_lookup` p50 / p95 / p99 | 3.3 / 6.3 / 8.9 ms | 2.4 / 4.5 / 17.3 ms |
| `ci_admit` p50 / p95 / p99 | 31.9 / 41.5 / 51.5 ms | 10.3 / 25.3 / 175.3 ms |
| Kiritilgan biletlar | 11 222 | 11 222 |
| Bir biletga maks. kirish | 1 | 1 |
| ADMITTED / TAKROR / BOSHQA TIZIM | — | 11 222 / 1 124 / 230 |
| Xatolar | 0 | 0 |
| Natija | **LOAD PASS** | **LOAD PASS** |

## Talab bilan solishtirish

Agar 11 222 tomoshabin 90 daqiqada kirsa: o'rtacha ~2 kiritish/s, eng og'ir 10 daqiqada (taxminan 30%) ~6 kiritish/s. Test sur'ati bundan ~65–130 baravar yuqori. Darvozadagi asosiy kechikish — mobil internet va odamlar, baza emas.

## Cheklovlar (halol)

- Test baza ichida (PostgREST/HTTP va mobil internetsiz) o'lchangan. Haqiqiy Supabase'da har so'rovga tarmoq kechikishi qo'shiladi (Toshkent → Yevropa odatda bir necha o'n ms dan yuzlab ms gacha; o'lchanmagan).
- Staging Supabase loyihasi hali yaratilmagan (bepul tarif limiti) — shuning uchun real bulut muhitida yuklama testi **o'tkazilmagan**. Staging tayyor bo'lgach, xuddi shu ssenariy HTTP orqali qayta o'tkaziladi.
- Bepul Supabase tarifi: 1 hafta harakatsizlikdan keyin pauza, avtomatik backup yo'q. Konsert uchun **Pro** tarifi tavsiya etiladi (kundalik backup, pauza yo'q). Uptime bo'yicha bu hujjat kafolat bermaydi.
- Rate-limit: xodim boshiga 10 soniyada 40 so'rov (`rate_limit_per_10s`). Tez rejimda bitta darvoza bundan oshmaydi; kerak bo'lsa Admin oshiradi.
