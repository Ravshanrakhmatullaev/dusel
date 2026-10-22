# DUSEL GROUP — Yulduzli Kecha · QR bilet sahifasi

Static sahifa (GitHub Pages). Rasmiy sayt: **https://dusel.pages.dev** (Cloudflare Pages, `main` branchdan). Har bir QR `https://dusel.pages.dev/?code=NNNNN` ga olib boradi.
`00001`–`11222` qabul qilinadi. Sahifa bilet raqami va SEKTOR/QATOR/JOY ni ko'rsatadi; biletning haqiqiyligini tasdiqlamaydi.

## Yagona manba
`production/DUSEL_MASTER_FINAL.csv` — 11 222 bilet (TICKET_NUMBER, ZONE, SECTOR, ROW, SEAT, QR_URL, SOURCE_SHEET, STATUS).
Blitcher A201/A205/C209/C213 — 0 joy (bilet yo'q); shu kodli 2-этаж sektorlari alohida va joylari bor.

```
места.xlsx ──tools/build_master.py──► production/DUSEL_MASTER_FINAL.csv
                                         ├─ tools/sync_site.py   ─► data/seats/s0..s11.json (sayt)
                                         ├─ tools/gen_qr.py      ─► QR SVG/PNG
                                         └─ tools/impose_prod.py ─► FRONT (1871 list) + BACK (1 sahifa) 6-up CMYK PDF
tools/final_tests.py + tools/test_site_final.mjs — yakuniy tekshiruv
```
STATUS: `ASSIGNED` / `REVIEW_REQUIRED` (Excel izohi raqamlashni noaniq qiladi — `audit/ISTISNOLAR_HISOBOTI.md`).
Raqamlash ketma-ket (har qatorda 1 dan), zalda fizik tekshirilmagan.
Katta bosma fayllar (PDF, QR ZIP) repoga qo'shilmaydi.
