# DUSEL GAL — 8-up test varag'i (320 × 450 mm) · QA

Sana: 2026-11-04 · Holat: **FAQAT TEST VARAQ — tasdiq kutilmoqda.** Qolgan 992 ta vaucher tayyorlanmadi.

## Natija: 14/14 PASS

| Parametr | Qiymat |
|---|---|
| Fayl | `DUSEL_GAL_TEST_8UP_320x450.pdf` — 1 sahifa |
| Varaq | **320 × 450 mm** (portret) |
| Vaucher | **156.04 × 66.29 mm** — asl dizayn proporsiyasi (2.354 : 1), cho'zilmagan |
| Joylash | 8 ta: 4 ustun × 2 qator, vaucherlar 90° burilgan (varaq eniga 4 ta sig'ishi uchun) |
| Tartib | 1-qator: 0001 · 0002 · 0003 · 0004 — 2-qator: 0005 · 0006 · 0007 · 0008 (chapdan o'ngga) |
| Vaucherlar orasi | 4 mm kesish oralig'i (har vaucherga 2 mm bleed — chetdagi qizil fon davomi) |
| Varaq chetlari | chap/o'ng 21.42 mm, yuqori/past 66.96 mm (trimgacha) |
| Kesish belgilari | tashqi hoshiyada, har kesish chizig'iga 2 ta: 8 vertikal + 4 gorizontal = 24 ta; Registration, 0.25 pt, 5 mm, trimdan 3 mm |
| Raqam | `Nº 0001` … `Nº 0008` — dizayndagi "SERIYA NOMER:" yonida (Inter Display Medium 4.7 pt, K100, vektor) |
| QR | `https://dusel.pages.dev/gal?code=0001` … `0008`; 16.89 mm (oq hoshiya bilan), QR v4-Q, vektor K100 |
| Rang | sRGB → ISO Coated v2 (ECI) / FOGRA39; OutputIntent bor (PDF/X deb da'vo qilinmaydi) |

## Tekshiruvlar

| # | Tekshiruv | Natija | Tafsilot |
|---|---|---|---|
| 1 | Varaq o'lchami aynan 320 × 450 mm (1 sahifa) | ✅ PASS | 320.000 × 450.000 mm |
| 2 | Har vaucher aynan 156.04 × 66.29 mm (varaqda 90° burilgan: 66.29 eni × 156.04 bo'yi) | ✅ PASS | [(66.29, 156.04)] |
| 3 | Varaqda aynan 8 ta vaucher | ✅ PASS |  |
| 4 | Raqamlar 0001–0008 (1-qator 0001–0004, 2-qator 0005–0008, chapdan o'ngga) | ✅ PASS | ['0001', '0002', '0003', '0004', '0005', '0006', '0007', '0008'] |
| 5 | Har QR havolasi https://dusel.pages.dev/gal?code=<4 xonali raqam> | ✅ PASS |  |
| 6 | Har vaucherda bitta bosilgan seriya raqami "Nº 000N", o'z joyida | ✅ PASS | [] |
| 7 | Har QR (8/8) 300 dpi'da dekod qilindi va o'z vaucher raqamiga mos | ✅ PASS | QR [(16.89, 16.89)] mm |
| 8 | Qo'shimcha: QR past ruxsatda ham (120 dpi) o'qiladi | ✅ PASS | [] |
| 9 | Hammasi varaq ichida, ustma-ust tushmaydi; vaucherlar orasida 4 mm kesish oralig'i (2 + 2 mm bleed) | ✅ PASS | eng kichik chet 19.4 mm, oraliqlar [4.0, 74.29] mm, ustma-ust [] |
| 10 | QR va raqam kesish chizig'idan ≥3 mm ichkarida (kesilmaydi) | ✅ PASS |  |
| 11 | Kesish belgilari: har bir kesish chizig'iga 2 ta (tashqi hoshiyada), Registration, 0.25 pt, 5 mm; vaucher ustiga tushmaydi | ✅ PASS | 24 belgi = 2 × (8 vertikal + 4 gorizontal kesish), uzunlik [5.0] mm |
| 12 | Dizayn cho'zilmagan: vaucher nisbati asl rasm bilan bir xil | ✅ PASS | vaucher 2.3539, asl 2.3538 |
| 13 | Dizayn asl rasm bilan mos (o'zgaruvchi zonalardan tashqari; farq faqat RGB→CMYK) | ✅ PASS | o'rtacha farq 4.6/255 |
| 14 | Shrift embed (subset), rasm CMYK ISO Coated v2, OutputIntent bor | ✅ PASS | {'IWDITZ+Inter Display Medium'} |

## GAL raqamlash 4 xonaliga o'tkazildi
- QR havolalari: `https://dusel.pages.dev/gal?code=0001` … `1000`.
- Sayt (`gal.html`) endi faqat 4 xonali `0001–1000` ni qabul qiladi — **production'ga chiqarildi va tekshirildi** (GitHub serveridan: `/gal?code=0001`, `/gal?code=1000` yangi versiya bilan ochiladi; bilet, GOLD, SILVER sahifalari o'zgarmagan).
- Yo'llar testi (40/40): GAL 0001/0100/1000 va tasodifiy kodlar to'g'ri; `1001`, `0000`, `000001`, `001000`, `11222` → xato (GAL sahifasida); test varag'idagi 8 ta QR ochilganda aynan o'z raqami ko'rinadi.
- ⚠️ Eski 6 xonali GAL fayllari (`DUSEL_GAL_MASTER` 000001…, `DUSEL_GAL_QR_1000.zip`, avvalgi GAL PDF'lar) **endi yaroqsiz** — ularni bosmang. Yangi master/QR/to'liq PDF test varag'i tasdiqlangandan keyin yaratiladi.

## Bosishdan oldin
1. Test varag'ini bosing, kesing va o'lchamni tekshiring (156.04 × 66.29 mm).
2. 2–3 telefon bilan QR'larni skanerlang — `Nº 0001` … `0008` chiqishi kerak.
3. Ma'qul bo'lsa — 1000 talik to'liq fayl (125 varaq × 8) tayyorlanadi.
