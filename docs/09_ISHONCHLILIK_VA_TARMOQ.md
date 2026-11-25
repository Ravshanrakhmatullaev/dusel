# 09 — Ishonchlilik: tarmoq, uskunalar, uzilish tartibi, mashq

Maqsad: internet yoki server muammosi **hech qachon jimgina "muvaffaqiyatli kirish"ga aylanmasligi** va darvozalar tez tiklanishi. Bu hujjat uptime kafolati bermaydi.

## 1. Arxitektura

```
 Darvoza telefonlari / 2D skanerlar ──Wi-Fi (faqat xodimlar, WPA2/3, yashirin emas, alohida SSID)──┐
 Nazoratchi ish stoli (noutbuk, simli) ─────────────────────────────────────────────────────────┤
                                                                                               Router (avtomatik failover)
                                                       ┌──────────── 1-provayder: simli (optika) ──┤
                                                       └──────────── 2-provayder: boshqa operator (LTE/5G modem yoki 2-optika)
 UPS: router, modem(lar), switch, Wi-Fi nuqtalari, nazoratchi noutbuki (kamida 60 daqiqa)
 Har darvoza telefonida: o'z mobil interneti (3-zaxira) — Wi-Fi o'chsa telefon avtomatik mobil tarmoqqa o'tadi
```

Server tomoni: Cloudflare Pages (sahifalar) + Supabase Pro (baza/Auth). Darvozalar faqat HTTPS orqali ishlaydi.

## 2. Uskunalar ro'yxati (tavsiya)

| Uskuna | Soni | Izoh |
|---|---|---|
| Darvoza telefonlari (Android 10+/iPhone iOS 16+) | darvozalar × 2 + 4 zaxira | `/scan-test` dan o'tgan, zaryad 100%, powerbank |
| 2D QR skaner (USB/Bluetooth, HID klaviatura rejimi, US tartib, suffiks Enter) | darvozalar × 1 + 2 zaxira | `/scan-test` da sinalgan; OTG adapter (Android) |
| Router (dual-WAN failover) | 1 + zaxira | failover ≤ 30 s sozlangan |
| 2-provayder modemi | 1 | boshqa operator |
| UPS | 1–2 | router + modem + switch + Wi-Fi |
| Wi-Fi nuqtalari | zalga qarab | darvozalar yonida signal ≥ −65 dBm |
| Nazoratchi ish stoli | 1 (+1 zaxira) | `tools/monitor.mjs`, dashboard, favqulodda qurilma |

Tashqi skaner sozlamasi: HID (klaviatura), **US** tartib, prefiks yo'q, suffiks **Enter**. Telefon klaviaturasi rus (kirill) tartibida bo'lsa ham ilova URL'ni tiklaydi (sinovdan o'tgan), lekin skaner US tartibda bo'lishi afzal.

## 3. Uzilish tartibi (darvozalar uchun qisqa)

1. Ekranda **"NATIJA NOMA'LUM — KIRITMANG"** yoki **"SERVER BILAN ALOQA YO'Q"** → mijozni **o'tkazmang**.
2. "Qayta urinish" (xavfsiz — bir xil so'rov ikki marta kiritmaydi).
3. 30 soniyada tiklanmasa: telefon Wi-Fi'ni o'chirib mobil internetga o'ting → "Qayta urinish".
4. Baribir yo'q → nazoratchini chaqiring. **Darvoza mustaqil oflayn kiritmaydi** (ilovada bunday tugma yo'q, server ham qabul qilmaydi).

## 4. Nazoratchi qarorlari

| Holat | Qaror |
|---|---|
| Bitta darvoza | qurilmani almashtirish / mobil internet |
| Hamma darvoza, internet yo'q | router failover'ni tekshirish; 2-provayder; navbatni to'xtatish (e'lon) |
| Internet bor, server javob bermaydi | `monitor.mjs` va status.supabase.com; navbat to'xtatiladi |
| 5+ daqiqa tiklanmasa | **Nazoratli favqulodda rejim** (tashkilotchi rahbari ruxsati bilan): faqat Admin oldindan belgilagan **bitta** nazoratchi qurilmasi, kod bilan; qolgan darvozalar yopiq. Har yozuv "NAZORAT OSTIDA QAYD ETILDI — server tasdiqlamagan" (yashil emas). Aloqa qaytgach sinxronlanadi, ziddiyatlar `OFFLINE_CONFLICT` holatiga |

