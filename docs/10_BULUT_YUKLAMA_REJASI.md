# 10 — Bulut (HTTPS) yuklama testi rejasi va hozirgi natijalar

## 1. Hozirgacha o'lchangan (bulutsiz)

| Test | Yo'l | Natija |
|---|---|---|
| `tests/load_test.py` | Postgres funksiyalari to'g'ridan-to'g'ri, 16 ishchi | 11 222 kirish, har biletga maks. 1, xato 0 (CI: ~800 kiritish/s) |
| `tests/http_load_test.mjs` (lokal) | **HTTP**: Auth token + `/rest/v1/rpc` (PostgREST taqlidi), 8 darvoza akkaunti | 23 933 so'rov / 43.8 s (547 so'rov/s); `ci_admit` p50 17 ms, p95 27 ms, p99 35 ms; **20 mijoz poygasi → 1 muvaffaqiyat**; ikki marta kirish 0; invariant butun |

Bular baza mantig'i va HTTP yo'lini tekshiradi, lekin **haqiqiy bulut kechikishini emas** (Toshkent → Supabase mintaqasi, mobil internet). Bulut testi staging loyihasi yaratilgach o'tkaziladi.

## 2. Bulut testi (staging Supabase Pro) — reja

**Sharti:** faqat STAGING loyihasi; skript muhit `PRODUCTION` bo'lsa o'zini to'xtatadi, baza toza bo'lmasa ham to'xtaydi.

1. Staging tayyorlash: `tools/staging_reset.sh`; 16–32 sinov darvoza akkaunti (`load-gN@…`, GATE), 16 darvoza (`L1…L16`), admin; `ci_admission_set(true, 'KIRISHNI OCHISH')`; `rate_limit_per_10s` = 200.
2. Yuguruvchilar (bir vaqtda):
   - **R1 — Toshkentdagi noutbuk**, simli internet (haqiqiy geografik kechikish);
   - **R2 — Toshkentdagi noutbuk, mobil hotspot** (darvoza telefoni sharoiti);
   - **R3 — GitHub Actions** (bulutdan bulutga, eng yaxshi holat).
3. Ssenariylar:
   | # | Ssenariy | Parametr | O'tish mezoni |
   |---|---|---|---|
   | L1 | Haqiqiy sur'at | 16 darvoza, `PACE_MS=3000` (≈5 kiritish/s jami), 30 daqiqa | p95 `ci_admit` < 1 s (R1), xato < 0.5%, ikki marta kirish 0 |
   | L2 | Eng og'ir 10 daqiqa ×3 | 32 darvoza, `PACE_MS=1000` | p95 < 1.5 s, xato < 1% |
   | L3 | Stress | 32 darvoza, `PACE_MS=0` | tizim qayerda sekinlashishini yozib olish (mezon emas) |
   | L4 | Poyga | `RACE=20` (bir biletga 20 mijoz) | aynan 1 muvaffaqiyat |
   | L5 | Tarmoq uzilishi | L1 davomida R2 hotspot o'chirib-yoqiladi | "NATIJA NOMA'LUM" → qayta urinish; ikki marta kirish 0 |
   | L6 | Takror/kupon/qayta yuborish | `DUP=0.1 FOREIGN=0.02 RETRY=0.01` | rad etiladi, replay bitta yozuv |
4. CI orqali: repo secrets (`STAGING_URL`, `STAGING_ANON_KEY`, `LOAD_GATES`, `LOAD_ADMIN`) va variable `RUN_CLOUD_LOAD=1` → `checkin-backend` ga push → `cloud-load` job. Qo'lda (misol):
   ```bash
   BASE=https://<staging-ref>.supabase.co ANON_KEY=<publishable> \
   GATES="$(cat gates.json)" ADMIN='{"email":"…","password":"…"}' \
   TICKETS=1-11222 PACE_MS=3000 RACE=20 OUT=L1_R1.json node tests/http_load_test.mjs
   ```
5. Har ssenariydan keyin: `ci_capacity_status.invariant_ok = true`, `ci_report('seat_conflicts')` bo'sh, `tools/staging_reset.sh`.
6. Hisobot: `docs/10_BULUT_YUKLAMA_NATIJALARI.md` (p50/p95/p99 har yuguruvchi bo'yicha, xatolar, Supabase CPU/ulanishlar grafigi skrinshoti).

## 3. Kompyut hajmi

- Kerakli sur'at: 11 222 kishi 90 daqiqada ≈ 2 kiritish/s o'rtacha, eng og'ir payt ≈ 6/s. Mahalliy o'lchov ~800/s.
- Boshlanish: **Micro**. L1–L3 da CPU > 70% bo'lsa — **Small**ga o'tish konsertdan **kamida 1 kun oldin** (hajm o'zgarishi qisqa uzilish bilan bo'ladi, konsert paytida qilinmaydi).
