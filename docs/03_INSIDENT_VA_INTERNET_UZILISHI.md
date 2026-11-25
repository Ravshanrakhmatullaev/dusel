# 03 — Insident va internet uzilishi rejasi

## 1. Konsertdan oldin (T−1 kun)

- [ ] Kirish **yopiq** (`admission_open = false`), sinov biletlari yo'q, haqiqiy biletlar `NOT_ADMITTED`.
- [ ] Har bir darvoza telefoni: zaryad, powerbank, kamera ruxsati, kirish tekshirilgan.
- [ ] Favqulodda qurilma (bitta nazoratchi telefoni/noutbuki) belgilangan, kod o'rnatilgan, qurilmada Panel → **Favqulodda ro'yxat** yuklangan.
- [ ] Har bir telefon va tashqi skaner `/scan-test` dan o'tgan.
- [ ] Zaxira internet: har darvozada 2 xil operator (mobil hotspot) + arena Wi-Fi.
- [ ] Nazorat stoli joylashgan, nazoratchi va admin telefon raqamlari darvozalarda.
- [ ] Supabase loyihasi faol (bepul tarifda 1 hafta harakatsizlikdan keyin pauza bo'ladi — T−1 kuni sahifani ochib tekshiring) va zaxira nusxa olingan.

## 2. Ssenariylar

| Hodisa | Belgisi | Harakat |
|---|---|---|
| Bitta telefon internetsiz | "NATIJA NOMA'LUM — KIRITMANG" | Qayta urinish → hotspotga ulanish → boshqa telefon |
| Butun arena internetsiz | Barcha darvozalarda "SERVER BILAN ALOQA YO'Q" | Router failover / 2-provayder; navbat to'xtatiladi; 5+ daqiqa — nazoratli favqulodda rejim (bitta qurilma) |
| Supabase ishlamayapti | Internet bor, lekin hamma so'rovlar xato | Supabase status sahifasini tekshirish; favqulodda rejim |
| Telefon yo'qoldi/o'g'irlandi | — | Admin: xodim sessiyasini bekor qilish (`ci_staff_revoke_sessions`), kerak bo'lsa favqulodda kodni almashtirish |
| Ko'p takror skan bir sektorda | Panel → holatlar ko'payadi | Inventar ma'lumotiga qarang (bosmaxona dublikati?), nazoratchilarni ko'paytiring |
| Sig'im tugadi, mijoz joysiz | `ESCALATED_NO_SEAT` | Tashkilotchi qaror qiladi; tizim sig'imdan oshirmaydi |
| Sahifa ochilmayapti (Cloudflare) | `/checkin` yuklanmaydi | Keshdan ochilgan sahifa ishlayveradi; aks holda zaxira URL (staging) faqat admin ruxsati bilan |

## 3. Nazoratli favqulodda rejim (mustaqil ko'p darvozali oflayn kirish YO'Q)

- Darvoza telefonlari server javobisiz hech kimni kiritmaydi: tugma yo'q, server `CONTINGENCY_DEVICE_ONLY` bilan rad etadi (E2E T15, baza T19a).
- Faqat Admin oldindan belgilagan **bitta** qurilma (`ci_contingency_device_set`), faqat SUPERVISOR/ADMIN, 10–12 raqamli kod (PBKDF2-SHA256, 300 000 iteratsiya; qurilmada faqat xesh, ochiq kod hech qayerda saqlanmaydi).
- Har yozuv sariq "NAZORAT OSTIDA QAYD ETILDI — server tasdiqlamagan"; shu qurilmadagi takror rad etiladi; ro'yxat yuklangan bo'lsa joy ko'rsatiladi.
- Aloqa qaytgach navbat bir xil `request_id` bilan yuboriladi; server oflayn vaqtni saqlaydi; allaqachon kirgan bilet → `OFFLINE_CONFLICT` holati.
- Cheklov: oflayn paytda bu qurilma boshqa darvozalarning avvalgi kirishlarini bilmaydi — shuning uchun rejim faqat tashkilotchi rahbari ruxsati bilan va qolgan darvozalar yopiq turganda.
- Qurilma ID ilova tomonidan yaratiladi; belgilash tashkiliy nazorat (rol + kod + bitta qurilma), kriptografik qurilma bog'lash emas.

## 4. Konsertdan keyin

1. Kirishni yopish.
2. Barcha telefonlarda sinxronlanmagan yozuvlar 0 ekanini tekshirish.
3. Panel → hisobotlar: admissions, cases, replacements, seat_conflicts — CSV yuklab olish.
4. Audit → "zanjirni tekshirish" (butun bo'lishi kerak), CSV yuklab olish.
5. Bazaning zaxira nusxasi (`pg_dump`).
6. Ochiq holatlarni yopish yoki tashkilotchiga topshirish.

## 5. Kafolatlar haqida

Tizim bitta bilet onlayn rejimda ikki marta kiritilmasligini ma'lumotlar bazasi darajasida ta'minlaydi (atomar `UPDATE … WHERE status='NOT_ADMITTED'`). Uptime, Supabase yoki mobil internet ishlashi uchun kafolat **berilmaydi** — shuning uchun yuqoridagi zaxira choralar kerak.
