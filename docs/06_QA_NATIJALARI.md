# 06 — QA natijalari

Sana: 25.11.2026. CI: GitHub Actions `Check-in CI`, run **45632856788** — barcha 4 job yashil.
Barcha yozuvchi testlar **alohida sinov bazalarida**; production sayt faqat o'qildi; haqiqiy biletlarga hech qanday kirish yozilmagan.

| To'plam | Natija | Qayerda |
|---|---|---|
| Baza testlari (`tests/test_db.py`) | **66/66 PASS** | lokal + CI |
| Brauzer E2E (`e2e/test_e2e.mjs`: `/checkin`, `/inventory`, `/scan-test`) | **44/44 PASS** | lokal + CI |
| Qurilma testlari HTTPS orqali (`e2e/test_devices.mjs`: WebKit/iPhone 15, Chromium/Pixel 7, Cloudflare preview + production faqat o'qish) | **23/23 PASS** | CI |
| Yuklama — baza (`tests/load_test.py`, 16 ishchi) | **PASS**: 11 222 kirish, har biletga maks. 1, xato 0 (CI: 1 169 kiritish/s) | lokal + CI |
| Yuklama — HTTP (`tests/http_load_test.mjs`, 8 darvoza, Auth + /rpc) | **PASS**: 20 mijoz poygasi → 1 muvaffaqiyat; ikki marta kirish 0; invariant butun | lokal + CI |
| Production moslik (`tests/prod_compat.mjs`, faqat o'qish) | **27/27 PASS** | CI |

## Egasining talab qilgan 14 ta testi

| # | Talab | Holat | Dalil |
|---|---|---|---|
| 1 | 500 jismoniy bilet inventarda — 0 kirish | **PASS** (11 737 skan bilan) | T10j, T10z |
| 2 | Bir biletni 3 marta inventarda — nusxa oshadi | **PASS** (1→2→3, 2-da "BIRINCHI DUBLIKAT") | T10i, E2E T10 |
| 3 | Yo'q biletlar "ko'rilmagan", "bosilmagan" emas | **PASS** | T10e, T21, E2E T21 |
| 4 | 00330 kiritish — 1 muvaffaqiyat | **PASS** | T05, E2E T05 |
| 5 | 00330 boshqa darvozada — rad | **PASS** (eski github.io URL bilan ham) | T06, E2E T06 |
| 6 | 20 mijoz bir vaqtda — ko'pi bilan 1 | **PASS** (24 parallel ×40 bilet; HTTP 20 mijoz) | T07, HTTP RACE |
| 7 | GOLD/SILVER/GAL — rad | **PASS** | T09, E2E T09, qurilma testi |
| 8 | Asosiy internet uzilib-ulanishi | **Ilova qismi PASS** (NATIJA NOMA'LUM → qayta urinish, 1 yozuv); zaldagi router failover — **zalda qo'lda** (09-hujjat F1–F10) | E2E T19a, T08 |
| 9 | 2-provayderga avtomatik o'tish | **Zalda qo'lda** (uskuna kerak) | 09-hujjat F2 |
| 10 | Kamera ruxsati xatolari va tashqi skaner | **PASS** (emulyatsiya + HTTPS); haqiqiy telefonlar — **qo'lda** (12-hujjat D1–D11) | E2E T10c/T10s, qurilma 23/23 |
| 11 | Takror bilet bahsi va almashtirish | **PASS** | T12–T14, T07r–v, T13j, E2E T12 |
| 12 | Bekor qilish/qayta urinish/timeout — ikki marta kirish yo'q | **PASS** | T08, T08b, E2E T08 |
| 13 | Kirish hisoblagichlari va sig'im cheklovi | **PASS** (ruxsatlar 11 222 / 11 222) | T07u, T13c–m, E2E T07u/T13d |
| 14 | Haqiqiy HTTPS bulut yuklama testi | **Rejalashtirilgan, staging kerak** (Supabase Pro ruxsati) | 10-hujjat |

## 2-bosqichda topilgan va tuzatilgan muammolar

1. **Dashboard 11223 / 11223** — sinovning o'zi sabab: E2E test EXTRA joy qo'shib, sig'imni qo'lda 11 223 ga ko'targan. Haqiqiy nuqson esa — sig'imni bitta maydon bilan oshirish mumkin edi. Tuzatildi: sig'im qulflangan (faqat yozma qaror + tasdiq matni), almashtirish uchun hech qachon oshmaydi, zaxira faqat isbotli tashkilotchi zaxirasidan (asl bilet bekor), baza trigger'i sig'imdan oshishni rad etadi.
2. **Har qanday darvoza oflayn kirita olardi** → faqat bitta belgilangan nazoratchi qurilmasi; server ham tekshiradi.
3. **Favqulodda kod oddiy sha256 edi** (8 raqamni tez topish mumkin) → PBKDF2-SHA256, 300 000 iteratsiya, 10–12 raqam, kod faqat belgilangan qurilmaga beriladi.
4. **Sessiyani bekor qilish refresh tokenni o'chirmasdi** → Supabase Auth sessiyalari va refresh tokenlar ham bekor (T18c).
5. **Inventar va kirish bir rol/ilovada edi** → alohida `/inventory`, INVENTORY roli, baza rejim trigger'i.
6. **Kamera rad etilsa faqat "ruxsat berilmadi"** → platformaga mos yo'riqnoma, tiklash tugmalari, tashqi skaner, `/scan-test`.
7. **Kirill tartibdagi telefon + skaner** URL'ni buzardi → jismoniy tugma kodi bo'yicha ikki talqinli dekodlash.
8. **Solishtiruv hisoboti 49 s** davom etardi → set-based so'rov, 0.1 s.
9. **Kirish ochilishi** tasdiqsiz edi → aniq "KIRISHNI OCHISH" matni; migratsiya/deploy ochmaydi (T20, T22).

## Skrinshotlar

CI artifact'lari: `e2e-screenshots` (login, natijalar, kamera rad etildi iPhone/Android, tashqi skaner, inventar dublikat, oflayn navbat, A403 solishtiruv, admin, almashtirish, panel, favqulodda rejim, scan-test) va `devices-https` (WebKit/Chromium: eski QR'lar, scan-test, kamera rad etildi).

## Ochiq qolganlar (ruxsat yoki zal kerak)

- Staging Supabase (Pro) → bulut yuklama (L1–L6), staging smoke.
- Zalda: router failover, UPS, haqiqiy telefonlar va skanerlar (09, 12-hujjatlar).
- Haqiqiy tarqatish ro'yxati (CSV) va A403 qoldiqlarini skanerlash.
