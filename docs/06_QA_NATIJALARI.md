# 06 — QA natijalari

Sana: 25.11.2026. CI: GitHub Actions `Check-in CI`, run **45622458572** — barcha 3 job yashil.
Barcha testlar **alohida sinov bazalarida** (haqiqiy production biletlariga hech qanday yozuv yo'q). Production sayt faqat o'qildi.

| To'plam | Natija | Qayerda |
|---|---|---|
| Baza testlari (`tests/test_db.py`) | **48/48 PASS** | lokal + CI |
| Brauzer E2E (`e2e/test_e2e.mjs`, Playwright, telefon o'lchami, soxta kamera) | **32/32 PASS** | lokal + CI |
| Yuklama (`tests/load_test.py`) | **LOAD PASS** | lokal + CI |
| Production moslik (`tests/prod_compat.mjs`, faqat o'qish) | **27/27 PASS** | CI |

## Talab qilingan testlar bo'yicha

| # | Tekshiruv | Natija | Testlar |
|---|---|---|---|
| T01–T02 | Eski QR'lar ishlaydi: `dusel.pages.dev/?code=`, `/ticket?code=`, `github.io/dusel/?code=` — to'g'ri raqam, 11223 rad etiladi | PASS | prod_compat 1–19 |
| T03 | 11 222 bilet yozuvi, sektor sonlari masterga mos (A402=277, A403=320, A405=445) | PASS | T03, T03b |
| T04 | Mijoz sahifasini ochish/yangilash biletni ishlatmaydi | PASS | T04 (baza), T04 (E2E) |
| T05 | Birinchi ruxsatli kirish → yashil; darvoza/qurilma/xodim/vaqt yoziladi | PASS | T05, T05a–d |
| T06 | Ikkinchi kirish (boshqa URL formati bilan ham) → qizil, oldingi kirish ko'rsatiladi, holat ochiladi | PASS | T06, T06b, T06c |
| T07 | 24 parallel skan × 40 bilet → har biletga aynan 1 ruxsat | PASS | T07 |
| T08 | Tarmoq qayta yuborishi (bir xil so'rov 16×) → 1 yozuv, natija noaniq emas | PASS | T08, T08b, E2E T08 |
| T09 | GOLD/SILVER/GAL QR → "BU KONSERT BILETI EMAS" | PASS | T09, T09a, E2E T09 |
| T10 | Inventar rejimi kiritmaydi, fizik dublikatlarni sanaydi (06114 ×2, 06101 ×2) | PASS | T10, T10b–e |
| T11 | Qog'ozdagi joy masterdan farq qilsa belgilanadi; ikki bilet bir joyga biriktirilmaydi | PASS | T11, T11b |
| T12 | Nazoratchi ko'rib chiqishi: tarix, dalil, qaror | PASS | T12, T12b–d |
| T13 | Zaxira joy: band joyni berib bo'lmaydi; sig'imdan oshsa `ESCALATED_NO_SEAT` | PASS | T13, T13b–f |
| T14 | Ikki nazoratchi bir joyni parallel band qilsa — faqat 1 muvaffaqiyat | PASS | T14 |
| T07r–u | Almashtirish bileti: 144-bit token, faqat xesh saqlanadi, bir marta kiritadi, soxta token rad | PASS | T07r–T07u |
| T15 | Ruxsatlar: darvoza xodimi bekor qila/sozlay olmaydi, anonim kira olmaydi, jadvallarga to'g'ridan-to'g'ri kirish yo'q, rate-limit | PASS | T15, T15b, E2E T15, T15c |
| T16 | Audit: barcha amallar yoziladi, xesh-zanjir butun, o'zgartirish bloklangan, buzilish aniqlanadi | PASS | T16, T16b, T16c |
| T17 | Noto'g'ri/manipulyatsiya qilingan URL va diapazondan tashqari raqam rad etiladi | PASS | T17a–c, E2E T17 |
| T18 | Admin sessiyani bekor qilsa eski token ishlamaydi | PASS | T18, T18b, E2E T18b |
| T19 | Internet uzilishi: "NATIJA NOMA'LUM", favqulodda rejim faqat kod bilan, sinxronlashda ziddiyat → `OFFLINE_CONFLICT` | PASS | T19, T19b (baza+E2E), T19a |
| T20 | `/checkin` alohida, login talab qiladi, CSP/xavfsizlik sarlavhalari, JS xatolari yo'q; production'da hali yo'q (404) | PASS | E2E T20b, T00; prod_compat 24–27 |

## Topilgan va tuzatilgan xatolar (ishlab chiqish davomida)

1. Sig'im to'lganda xato `raise` qilingani uchun holat `ESCALATED_NO_SEAT` saqlanmay qolardi → xato JSON qaytariladi, audit yoziladi.
2. Chiqishda sessiya brauzer xotirasida qolardi (poyga holati) → `signOut` darhol tozalaydi.
3. CI: `psycopg-binary 3.2.3` yo'q → 3.2.13; Playwright 1.49 CSP ostida `waitForFunction` ishlatolmadi → eval'siz kutish, Playwright 1.63.

## Skrinshotlar

`e2e/shots/` (CI artifact `e2e-screenshots`): 01_login … 13_offline_mode, 05b_referred, 11b_replacement_qr.

## Ochiq qolganlar

- Real Supabase staging'da smoke va HTTP yuklama testi — loyiha yaratilgach.
- Haqiqiy tarqatish ro'yxati (kim qaysi biletni olgan) import qilinmagan — tizim taxmin qilmaydi, "UNKNOWN" ko'rsatadi.
