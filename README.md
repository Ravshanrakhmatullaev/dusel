# DUSEL GROUP — Yulduzli Kecha · QR bilet sahifasi

Static sahifa (GitHub Pages). Har bir QR `https://ravshanrakhmatullaev.github.io/dusel/?code=NNNNN` ga olib boradi.
`00001`–`11222` qabul qilinadi. Sahifa bilet raqami va SEKTOR/QATOR/JOY ni ko'rsatadi; biletning haqiqiyligini tasdiqlamaydi.

## Yagona manba
`production/DUSEL_MASTER_11222.csv` — 11 222 bilet (TICKET_NUMBER, SECTOR, ROW, SEAT, ZONE, STATUS, QR_URL).

```
места.xlsx ──tools/build_master.py──► production/DUSEL_MASTER_11222.csv
                                         ├─ tools/sync_site.py   ─► data/seats/s0..s11.json (sayt)
                                         ├─ tools/gen_qr.py      ─► QR SVG/PNG
                                         └─ tools/impose_prod.py ─► FRONT/BACK 6-up CMYK PDF
tools/final_tests.py + tools/test_site_final.mjs — yakuniy tekshiruv
```
STATUS: `ASSIGNED` / `REVIEW_REQUIRED` (Excel izohi raqamlashni noaniq qiladi — `audit/ISTISNOLAR_HISOBOTI.md`).
Raqamlash ketma-ket (har qatorda 1 dan), zalda fizik tekshirilmagan.
Katta bosma fayllar (PDF, QR ZIP) repoga qo'shilmaydi.
