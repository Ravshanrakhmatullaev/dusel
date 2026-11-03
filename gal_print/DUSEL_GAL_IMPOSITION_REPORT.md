# DUSEL GAL — bosma impozitsiyasi hisoboti

Sana: 2026-11-03 · Branch: `feature/gal-voucher` (PR #2, merge qilinmagan) · Holat: **PROOF — tasdiq kutilmoqda, ommaviy bosish ruxsat etilmagan**

## Asosiy ko'rsatkichlar

| Parametr | Qiymat |
|---|---|
| Asl dizayn | `Vaucher(1).png` — Photoshop eksporti, 3686 × 1566 px, **600 ppi**, RGB (ICC profilsiz) |
| **Vaucher o'lchami** | **156.04 × 66.29 mm** — faylning o'z 600 ppi o'lchami (dizaynerning hujjat o'lchami). ⚠️ *Taklif — tasdiqlanmagan* |
| Proporsiya | 2.3538 : 1 — asl bilan bir xil (cho'zilmagan) |
| Bosma varaq | 450 × 320 mm |
| Joylash | 2 ustun × 4 qator = **8 ta vaucher / varaq**, hammasi bir xil yo'nalishda |
| Jami varaqlar | **125** (1000 / 8 — hammasi to'liq; chala varaq yo'q) |
| Ketma-ketlik | 1-varaq 000001–000008, 2-varaq 000009–000016 … 125-varaq 000993–001000 (har varaqda chapdan o'ngga, yuqoridan pastga) |
| Kesish oralig'i | Vaucherlar orasida **4 mm** (har vaucherga 2 mm bleed) — har vaucher alohida kesiladi (ikki tomonlama kesish) |
| Bleed | 2 mm — asl faylda bleed yo'q, shuning uchun chetdagi qizil fon 2 mm cho'zildi (sintetik bleed) |
| Varaq chetlari | chap/o'ng 66.96 mm, yuqori/past 21.42 mm (trim chizig'igacha) |
| Kesish belgilari | Har bir kesish chizig'i uchun tashqi hoshiyada 2 tadan: Registration (C100 M100 Y100 K100), 0.25 pt, uzunligi 5 mm, trimdan 3 mm uzoqlikda |
| Xavfsiz zona | QR va raqam kesish chizig'idan kamida 3 mm ichkarida (tekshirildi) |
| **QR o'lchami** | **16.89 × 16.89 mm** (oq hoshiya bilan); belgining o'zi 13.6 mm, modul 0.41 mm; QR versiya 4, xato tuzatish Q (~25%), 4 modul oq hoshiya; vektor, K100 |
| Seriya raqami | `Nº 000001` — dizayndagi joyida, "SERIYA NOMER:" yonida; Inter Display Medium 4.7 pt (asl namunaga piksel bo'yicha eng mos shrift), K100, vektor matn |
| Namuna qiymatlar | Dizayndagi namuna `Nº 000100` va namuna QR oq fon bilan yopilib, har vaucherga o'zi qo'yildi; ISM va SANA bo'sh qoldirildi |
| **Rang profili** | Rasm sRGB deb qabul qilindi → **ISO Coated v2 (ECI) / FOGRA39** CMYK, Relative Colorimetric + BPC; PDF OutputIntent: ISO Coated v2 (ECI). PDF/X sertifikati da'vo qilinmaydi |
| Rasm sifati | 600 ppi (100% masshtab); dizayn rasmi PDF ichida bitta obyekt, barcha vaucherlarda qayta ishlatiladi |
| Fayllar | `DUSEL_GAL_1000_PRINT_450x320.pdf` (125 varaq, 9.9 MB), `DUSEL_GAL_8UP_TEST.pdf` (1 varaq, 000001–000008) |

Har varaqning pastki chetida (kesiladigan qismdan tashqarida) texnik qator bor: varaq raqami, shu varaqdagi raqamlar oralig'i, o'lcham va rang profili.

## Nega 8 ta (6 ta emas)

Asl o'lchamda (156 × 66 mm) varaqqa 8 tasi sig'adi; 6 tasini joylash uchun vaucherni 213 × 90.5 mm gacha kattalashtirish kerak bo'lardi (125 o'rniga 167 varaq). Shu sababli `DUSEL_GAL_6UP_TEST.pdf` o'rniga **`DUSEL_GAL_8UP_TEST.pdf`** tayyorlandi.

Boshqa variantlar (450 × 320, chetlar ≥10 mm, oraliq 4 mm):

| Varaqda | Vaucher o'lchami | Masshtab | Varaqlar (1000 ta) | Izoh |
|---|---|---|---|---|
| 6 (2×3) | 213.0 × 90.5 mm | 137% | 167 | eng yirik, mayda matn ~4.5 pt |
| **8 (2×4)** | **156.0 × 66.3 mm** | **100%** | **125** | **tanlangan — dizayner o'lchami** |
| 8 (2×4) | 169.5 × 72.0 mm | 109% | 125 | xuddi shu varaq soni, biroz yirikroq |
| 12 (3×4) | 140.7 × 59.8 mm | 90% | 84 | qog'oz tejaladi, lekin mayda matn ~3 pt |

Siz boshqa o'lcham tanlasangiz, fayl bir buyruqda qayta chiqariladi (`gal_layout.json` → `voucher_mm`, `layout`).

## Tekshiruvlar — 35/35 PASS

1. Bosilgan vaucherlar soni = 1000 ✔
2. Raqamlar 000001–001000, ketma-ket, tushib qolgan yo'q ✔
3. Takroriy raqam yo'q ✔
4. **Har bir bosilgan QR (1000/1000)** PDF'dan 300 dpi'da render qilinib dekod qilindi — o'sha vaucherning raqamiga mos ✔
5. Har bir QR manzili `https://dusel.pages.dev/gal?code=<raqam>` ✔ (QR va master avvalgidek — `DUSEL_GAL_QR_1000.zip` va master CSV SHA-256 bo'yicha o'zgarmagan)
6. Bilet (`index.html`) va GOLD/SILVER (`coupon.html`) sahifalari `main` bilan bayt-bayt bir xil ✔
7. Vaucherlar kesilmaydi va ustma-ust tushmaydi (trim va bleed) ✔; QR va raqam trimdan ≥3 mm ichkarida ✔
8. Hammasi 450 × 320 mm varaq ichida, chetdan ≥7 mm ✔
9. Har varaqda 8 ta (125 × 8) ✔
10. Har vaucherda bitta seriya raqami, o'z joyida, QR bilan bir xil ✔
11. Kesish belgilari: 4 vertikal + 8 gorizontal kesish chizig'i × 2 = 24 ta belgi ✔
12. Shrift embed qilingan (subset) ✔; OutputIntent ISO Coated v2 ✔; rasm CMYK ✔
13. Dizayn mosligi: proof'dagi vaucher asl rasm bilan solishtirildi (o'zgaruvchi zonalardan tashqari) — o'rtacha farq 5.3/255 (faqat RGB→CMYK konvertatsiyasi farqi) ✔; proporsiya 2.3539 / 2.3538 ✔

