# DUSEL GROUP — Yulduzli Kecha · QR bilet sahifasi

Rasmiy sayt: **https://dusel.pages.dev** (Cloudflare Pages, `main` branchdan).
Har bir QR `https://dusel.pages.dev/?code=NNNNN` ga olib boradi; `00001`–`11222` qabul qilinadi.
Sahifa faqat bilet raqami va tadbir ma'lumotini ko'rsatadi; biletning haqiqiyligini tasdiqlamaydi.

Bosma uchun ma'lumot va vositalar (master, QR, PDF) `prep/11222-ticket-capacity` branchida.

## Kuponlar (GOLD / SILVER)

Kupon QR'lari alohida sahifaga olib boradi — bilet tizimiga tegmaydi:

- Gold: `https://dusel.pages.dev/coupon?type=gold&code=0001` … `2000`
- Silver: `https://dusel.pages.dev/coupon?type=silver&code=0001` … `4000`

`coupon.html` faqat kupon turi va raqamini ko'rsatadi; kuponning haqiqiyligini tasdiqlamaydi.

## GAL vaucherlar — "Ishonchli hamkorlar aksiyasi" (1 250 000 so'mlik)

- QR: `https://dusel.pages.dev/gal?code=000001` … `001000` (1000 ta, 6 xonali)
- Sahifa: `gal.html` — faqat vaucher raqamini ko'rsatadi; haqiqiylikni tasdiqlamaydi.

## QR yo'llari reyestri (o'zgartirmang)

| Tizim | URL | Diapazon | Sahifa |
|---|---|---|---|
| Bilet | `/?code=NNNNN` | 00001–11222 | `index.html` |
| GOLD kupon | `/coupon?type=gold&code=NNNN` | 0001–2000 | `coupon.html` |
| SILVER kupon | `/coupon?type=silver&code=NNNN` | 0001–4000 | `coupon.html` |
| GAL vaucher | `/gal?code=NNNNNN` | 000001–001000 | `gal.html` |

`404.html`: `/gal…` va `/coupon…` ko'rinishidagi noto'g'ri yo'llar o'z sahifasiga qaytariladi (bilet sahifasiga emas); qolganlari avvalgidek `/?code=invalid`.
Bosilgan QR'lar shu domen va yo'llarga bog'liq — `dusel.pages.dev`, `index.html`, `coupon.html`, `gal.html` nomlarini o'zgartirmang/o'chirmang.
