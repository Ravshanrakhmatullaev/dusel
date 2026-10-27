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