Favqulodda qurilma bitta bo'lgani uchun ikki mustaqil oflayn qurilma bir biletni qabul qila olmaydi. Qolgan cheklov: oflayn paytda shu qurilma boshqa darvozalar avval kiritgan biletni bilmaydi — bu ziddiyatlar sinxronlashda aniqlanadi (T19b).

## 5. Monitoring

- **Nazoratchi ish stolida**: `tools/monitor.mjs` (har 15 s): `/checkin` sayt, Supabase Auth sog'ligi, RPC kechikishi, kirish holati, har darvozaning oxirgi skan vaqti (3 daqiqadan eski bo'lsa ogohlantirish), sig'im invarianti. Muammo — qizil qator + ovoz + `monitor_log.csv`.
- **Panel** (`/checkin` → Panel): har 15 s yangilanadi — darvozalar, 15 daqiqalik oqim, takror skanlar, ochiq holatlar, sig'im nazorati.
- Tashqi: Supabase status sahifasi; Cloudflare status sahifasi.

## 6. Failover sinovi (konsertdan oldin, zalda) — bayonnoma shabloni

**Haqiqiy ma'lumot bilan EMAS**: staging muhitida (`feature-checkin…/checkin`, STAGING baza) va sinov biletlari bilan.

| # | Qadam | Kutilgan natija | Haqiqiy natija | Vaqt |
|---|---|---|---|---|
| F1 | 4 darvoza telefoni staging'da skanerlamoqda (sinov rejimi) | yashil/qizil natijalar | | |
| F2 | 1-provayder kabelini sug'urish | router ≤ 30 s da 2-provayderga o'tadi; darvozalarda ko'pi bilan bitta "NATIJA NOMA'LUM" → "Qayta urinish" bilan tiklanadi | | |
| F3 | Kabelni qaytarish | qaytadi, uzilish yo'q yoki qisqa | | |
| F4 | Ikkala provayder o'chiriladi | hamma darvozada "SERVER BILAN ALOQA YO'Q"; **bitta ham yashil yo'q** | | |
| F5 | Telefon Wi-Fi o'chiriladi (mobil internet) | darvoza ishlaydi | | |
| F6 | UPS: tok o'chiriladi | router/modem ishlashda davom etadi | | |
| F7 | Favqulodda qurilma: kod bilan rejim, 5 sinov bileti | sariq "NAZORAT OSTIDA" | | |
| F8 | Internet qaytariladi | navbat sinxronlanadi, ziddiyat holati ochiladi | | |
| F9 | `monitor.mjs` | F2/F4 da qizil ogohlantirish | | |
| F10 | Staging tozalash (`tools/staging_reset.sh`) | sinov yozuvlari o'chadi | | |

Imzolar: texnik rahbar ____ nazoratchi ____ sana ____

## 7. Insident mashqi (T−7 va T−2 kun, 30 daqiqa)

1. **Ssenariy A — takror bilet**: nazoratchiga ikki "mijoz" bir xil 06114 bilan → holat, dalil, isbotli zaxira joydan almashtirish yoki "Tashkilotchiga".
2. **Ssenariy B — server uzilishi**: F4 ni takrorlash; darvozalar to'xtashini, e'lon matnini, favqulodda qurilmaga o'tishni mashq qilish.
3. **Ssenariy C — telefon yo'qoldi**: Admin → sessiyani bekor qilish → u telefon keyingi amalda chiqariladi (T18b).
4. **Ssenariy D — kamera ishlamaydi**: yo'riqnoma → tashqi skaner → qo'lda raqam + bilet qog'ozidagi sektor/joyni ko'z bilan solishtirish.
Har mashqdan keyin: nima sekin bo'ldi, kim nima qilmadi — 02/03 hujjatlarni yangilash.
