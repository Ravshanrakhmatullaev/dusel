# DUSEL — joylar bo'yicha istisnolar hisoboti (11 222 bilet)

Manba: `места.xlsx` (SHA-256 `dfe3d2185d22485d…`). Prep-branch auditida tilga olingan `места(2).xlsx` bu sessiyaga yuborilmagan; foydalanilgan fayl bilan qavat jamlari (1 896 / 3 519 / 5 807), 48 ta sektor bloki va 481 ta qator yozuvi auditdagi bilan aynan mos.

## Qo'llangan qoidalar (mijoz tasdiqlagan)

- Faqat Блитчеры, 2-этаж, 4-этаж. `балкон 3-vip` (571 VIP/loja joyi) to'liq chiqarib tashlandi.
- Tartib: SEKTOR (201→216, keyin 401→416) → QATOR → JOY. Bir xil sektor kodi blitcherda (1–8 qatorlar) va 2-qavatda (9–18 qatorlar) bor — ular bitta sektor sifatida qator bo'yicha ketma-ket. A201, A205, C209, C213 sektorlarida blitcher joylari yo'q (Excel: "Итого: НЕТ"), shuning uchun **00001 = A201, 9-qator, 1-joy**.
- Har qatorda joy 1 dan boshlanadi; soni Excel'dagi "Кол-во мест". Izohdagi qo'shimcha joylar qo'shilmadi.
- Raqamlash ketma-ket hisoblangan, **zalda fizik tekshirilmagan**. `REVIEW_REQUIRED` — Excel izohi raqamlashni noaniq qiladigan joylar; biletga baribir ketma-ket raqam bosiladi (mijoz qoidasi), saytda neytral izoh chiqadi.

**Natija:** 11222 bilet = 10758 ASSIGNED + 464 REVIEW_REQUIRED. Takroriy joy: 0. Qavat jamlari Excel bilan aynan mos.

## Istisno qatorlar (22 ta, 464 joy)

