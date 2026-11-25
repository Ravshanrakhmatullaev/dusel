# 03 — Insident va internet uzilishi rejasi

## 1. Konsertdan oldin (T−1 kun)

- [ ] Kirish **yopiq** (`admission_open = false`), sinov biletlari yo'q, haqiqiy biletlar `NOT_ADMITTED`.
- [ ] Har bir darvoza telefoni: zaryad, powerbank, kamera ruxsati, kirish tekshirilgan.
- [ ] Har bir telefonga onlayn paytda: Panel → **ro'yxatni yuklab olish** (oflayn uchun) va favqulodda kod yuklangan.
- [ ] Zaxira internet: har darvozada 2 xil operator (mobil hotspot) + arena Wi-Fi.
- [ ] Nazorat stoli joylashgan, nazoratchi va admin telefon raqamlari darvozalarda.
- [ ] Supabase loyihasi faol (bepul tarifda 1 hafta harakatsizlikdan keyin pauza bo'ladi — T−1 kuni sahifani ochib tekshiring) va zaxira nusxa olingan.

## 2. Ssenariylar

| Hodisa | Belgisi | Harakat |
|---|---|---|
| Bitta telefon internetsiz | "NATIJA NOMA'LUM — KIRITMANG" | Qayta urinish → hotspotga ulanish → boshqa telefon |
| Butun arena internetsiz | Barcha darvozalarda kulrang natija | Nazoratchi qaror qiladi: (a) kutish 2–3 daqiqa; (b) **favqulodda rejim** faqat kerakli darvozalarda |
| Supabase ishlamayapti | Internet bor, lekin hamma so'rovlar xato | Supabase status sahifasini tekshirish; favqulodda rejim |
| Telefon yo'qoldi/o'g'irlandi | — | Admin: xodim sessiyasini bekor qilish (`ci_staff_revoke_sessions`), kerak bo'lsa favqulodda kodni almashtirish |
| Ko'p takror skan bir sektorda | Panel → holatlar ko'payadi | Inventar ma'lumotiga qarang (bosmaxona dublikati?), nazoratchilarni ko'paytiring |
| Sig'im tugadi, mijoz joysiz | `ESCALATED_NO_SEAT` | Tashkilotchi qaror qiladi; tizim sig'imdan oshirmaydi |
| Sahifa ochilmayapti (Cloudflare) | `/checkin` yuklanmaydi | Keshdan ochilgan sahifa ishlayveradi; aks holda zaxira URL (staging) faqat admin ruxsati bilan |

## 3. Favqulodda (oflayn) rejim qoidalari

- Faqat nazoratchi kodi bilan yoqiladi; kod sha256(salt:kod) ko'rinishida saqlanadi.
- Har bir oflayn qabul qurilmada navbatga yoziladi (`request_id`, vaqt, darvoza).
- Qurilma **o'z ichidagi** takrorlarni rad etadi va yuklangan ro'yxatdan raqam/joyni ko'rsatadi; boshqa qurilmalar bilan solishtira olmaydi. Shu sababli bir nechta qurilma bir vaqtda oflayn ishlasa, bitta bilet ikki darvozadan o'tishi **mumkin** — bu sinxronlashda `OFFLINE_CONFLICT` sifatida aniqlanadi, lekin oldini olmaydi.
- Xavfni kamaytirish: oflayn rejimni iloji boricha bitta darvozada yoqing, qolgan darvozalarni yopib turing.
- Internet qaytgach navbat avtomatik yuboriladi (xuddi shu `request_id` — takror yozilmaydi). Server oflayn vaqtni (`admitted_offline_at`) saqlaydi.

## 4. Konsertdan keyin

1. Kirishni yopish.
2. Barcha telefonlarda sinxronlanmagan yozuvlar 0 ekanini tekshirish.
3. Panel → hisobotlar: admissions, cases, replacements, seat_conflicts — CSV yuklab olish.
4. Audit → "zanjirni tekshirish" (butun bo'lishi kerak), CSV yuklab olish.
5. Bazaning zaxira nusxasi (`pg_dump`).
6. Ochiq holatlarni yopish yoki tashkilotchiga topshirish.

## 5. Kafolatlar haqida

Tizim bitta bilet onlayn rejimda ikki marta kiritilmasligini ma'lumotlar bazasi darajasida ta'minlaydi (atomar `UPDATE … WHERE status='NOT_ADMITTED'`). Uptime, Supabase yoki mobil internet ishlashi uchun kafolat **berilmaydi** — shuning uchun yuqoridagi zaxira choralar kerak.
