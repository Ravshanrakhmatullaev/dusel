# 02 — Xodimlar qo'llanmasi (Darvoza, Nazoratchi, Admin)

Sahifa: `https://dusel.pages.dev/checkin` (faqat Admin faollashtirgandan keyin ishlaydi).
Sinov (staging): `https://feature-checkin.dusel.pages.dev/checkin`.

> Mijozlar uchun bilet sahifasi (`/?code=…`, `/ticket?code=…`) **hech qachon** biletni ishlatmaydi. Biletni faqat shu `/checkin` sahifasidagi xodim "KIRITISH" tugmasi bilan kiritadi.

## 1. Kirish va rollar

| Rol | Ko'radigan bo'limlar | Asosiy vazifa |
|---|---|---|
| INVENTORY | faqat `/inventory` | Qog'oz biletlarni sanash (kirishga ta'sir qilmaydi) |
| GATE (darvoza) | Kirish | QR skan → kiritish yoki nazoratga yuborish |
| SUPERVISOR (nazoratchi) | + Nazorat, Panel | Takror/shubhali holatlarni hal qilish, zaxira joy, almashtiruvchi bilet |
| ADMIN | + Admin | Kirishni ochish/yopish, xodimlar, darvozalar, sozlamalar, audit |

1. Telefon brauzerida sahifani oching, Admin bergan email + parol bilan kiring.
2. Darvozani tanlang (G1–G4, VIP). Har bir skan shu darvozaga yoziladi.
3. 2 soat harakatsizlikdan keyin tizim avtomatik chiqaradi. Admin istalgan xodim sessiyasini masofadan bekor qila oladi.
4. Parolni hech kimga bermang, telefonni qarovsiz qoldirmang.

## 2. Darvozada ishlash (Kirish bo'limi)

1. Kamera ruxsatini bering. QR'ni ramkaga tuting (yoki raqamni qo'lda yozing).
2. Ekranda bilet ma'lumoti chiqadi: **raqam, zona, sektor, qator, joy**. Mijozdan joyni so'rab solishtiring.
3. **KIRITISH** tugmasini bosing. Natija rangi:

| Ekran | Rang | Nima qilish kerak |
|---|---|---|
| KIRISH TASDIQLANDI | yashil | Mijozni o'tkazing |
| ALLAQACHON KIRITILGAN / TAKROR SKAN | qizil | **Mijozni ayblamang.** Oldingi kirish vaqti/darvozasi ko'rsatiladi. Mijozni nazorat stoliga yuboring — holat raqami avtomatik ochiladi |
| TO'XTATILGAN — NAZORATCHIGA | sariq | Nazoratchiga yuboring |
| NAZORATCHIGA YUBORING (ushlab qolingan zaxira) | sariq | Bilet tarqatilmagan zaxiradan — nazoratchi hal qiladi |
| BEKOR QILINGAN BILET | qizil | Nazoratchiga yuboring |
| BU KONSERT BILETI EMAS | qizil | GOLD/SILVER/GAL kupon — konsertga kiritmaydi |
| YAROQSIZ QR / BILET TOPILMADI | qizil | Boshqa QR yoki 1–11222 oralig'idan tashqari raqam |
| KIRISH HALI OCHILMAGAN | qizil | Admin kirishni ochmagan |
| **NATIJA NOMA'LUM — KIRITMANG** | kulrang | Internet uzildi. "Qayta urinish" bosing (xuddi shu so'rov qayta yuboriladi, ikki marta kiritilmaydi). Davom etsa — 4-bo'lim |

