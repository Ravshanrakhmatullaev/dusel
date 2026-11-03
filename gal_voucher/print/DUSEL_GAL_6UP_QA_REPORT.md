# DUSEL GAL — 6-up 200 × 100 mm bosma: QA hisoboti

Sana: 2026-11-03 · Holat: **PROOF — tasdiq kutilmoqda; ommaviy bosish ruxsat etilmagan**

## Natija: 35/35 PASS (+ geometriya va tartib tekshiruvi)

| Parametr | Qiymat |
|---|---|
| Varaq | **450 × 320 mm** |
| Vaucher (tayyor o'lcham) | **200 × 100 mm** |
| Varaqda | **6 ta — 2 ustun × 3 qator** |
| Jami | **1000 vaucher, 167 varaq**: 1–166-varaqlar 6 tadan, **167-varaq 4 ta** (000997–001000) |
| Tartib | 1-qator 000001 \| 000002 · 2-qator 000003 \| 000004 · 3-qator 000005 \| 000006 → keyingi varaqlarda davomi |
| Joylashuv | vaucherlar oralig'isiz (umumiy kesish chizig'i, chiptalar va kuponlardagidek); chap/o'ng 25 mm, yuqori/past 10 mm |
| Kesish chiziqlari | vertikal x = 25 / 225 / 425 mm; gorizontal y = 10 / 110 / 210 / 310 mm (oxirgi varaqda 10 / 110 / 210) |
| Kesish belgilari | Registration, 0.25 pt, 5 mm, trimdan 3 mm uzoqda — faqat tashqi hoshiyada; vaucher atrofida ramka yo'q |
| Bleed | tashqi tomonlarda 2 mm (fon davomi); ichki tomonlarda yo'q — qo'shni vaucher bilan ustma-ust tushish yo'q |
| QR | **21.65 × 21.65 mm** (oq hoshiya bilan), modul 0.53 mm, versiya 4-Q, vektor K100 |
| Seriya raqami | `Nº 000001` — dizayndagi "SERIYA NOMER:" yonida, Inter Display Medium 6.0 pt, K100, vektor |
| Rang | sRGB → ISO Coated v2 (ECI) / FOGRA39, Relative Colorimetric + BPC; OutputIntent bor. PDF/X deb da'vo qilinmaydi |
| Rasm sifati | ~468 ppi (200 mm kenglikda) |

## Dizaynni 200 × 100 ga moslash (cho'zmasdan)

Asl `Vaucher(1).png` nisbati 2.354 : 1 (3686 × 1566 px), 200 × 100 esa 2 : 1. Dizayn **cho'zilmadi va kesilmadi**:
- butun dizayn eni bo'yicha 200 mm ga bir xil masshtabda joylandi (balandligi 84.97 mm);
- yuqoriga 7.49 mm va pastga 7.54 mm **asl qizil fon davom ettirildi** (har ustunning chekka rangi, chetga qarab dizayn burchagidagi to'q qizilga silliq o'tadi);
- logo, sarlavha, bino va sovg'alar, summa, ISM / SERIYA NOMER / SANA maydonlari, QR qutisi va shartlar o'z joyida, o'zaro nisbati o'zgarmagan.
- Tekshiruv: asl dizayn qismi eni/bo'yi nisbati 2.3538 = asl 2.3538; asl rasm bilan o'rtacha farq 5.8/255 (faqat RGB→CMYK).

## Tekshiruvlar

1. 1000 ta vaucher, 000001–001000, ketma-ket, takrorsiz ✔
2. 167 varaq; 166 × 6 + 4 ✔; har varaqdagi tartib (slot 1–6) va koordinatalar aynan talabdagidek ✔ (0 xato)
3. Har vaucher 200.00 × 100.00 mm ✔; hammasi varaq ichida ✔; ustma-ust tushish yo'q ✔
4. **1000/1000 QR** PDF'dan 300 dpi'da render qilinib dekod qilindi — har biri o'sha vaucherdagi raqamga mos (`https://dusel.pages.dev/gal?code=<raqam>`) ✔
5. Har vaucherda bitta bosilgan seriya raqami, QR bilan bir xil ✔
6. QR va raqam kesish chizig'idan ≥3 mm ichkarida ✔
7. Kesish belgilari: 3 vertikal + 4 gorizontal × 2 = 14 ta ✔
8. Shrift embed (subset) ✔, OutputIntent ✔, rasm CMYK va bitta obyekt ✔
9. GAL master va QR arxivi o'zgarmagan (SHA-256 bir xil) ✔

## Ochiq xavflar
1. Asl fayl RGB PNG (ICC yo'q) — bosmaxonada rang probasi tavsiya etiladi.
2. Yuqori/pastki 7.5 mm fon — dizayner qo'shmagan, men davom ettirdim; ko'zdan kechiring.
3. Test varag'ini bosib, 2–3 telefon bilan QR'ni skanerlang.
4. `/gal` sahifasi production'da faqat PR #2 tasdiqlanib `main`ga qo'shilgandan keyin ishlaydi — ungacha tarqatmang.

Fayllar: `DUSEL_GAL_6UP_200x100_TEST.pdf`, `DUSEL_GAL_6UP_200x100_PREVIEW.png`, `DUSEL_GAL_1000_6UP_200x100_FINAL.pdf`.
