# 02 — Xodimlar qo'llanmasi (Darvoza, Nazoratchi, Admin)

Sahifa: `https://dusel.pages.dev/checkin` (faqat Admin faollashtirgandan keyin ishlaydi).
Sinov (staging): `https://feature-checkin.dusel.pages.dev/checkin`.

> Mijozlar uchun bilet sahifasi (`/?code=…`, `/ticket?code=…`) **hech qachon** biletni ishlatmaydi. Biletni faqat shu `/checkin` sahifasidagi xodim "KIRITISH" tugmasi bilan kiritadi.

## 1. Kirish va rollar

| Rol | Ko'radigan bo'limlar | Asosiy vazifa |
|---|---|---|
| GATE (darvoza) | Kirish, Inventar | QR skan → kiritish yoki nazoratga yuborish |
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
- **Zaxira joy band qilish → Almashtiruvchi bilet berish** — yangi QR (`DUSELR1:…`, taxmin qilib bo'lmaydigan 144-bit kod) chiqadi, chop eting yoki telefonda ko'rsating. Zaxira faqat Admin kiritgan haqiqiy bo'sh joylardan olinadi; ortiqcha bosilgan biletlar zaxira **hisoblanmaydi**.
- **Bo'sh joy yo'q** — tizim sig'imdan oshirmaydi, holat `ESCALATED_NO_SEAT` bo'ladi → tashkilotchi hal qiladi.
- **Rad etish / yopish** — sabab bilan.

Asl bilet avtomatik bekor qilinmaydi. Bekor qilish faqat nazoratchi qarori bilan, sabab yozilib.

## 4. Internet uzilsa (favqulodda rejim)

1. Avval "Qayta urinish" — ko'pincha 1–2 soniyada tiklanadi.
2. Davom etsa, nazoratchidan **favqulodda kod** so'rang → "Favqulodda rejim" → kodni kiriting. Kod qurilmaga oldindan (onlayn paytda) yuklangan bo'lishi kerak.
3. Ekranda **"VAQTINCHA QABUL (oflayn)"** chiqadi. Qurilma faqat o'zi ko'rgan takrorlarni biladi — boshqa darvozalar bilan taqqoslay olmaydi.
4. Internet qaytgach yozuvlar avtomatik yuboriladi. Agar shu bilet boshqa joyda allaqachon kiritilgan bo'lsa — **ziddiyat** xabari va `OFFLINE_CONFLICT` holati ochiladi.
5. Oflayn rejimni faqat zarur bo'lganda va iloji boricha bitta darvozada ishlating.

Batafsil: `03_INSIDENT_VA_INTERNET_UZILISHI.md`.

## 5. Inventar (biletni sanash — kiritmaydi)

Bosmaxonadan qolgan / tarqatilmagan biletlarni sanash uchun. **Kirish holatiga ta'sir qilmaydi.**
1. Inventar → yangi partiya oching (nomi: "Ombor 1-quti" kabi).
2. Uzluksiz skan qiling. Bir xil raqam ikkinchi marta chiqsa — "Inventar nusxa" (fizik dublikat).
3. Partiyani yoping. Panel → hisobotlar: dublikatlar, yetishmaganlar, joy ziddiyatlari.

## 6. Admin

- Kirishni ochish/yopish (konsert kuni, darvozalar ochilishidan oldin).
- `block_held_stock` — tarqatilmagan deb belgilangan biletlarni nazoratga yo'naltirish.
- Xodim qo'shish (Supabase'da yaratilgan email), rol berish, o'chirish, sessiyani bekor qilish.
- Tarqatish ro'yxatini CSV import (hammasi yoki hech narsa).
- Zaxira joylar qo'shish, sig'im (kiritilgan + band qilinganlardan kam bo'lmaydi).
- Favqulodda kod (8–12 raqam) o'rnatish.
- Audit jurnalini tekshirish ("zanjir butun") va CSV yuklab olish.