| Zona | Sektor | Qator | Joylar | REVIEW | Biletlar | Excel izohi | Qabul qilingan qoida |
|---|---|---|---|---|---|---|---|
| 2-этаж | А202 | 16 | 22 | 22 | 00593–00614 | с 16го нет номеров | Izoh: 'с 16го нет номеров'. Joylar 1–22 ketma-ket, fizik raqamlash tekshirilishi kerak. |
| 2-этаж | А202 | 17 | 18 | 18 | 00615–00632 | — | 16-qatordagi izoh 'с 16го нет номеров' ('16-dan boshlab raqam yo'q') ehtiyotkorlik uchun 17–18 qatorlarga ham tatbiq etildi. Joylar 1–18 ketma-ket. |
| 2-этаж | А202 | 18 | 21 | 21 | 00633–00653 | — | 16-qatordagi izoh 'с 16го нет номеров' ('16-dan boshlab raqam yo'q') ehtiyotkorlik uchun 17–18 qatorlarga ham tatbiq etildi. Joylar 1–21 ketma-ket. |
| 2-этаж | А203 | 15 | 24 | 24 | 01108–01131 | нет номеров | Maxsus yozuv 'Хумо А 24': 24 joy, o'rindiqlarda raqam yo'q (нет номеров). Qator belgisi Excel'dagi 'Ряд' ustunidan (15). Joylar 1–24 ketma-ket (mijoz tasdiqlagan qoida). |
| 2-этаж | В206 | 15 | 15 | 15 | 01908–01922 | можно добавить ещё 2 места | Izoh: 'можно добавить ещё 2 места'. Joylar 1–15 ketma-ket, fizik raqamlash tekshirilishi kerak. Izohdagi qo'shimcha joylar Excel sonida yo'q — QO'SHILMADI. |
| 2-этаж | В206 | 16 | 16 | 16 | 01923–01938 | можно добавить ещё 2 места | Izoh: 'можно добавить ещё 2 места'. Joylar 1–16 ketma-ket, fizik raqamlash tekshirilishi kerak. Izohdagi qo'shimcha joylar Excel sonida yo'q — QO'SHILMADI. |
| 2-этаж | В206 | 18 | 18 | 18 | 01956–01973 | помле 16 идёт 18-19 | Izoh: 'помле 16 идёт 18-19'. Joylar 1–18 ketma-ket, fizik raqamlash tekshirilishi kerak. |
| 2-этаж | В207 | 16 | 24 | 24 | 02441–02464 | неправильно расставлены + нет номеров | Izoh: 'неправильно расставлены + нет номеров'. Joylar 1–24 ketma-ket, fizik raqamlash tekshirilishi kerak. |
| 2-этаж | В207 | 17 | 24 | 24 | 02465–02488 | неправильно расставлены + нет номеров | Izoh: 'неправильно расставлены + нет номеров'. Joylar 1–24 ketma-ket, fizik raqamlash tekshirilishi kerak. |
| 2-этаж | В207 | 18 | 28 | 28 | 02489–02516 | неправильно расставлены + нет номеров | Izoh: 'неправильно расставлены + нет номеров'. Joylar 1–28 ketma-ket, fizik raqamlash tekshirilishi kerak. |
| 2-этаж | В208 | 16 | 15 | 15 | 02670–02684 | можно добавить первые 4 места | Izoh: 'можно добавить первые 4 места'. Joylar 1–15 ketma-ket, fizik raqamlash tekshirilishi kerak. Izohdagi qo'shimcha joylar Excel sonida yo'q — QO'SHILMADI. |
| 2-этаж | С210 | 16 | 22 | 4 | 03322–03343 | последние 4 места без цифр | Izoh: 'последние 4 места без цифр'. 1–18 joylar raqamli (ASSIGNED); oxirgi 4 joy (19–22) raqamsiz — REVIEW_REQUIRED. |
| 2-этаж | С211 | 14 | 24 | 24 | 03812–03835 | наклейки на подлокотниках, без номеров на сиденьях | Maxsus yozuv 'ХУМО С 24': 24 joy, o'rindiqlarda raqam yo'q (наклейки на подлокотниках, без номеров на сиденьях). Qator belgisi Excel'dagi 'Ряд' ustunidan (14). Joylar 1–24 ketma-ket (mijoz tasdiqlagan qoida). |
| Блитчеры | С212 | 4 | 25 | 25 | 03911–03935 | номера расставлены не правильно | Izoh: 'номера расставлены не правильно'. Joylar 1–25 ketma-ket, fizik raqamlash tekshirilishi kerak. Izoh birlashtirilgan katakda (P31:P34) — shu oraliqdagi barcha qatorlarga tegishli deb olindi. |
| Блитчеры | С212 | 5 | 25 | 25 | 03936–03960 | номера расставлены не правильно | Izoh: 'номера расставлены не правильно'. Joylar 1–25 ketma-ket, fizik raqamlash tekshirilishi kerak. Izoh birlashtirilgan katakda (P31:P34) — shu oraliqdagi barcha qatorlarga tegishli deb olindi. |
| Блитчеры | С212 | 6 | 25 | 25 | 03961–03985 | номера расставлены не правильно | Izoh: 'номера расставлены не правильно'. Joylar 1–25 ketma-ket, fizik raqamlash tekshirilishi kerak. Izoh birlashtirilgan katakda (P31:P34) — shu oraliqdagi barcha qatorlarga tegishli deb olindi. |
| Блитчеры | С212 | 7 | 25 | 25 | 03986–04010 | номера расставлены не правильно | Izoh: 'номера расставлены не правильно'. Joylar 1–25 ketma-ket, fizik raqamlash tekshirilishi kerak. Izoh birlashtirilgan katakda (P31:P34) — shu oraliqdagi barcha qatorlarga tegishli deb olindi. |
| 2-этаж | С212 | 16 | 22 | 22 | 04230–04251 | цифры не правильно расставлены | Izoh: 'цифры не правильно расставлены'. Joylar 1–22 ketma-ket, fizik raqamlash tekshirilishi kerak. |
| 4-этаж | А405 | 13 | 28 | 28 | 07061–07088 | нет номеров | Izoh: 'нет номеров'. Joylar 1–28 ketma-ket, fizik raqamlash tekshirilishi kerak. |
| 4-этаж | В406 | 13 | 15 | 15 | 07466–07480 | нет номеров | Izoh: 'нет номеров'. Joylar 1–15 ketma-ket, fizik raqamlash tekshirilishi kerak. |
| 4-этаж | В408 | 13 | 12 | 12 | 08331–08342 | нет номеров | Izoh: 'нет номеров'. Joylar 1–12 ketma-ket, fizik raqamlash tekshirilishi kerak. |
| 4-этаж | С409 | 13 | 34 | 34 | 08757–08790 | нет номеров | Izoh: 'нет номеров'. Joylar 1–34 ketma-ket, fizik raqamlash tekshirilishi kerak. |

### Prep-branch auditidan farqi
Auditda 17 qator belgilangan. Bu yerda yana 5 ta qator bor:
- **Блитчеры C212, 5–7 qatorlar:** izoh Excel'da birlashtirilgan katakda (`P31:P34`), ya'ni 4–7 qatorlarga tegishli.
- **2-этаж A202, 17–18 qatorlar:** 16-qatordagi "с 16го нет номеров" izohi "16-dan boshlab" deb talqin qilindi.
Ikkalasi faqat holat belgisini o'zgartiradi; joy soni va raqamlari bir xil.

## Joysiz qatorlar (40 ta, Excel'da 0 yoki "НЕТ")
Blitcher A201, A205, C209, C213 (1–8 qatorlar); 2-этаж A203 16–18, C211 15–18, D215 18. Ularga bilet berilmadi.

## Joyida tekshirish kerak
1. Istisno qatorlarida haqiqiy joy raqamlari (yo'q, noto'g'ri yoki o'tkazib yuborilgan raqamlar).
2. Qatorda raqamlash yo'nalishi (chapdan yoki o'ngdan) — Excel'da ko'rsatilmagan.
3. Maxsus "Хумо А 24" (A203/15) va "ХУМО С 24" (C211/14) zonalari — o'rindiqlarda raqam yo'q.