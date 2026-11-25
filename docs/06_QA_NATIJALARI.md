# 06 — QA natijalari

Sana: 25.11.2026. CI: GitHub Actions `Check-in CI` — barcha 4 job yashil (oxirgi natijalar quyida).
Barcha yozuvchi testlar **alohida sinov bazalarida**; production sayt faqat o'qildi; haqiqiy biletlarga hech qanday kirish yozilmagan.

| To'plam | Natija | Qayerda |
|---|---|---|
| Baza testlari (`tests/test_db.py`) | **72/72 PASS** | lokal + CI |
| Sig'imni aylanib o'tish urinishlari (`tests/test_capacity_attack.py`, toza baza, parallel) | **9/9 PASS** | lokal + CI |
| Brauzer E2E (`e2e/test_e2e.mjs`: `/checkin`, `/inventory`, `/scan-test`) | **47/47 PASS** | lokal + CI |
| Qurilma testlari HTTPS orqali (WebKit/iPhone 15, Chromium/Pixel 7) | **23/23 PASS** | CI |
| Yuklama — baza (16 ishchi) va HTTP (8 darvoza, Auth + /rpc, 20 mijoz poygasi) | **PASS** | lokal + CI |
| Toza migratsiya → production tekshiruvi (`tools/production_verify.sql`) | **17/17 OK** | lokal + CI |
| Production moslik (faqat o'qish) + ommaviy sahifalar `main` bilan bayt-ma-bayt bir xil | **27/27 PASS** + diff bo'sh | CI |

## 3-bosqich (25.11.2026, kechki) — qo'shilgan tekshiruvlar

| Talab | Natija | Dalil |
|---|---|---|
| Takror skan ≠ ikkinchi qog'oz | Takror qarorsiz nusxa hisoblanmaydi; SAME_PAPER/SECOND_COPY; faqat o'z skaniga bir marta; nazoratchi sabab bilan o'zgartiradi; tarix o'chmaydi | T10, T10v, T10i, T10p, E2E T10 |
| Boshlang'ich zaxira = 0 | yangi baza: 0 zaxira, 0 EXTRA; qarorsiz takror/ortiqcha qog'oz/noma'lum zaxira bo'lmaydi | C0, T13h, production_verify |
| Dublikat va tarqatish nizosi → belgi, bilet bekor qilinmaydi | avtomatik belgilar; bilet kiritilishi mumkin | T10d, T23, T24, E2E T24 |
| 11 222 sig'imni aylanib o'tib bo'lmaydi | sozlama/SQL/rol/qarorsiz/noto'g'ri tasdiq — rad; 10 parallel almashtirish (bo'sh o'rin 0) → 0; (bo'sh 1) → 1; 8 parallel to'g'ridan-to'g'ri INSERT (bo'sh 2) → 2; kiritish↔almashtirish va kiritish↔zaxira poygalari (ikkala tartibda) — hech qachon ikkalasi emas; to'liq zalda ≤ 11 222 | C1–C8 |
| Staging ≠ production | sinov QR production'da yaroqsiz; sayt↔baza muhiti mos kelmasa ilova to'xtaydi; tayyorlik tekshiruvi sinov bazasini rad etadi | T25, T26, E2E T26/T27 |
| Topilgan nuqson | qarorsiz takrori bor varaqdagi bilet zaxiraga o'tishi mumkin edi → tuzatildi (T13h) | — |
| Topilgan nuqson | sinov varaqasidagi qisqa QR segno tomonidan Micro QR (telefonlar o'qimaydi) bo'lib chiqardi → oddiy QR majburiy | `tools/make_test_kit.py` |

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
| 14 | Haqiqiy HTTPS bulut yuklama testi | **Tayyor, staging kerak**: CI `cloud-load` job (`RUN_CLOUD_LOAD=1` + staging secrets) | 10-hujjat |

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