4. **Tez rejim** belgilansa, skandan keyin tugmasiz darhol kiritadi (navbat katta bo'lganda). Joyni solishtirish xodim zimmasida qoladi.
5. Shubha bo'lsa — **"Nazoratga yuborish"**, sababini yozing. Bilet kiritilmaydi, holat ochiladi.

## 3. Nazorat stoli (Supervisor)

Har bir holatda: bilet raqami, joyi, oldingi kirish (vaqt, darvoza, xodim), skanlar tarixi, inventar natijasi, tarqatish yozuvi (agar import qilingan bo'lsa), bosmaxonadagi fizik nusxalar soni.

**Muhim tamoyil:** birinchi skan qilgan odam har doim haqiqiy egasi emas. Bosmaxona bir xil raqamni ikki marta bosgan holatlar bor (masalan №06114). Qaror mijoz bilan gaplashib, hujjat/xarid dalili bilan qabul qilinadi.

Amallar:
- **Kiritish (nazoratchi)** — sabab majburiy; faqat bilet hali kiritilmagan bo'lsa.
- **Ushlab turish / bo'shatish** — biletni vaqtincha to'xtatadi.
- **Asl bilet o'rniga yangi QR (o'sha joy)** — asl bilet hali kiritilmagan bo'lsa (shikastlangan, yo'qolgan): asl bekor qilinadi, yangi xavfsiz QR o'sha joyga; jami ruxsatlar o'zgarmaydi. Tasdiqlash uchun bilet raqamini qayta yozasiz.
- **Ikkinchi xaridor uchun zaxira joy band qilish → Almashtiruvchi bilet berish** — yangi QR (`DUSELR1:…`, taxmin qilib bo'lmaydigan 144-bit kod) chiqadi, chop eting yoki telefonda ko'rsating. Zaxira faqat Admin kiritgan haqiqiy bo'sh joylardan olinadi; ortiqcha bosilgan biletlar zaxira **hisoblanmaydi**.
- **Bo'sh joy yo'q** — tizim sig'imdan oshirmaydi, holat `ESCALATED_NO_SEAT` bo'ladi → tashkilotchi hal qiladi.
- **Rad etish / yopish** — sabab bilan.

Asl bilet avtomatik bekor qilinmaydi. Bekor qilish faqat nazoratchi qarori bilan, sabab yozilib.

## 4. Internet uzilsa

1. "Qayta urinish" — ko'pincha 1–2 soniyada tiklanadi (bir xil so'rov ikki marta kiritmaydi).
2. 30 soniyada tiklanmasa — telefon Wi-Fi'ni o'chirib mobil internetda "Qayta urinish".
3. Baribir yo'q — **mijozni o'tkazmang**, nazoratchini chaqiring. Darvoza telefoni **oflayn kirita olmaydi** (tugma yo'q, server ham qabul qilmaydi).
4. Uzoq uzilishda faqat **nazoratli favqulodda rejim**: Admin oldindan belgilagan **bitta** nazoratchi qurilmasi, 10–12 raqamli kod bilan. Ekranda sariq "NAZORAT OSTIDA QAYD ETILDI — server tasdiqlamagan" (hech qachon yashil emas). Aloqa qaytgach yozuvlar serverga yuboriladi; boshqa darvozada avval kirgan bilet — `OFFLINE_CONFLICT` holati.

Batafsil: `03_INSIDENT_VA_INTERNET_UZILISHI.md`, `09_ISHONCHLILIK_VA_TARMOQ.md`.

## 5. Inventar — alohida ilova

Qog'oz biletlarni sanash `/inventory` ilovasida, alohida **INVENTORY** rolidagi xodimlar bilan (darvoza xodimi inventar qila olmaydi, inventar xodimi kirita olmaydi). Takror skan chiqsa — qog'ozlarni solishtiring: o'sha qog'oz bo'lsa "YO'Q", ikkinchi qog'oz bo'lsa "HA" va uni DUBLIKAT konvertiga soling. Batafsil: `08_INVENTAR_VA_SOLISHTIRUV.md`.

## 5b. Nazoratchi belgilari

Nazorat → "Nazoratchi belgilari": tasdiqlangan bosma dublikatlari va tarqatish nizolari. Belgi biletni bekor qilmaydi. Mijoz kelsa — holat ochib, dalillar asosida qaror qiling.

## 5a. Kamera ishlamasa

Ilova sababini va platformaga mos yo'lni ko'rsatadi (iPhone: «aA → Veb-sayt sozlamalari → Kamera»; Android: «qulf → Ruxsatlar → Kamera»), «Kamerani qayta yoqish» tugmasi bor. Kamerasiz: tashqi 2D skaner (maydonni bo'sh qoldirib skanerlang) yoki raqamni qo'lda yozing va qog'ozdagi sektor/qator/joyni ekrandagi bilan solishtiring. Qurilmani oldindan `/scan-test` da sinang.

## 6. Admin

- Kirishni ochish — faqat aniq tasdiq matni **KIRISHNI OCHISH** bilan (konsert kuni, egasi bilan birga); yopish — bir tugma.
- `block_held_stock` — tarqatilmagan deb belgilangan biletlarni nazoratga yo'naltirish.
- Xodim qo'shish (Supabase'da yaratilgan email), rol berish, o'chirish, sessiyani bekor qilish.
- Tarqatish ro'yxatini CSV import (hammasi yoki hech narsa).
- Sig'im (11 222) faqat ko'rsatiladi; almashtirish uchun **hech qachon oshirilmaydi**. Zaxira joy faqat: (a) isbotli tashkilotchi zaxirasidagi bilet (asl bilet bekor, joyi zaxiraga — jami o'zgarmaydi) yoki (b) masterda yo'q EXTRA joy, lekin unga almashtirish faqat sig'imda bo'sh o'rin bo'lsa.
- Favqulodda kod (10–12 raqam) va **favqulodda qurilmani** belgilash (faqat bitta nazoratchi qurilmasi).
- Audit jurnalini tekshirish ("zanjir butun") va CSV yuklab olish.
