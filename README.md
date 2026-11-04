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

## QR yo'llari reyestri — har bir mahsulot o'z yo'lida (o'zgartirmang)

| Tizim | Yangi QR URL | Kod | Diapazon | Sahifa |
|---|---|---|---|---|
| Konsert bileti | `https://dusel.pages.dev/ticket?code=NNNNN` | 5 xona | 00001–11222 | `ticket.html` |
| GAL vaucher | `https://dusel.pages.dev/gal?code=NNNN` | 4 xona | 0001–1000 | `gal.html` |
| GOLD kupon | `https://dusel.pages.dev/gold?code=NNNN` | 4 xona | 0001–2000 | `gold.html` |
| SILVER kupon | `https://dusel.pages.dev/silver?code=NNNN` | 4 xona | 0001–4000 | `silver.html` |

Har sahifa faqat o'z yo'li, kod uzunligi va diapazonini qabul qiladi; noto'g'ri kodda **o'sha sahifaning o'zida** xato ko'rsatiladi — boshqa mahsulotga hech qachon yo'naltirilmaydi.

Eski havolalar (avval chop etilgan bo'lsa ishlashi uchun saqlangan, faqat o'z mahsuloti):
- `/?code=NNNNN` → `index.html` — faqat bilet (5 xona, 00001–11222)
- `/coupon?type=gold|silver&code=NNNN` → `coupon.html` — faqat GOLD/SILVER kupon

`404.html` — neytral "Sahifa topilmadi"; faqat o'sha yo'lning yozilishini to'g'rilaydi (`/GAL` → `/gal`, `/ticket/` → `/ticket`), boshqa mahsulotga yubormaydi.
Bosilgan QR'lar shu domen va yo'llarga bog'liq — `dusel.pages.dev` va yuqoridagi fayl nomlarini o'zgartirmang/o'chirmang.
