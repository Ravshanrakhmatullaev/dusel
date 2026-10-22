# DUSEL · Yulduzli Kecha — bosma yo'riqnomasi (11 222 bilet)

## Fayllar holati

| Fayl | Holati |
|---|---|
| `DUSEL_PROOF_6UP_CMYK.pdf` + preview | Proof — **tasdiqlash uchun** |
| `DUSEL_DUPLEX_TEST.pdf` | Ikki tomonlama sinov listi — **faqat sinov uchun**, hoshiyada pozitsiya raqamlari bor |
| `DUSEL_FRONT_11222_CMYK.pdf`, `DUSEL_BACK_11222_CMYK.pdf` | Texnik jihatdan tayyor va tekshirilgan. **Proof va duplex sinov tasdiqlanmaguncha bosmaga ruxsat yo'q.** |
| `DUSEL_MASTER_11222.xlsx / .csv` | Yagona manba. Bosma ham, sayt ham shundan |
| `DUSEL_QR_SVG_11222.zip`, `DUSEL_QR_PNG_11222.zip` | QR fayllar (PDF ichidagi QR'lar bilan bir xil) |

## Varaq va kesish

- Varaq **450 × 320 mm**, landshaft. Bilet **200 × 100 mm**, 2 × 3, oraliqsiz. To'r 400 × 300 mm, varaq markazida (chap/o'ng 25 mm, yuqori/past 10 mm).
- Kesish: belgilar bo'yicha 3 ta vertikal (25 / 225 / 425 mm) va 4 ta gorizontal (10 / 110 / 210 / 310 mm) kesim.
- Asl dizaynda bleed yo'q. Kesish aniqligi ±0.2 mm bo'lishi kerak, aks holda qo'shni biletning chekkasi ko'rinadi.
- List tartibi: 1-list 00001–00006 … 1870-list 11215–11220, **1871-list 11221–11222 (2 ta bilet, yuqori qator)**.
- Listdagi o'rinlar (old tomon):
  ```
  [1][2]
  [3][4]
  [5][6]
  ```

## Ikki tomonlama bosma (muhim)

- Orqa tomon **varaqni chapdan o'ngga aylantirib** bosiladi (vertikal o'q atrofida, yuqori chet yuqorida qoladi).
  - Landshaft hujjat uchun printer sozlamasi odatda: **"Flip on short edge" / "Переворот по короткому краю"**.
  - RIP varaqni portret holatda uzatsa, nom teskari bo'lishi mumkin. Shuning uchun quyidagi sinovni qiling.
- Tekshirish: `DUSEL_DUPLEX_TEST.pdf` ni bitta varaqqa ikki tomonlama bosing va yorug'likka tuting:
  1. Old tomondagi **1–6** raqamlari orqa tomondagi xuddi shu raqamlar ustiga tushishi kerak.
  2. Ikkala tomonning "YUQORI CHETI" yozuvi bir chetda bo'lishi kerak.
  3. Old tomondagi oq "2026" qismi orqa tomondagi oq "D" logotipli qism ustiga tushadi (ikkalasi 32.17 mm).
  4. Kesish belgilari ikki tomonda ustma-ust tushadi.
- Orqa tomon hamma listda bir xil. Oxirgi (1871-) listda faqat 2 ta orqa bor — old tomondagi 2 ta biletga mos.

## Ranglar

- Artwork **CMYK, ISO Coated v2 (ECI)**. Bu profil dizayner PDF'ining o'zida joylashgan; Relative Colorimetric + BPC bilan o'tkazilgan.
- QR, raqam, SEKTOR/QATOR/JOY — **faqat 100% K**. Kesish belgilari Registration.
- RIP'da: CMYK ma'lumotni qayta konvertatsiya qilmang ("Preserve CMYK numbers"), output intent FOGRA39.
- Faylda asl dizayndan qolgan shaffoflik (Multiply, yumshoq niqob) bor. RIP PDF 1.4+ shaffoflikni qo'llashi kerak (APPE yoki zamonaviy RIP).
- Ekrandagi yorqin qizil (sRGB) CMYK'da biroz xiralashadi — bu gamut chegarasi.

## CorelDRAW'da ishlash

- **Tavsiya:** tayyor PDF'ni to'g'ridan-to'g'ri RIP'ga yuboring. CorelDRAW'da qayta saqlash ranglar, shaffoflik va shriftlarni o'zgartirishi mumkin.
- Faqat ko'rish yoki bitta list kerak bo'lsa: *File → Import* (PDF) → kerakli sahifa → "Import text as: Text". Rang boshqaruvini "Preserve CMYK" qilib qo'ying.
- O'zgaruvchan ma'lumotni CorelDRAW Print Merge bilan qilmoqchi bo'lsangiz, `DUSEL_MASTER_11222.csv` dan foydalaning (TICKET_NUMBER, SECTOR, ROW, SEAT, QR_URL). Lekin tekshirilgan yo'l — tayyor PDF.
- Katta fayllarni bo'lib chop etish kerak bo'lsa, PDF sahifa oralig'ini tanlang (masalan 1–500, 501–1000 …). Sahifa = list raqami.

## Bosishdan oldin

1. Proof (`DUSEL_PROOF_6UP_CMYK.pdf`) ni tasdiqlang.
2. Duplex sinov listini bosib, yuqoridagi 4 bandni tekshiring.
3. 1-, 936- va 1871-listlardan bittadan bosib, QR'ni telefonda skanerlang.
4. Istisno qatorlar (`ISTISNOLAR_HISOBOTI.md`, 22 qator, 464 joy) zalda tekshirilishi kerak.