## Ochiq xavflar (bosishdan oldin hal qilish kerak)

1. **Fizik o'lcham tasdiqlanmagan.** 156.04 × 66.29 mm — faylning 600 ppi metama'lumotidan olingan. Tasdiqlang yoki boshqa o'lcham ayting.
2. **Asl fayl RGB PNG, CMYK original emas.** ICC profil yo'q (sRGB deb qabul qilindi). Yorqin qizil va oltin rang bosmada ekrandagidan biroz xiraroq chiqishi mumkin. Imkon bo'lsa, dizaynerdan qatlamli PSD yoki CMYK PDF so'rang; aks holda bosmaxonada rang probasi (proof) qiling.
3. **Bleed sintetik.** Chetdagi qizil fon 2 mm cho'zildi — fon bir tekis bo'lgani uchun ko'rinmaydi, lekin dizaynerning o'z bleed'i yaxshiroq.
4. **Mayda matn.** Pastki shartlar qatori asl o'lchamda ~0.8 mm bosh harf (~3.3 pt), "15 kun" qatori ~0.75 mm. Dizaynerning tanlovi; o'qiladi, lekin juda mayda. Kattaroq kerak bo'lsa — 169.5 × 72 mm (8 ta) yoki 213 × 90.5 mm (6 ta).
5. **Matnlar rasm ichida** (vektor emas) — 600 ppi'da aniq, lekin vektor matnchalik o'tkir emas. Seriya raqami va QR esa vektor.
6. **QR skaneri:** test varag'ini bosib, 2–3 xil telefon bilan skanerlang (13.6 mm QR — yaqindan yaxshi o'qiladi).
7. **Ommaviy bosish va `main`ga merge — tasdig'ingizdan keyin.** Production'da `/gal` sahifasi merge'dan keyin paydo bo'ladi; ungacha vaucherlarni tarqatmang.
