# DUSEL GAL — 1000 ta vaucher, to'liq bosma (320 × 450 mm, 8-up) · QA

Sana: 2026-11-04 · Asos: tasdiqlangan test varag'i `DUSEL_GAL_TEST_8UP_320x450.pdf`

## Natija: 18/18 PASS

| Parametr | Qiymat |
|---|---|
| Fayl | `DUSEL_GAL_1000_8UP_320x450_FINAL.pdf` |
| Varaqlar | **125** (har birida 8 ta, chala varaq yo'q) |
| Varaq | 320 × 450 mm |
| Vaucher | 156.04 × 66.29 mm (90° burilgan, 4 ustun × 2 qator) |
| Raqamlar | **0001 – 1000** (4 xonali), 6 xonali raqam yo'q |
| Tartib | 1-varaq: 0001–0004 / 0005–0008 · 2-varaq: 0009–0012 / 0013–0016 · … · 125-varaq: 0993–0996 / 0997–1000 |
| QR | `https://dusel.pages.dev/gal?code=0001` … `1000` (16.89 mm, vektor K100) |
| Kesish | vaucherlar orasida 4 mm; har varaqda 24 ta kesish belgisi |
| Rang | ISO Coated v2 (ECI) / FOGRA39 |

1-varaq tasdiqlangan test varag'i bilan piksel bo'yicha bir xil (faqat chap hoshiyadagi texnik qator "TEST" → "PRINT, varaq 1/125").

## Tekshiruvlar

| # | Tekshiruv | Natija |
|---|---|---|
| 1 | Master: 1000 ta, 0001–1000, 4 xonali, takrorsiz, tushib qolgan yo'q | ✅ |
| 2 | Master: QR_URL = https://dusel.pages.dev/gal?code=<4 xonali>; STATUS=NOT_ISSUED; ISM/SANA bo'sh | ✅ |
| 3 | Master: 6 xonali raqam (000001…) yo'q | ✅ |
| 4 | Master XLSX = CSV, raqam matn formatida (0001) | ✅ |
| 5 | QR PNG: 1000/1000 dekod, payload aynan /gal?code=<raqam> | ✅ |
| 6 | QR SVG: namuna (41 ta) dekod to'g'ri | ✅ |
| 7 | DUSEL_GAL_QR_1000.zip: GAL_0001…GAL_1000 (1000 SVG + 1000 PNG) + master CSV, butun | ✅ |
| 8 | Bosma: 125 varaq, har biri aynan 320 × 450 mm | ✅ |
| 9 | Bosma: jami 1000 vaucher, har varaqda 8 ta | ✅ |
| 10 | Bosma: har vaucher aynan 156.04 × 66.29 mm | ✅ |
| 11 | Bosma: tartib — har varaqda 1-qator n+1…n+4, 2-qator n+5…n+8; 0001–1000 ketma-ket, takrorsiz | ✅ |
| 12 | Bosma: barcha varaqlarda joylashuv bir xil (tasdiqlangan test varag'idagidek) | ✅ |
| 13 | Bosma: har vaucherda bitta bosilgan raqam "Nº 0001"…"Nº 1000", o'z joyida | ✅ |
| 14 | Bosma: 1000/1000 QR PDF'dan 300 dpi'da dekod qilindi — har biri o'z vaucher raqamiga mos | ✅ |
| 15 | Bosma: hech biri kesilmaydi/ustma-ust tushmaydi, hammasi varaq ichida; QR va raqam trimdan ≥3 mm ichkarida | ✅ |
| 16 | Bosma: har varaqda 24 ta kesish belgisi (8 vertikal + 4 gorizontal kesish × 2), 0.25 pt Registration | ✅ |
| 17 | 1-varaq tasdiqlangan test varag'i bilan piksel bo'yicha bir xil (texnik qatordan tashqari) | ✅ |
| 18 | Shrift embed (subset), OutputIntent ISO Coated v2, dizayn rasmi bitta obyekt (CMYK) | ✅ |

## Sayt
`https://dusel.pages.dev/gal?code=0001` … `1000` — production'da ishlaydi (4 xonali); `000001` kabi 6 xonali kodlar qabul qilinmaydi.

## Fayllar
- `DUSEL_GAL_1000_8UP_320x450_FINAL.pdf` — bosmaga
- `DUSEL_GAL_MASTER.xlsx` / `.csv` — 0001–1000 (STATUS, ISSUE_DATE, RECIPIENT_NAME ustunlari bilan)
- `DUSEL_GAL_QR_1000.zip` — GAL_0001 … GAL_1000 (SVG + PNG)

Eski 6 xonali GAL fayllari yaroqsiz — ishlatmang.
