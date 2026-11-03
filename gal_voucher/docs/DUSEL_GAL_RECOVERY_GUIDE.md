# DUSEL — QR sahifalari: zaxira, deploy va tiklash qo'llanmasi

Oxirgi yangilanish: 2026-11-03 · Tegishli: bilet, GOLD/SILVER kupon, GAL vaucher

## 1. Domen va yo'llar reyestri (bosilgan QR'lar shunga bog'liq)

Production domen: **https://dusel.pages.dev** (Cloudflare Pages loyihasi `dusel`, production branch `main`).

| Tizim | QR ichidagi URL | Diapazon | Fayl |
|---|---|---|---|
| Bilet | `https://dusel.pages.dev/?code=NNNNN` | 00001–11222 | `index.html` |
| GOLD kupon | `https://dusel.pages.dev/coupon?type=gold&code=NNNN` | 0001–2000 | `coupon.html` |
| SILVER kupon | `https://dusel.pages.dev/coupon?type=silver&code=NNNN` | 0001–4000 | `coupon.html` |
| GAL vaucher | `https://dusel.pages.dev/gal?code=NNNNNN` | 000001–001000 | `gal.html` |

Qoidalar:
- Domen, yo'llar (`/`, `/coupon`, `/gal`) va `code`/`type` parametr nomlari **hech qachon o'zgartirilmaydi**. `index.html`, `coupon.html`, `gal.html`, `404.html` o'chirilmaydi va qayta nomlanmaydi.
- Har bir tizim raqamni o'z uzunligi bo'yicha qabul qiladi (bilet 5, kupon 4, GAL 6 xona), shuning uchun bir xil son boshqa tizimga tushmaydi.
- `404.html`: `/gal…` va `/coupon…` ko'rinishidagi xato yo'llar o'z sahifasiga qaytariladi; qolgani `/?code=invalid` (bilet sahifasi).
- Sahifalar statik: server, ma'lumotlar bazasi, login, token yoki pullik QR xizmati yo'q. QR'da qisqartirgich (bit.ly va h.k.) yo'q — to'g'ridan-to'g'ri URL.
- Aksiya muddati (vaucher berilgandan 15 kun) — bu reklama sharti; sahifa muddat tugagach ham ishlab turadi (avtomatik o'chmaydi).

## 2. Nima qayerda saqlanadi

| Nima | Joy |
|---|---|
| Production sayt manbasi | GitHub `Ravshanrakhmatullaev/dusel`, branch `main` |
| GAL ishlab chiqish | branch `feature/gal-voucher` (PR orqali `main`ga) |
| Bosma vositalari, master ma'lumotlar, testlar | branch `prep/11222-ticket-capacity` (`gal_voucher/`, `coupon/`, `tools/`, `data/`) |
| GAL master | `DUSEL_GAL_MASTER.xlsx` / `.csv` |
| GAL QR manbalari | `DUSEL_GAL_QR_1000.zip` (1000 SVG + 1000 PNG + master CSV) |
| Bosma fayllar | `DUSEL_GAL_PRINT.pdf`, `DUSEL_GAL_PROOF.pdf` |

QR'lar deterministik: `python gal_voucher/tools/gal_build.py --out out` har safar aynan bir xil 1000 ta QR va master hosil qiladi (URL'lar o'zgarmaydi).

**Tavsiya etiladigan zaxira (kamida 2 nusxa, biri internetdan tashqarida):**
1. Repo to'liq nusxasi: `git clone --mirror https://github.com/Ravshanrakhmatullaev/dusel.git` → arxivlab flesh/diskda saqlash (har yirik o'zgarishdan keyin yangilash).
2. Master XLSX/CSV, QR ZIP va bosma PDF'larni Google Drive (yoki boshqa bulut) + flesh diskda saqlash.
3. Vaucher berilganda `STATUS`, `ISSUE_DATE`, `RECIPIENT_NAME` ustunlarini master XLSX'da to'ldirib boring va nusxasini saqlang (bu ma'lumot saytga chiqmaydi).

## 3. Deploy (faqat tasdiqdan keyin)

1. GitHub'da PR (`feature/gal-voucher` → `main`) ochiladi va preview tekshiriladi: `https://feature-gal-voucher.dusel.pages.dev/gal?code=000001`.
2. Tasdiqlangach PR **Merge** qilinadi. Cloudflare Pages 1–2 daqiqada `main`ni avtomatik deploy qiladi (build buyrug'i yo'q, fayllar ildizdan).
3. Deploydan keyin telefonda tekshirish ro'yxati (yangi/incognito oynada):
   - `https://dusel.pages.dev/?code=00001` va `?code=11222` → bilet sahifasi
   - `https://dusel.pages.dev/coupon?type=gold&code=0001` → GOLD; `…type=silver&code=0001` → SILVER
   - `https://dusel.pages.dev/gal?code=000001` va `…001000` → GAL vaucher
   - `https://dusel.pages.dev/gal?code=001001` → "Vaucher topilmadi"
   - Sahifani yangilash (refresh) — o'sha raqam qoladi.
4. Bosilgan QR'dan bittasini haqiqiy telefon bilan skanerlash.

## 4. Orqaga qaytarish (rollback) — deploy xato bo'lsa

**Eng tez yo'l (1 daqiqa, kod o'zgarmaydi):** Cloudflare dashboard → Workers & Pages → `dusel` → Deployments → oxirgi ishlagan production deploy → "⋯" → **Rollback to this deployment**.

**Git orqali (doimiy tuzatish):**
```bash
git clone https://github.com/Ravshanrakhmatullaev/dusel.git && cd dusel
git log --oneline -5 main                 # xato commitni toping
git revert <xato_commit>                  # yoki merge commit uchun: git revert -m 1 <merge_commit>
git push origin main                      # Cloudflare avtomatik qayta deploy qiladi
```
Ma'lum ishlagan holatlar: `31185b6` (bilet + kupon, GAL'siz). GAL qo'shilgan merge commit PR'dan keyin shu ro'yxatga yoziladi.

**Build butunlay buzilsa:** Cloudflare → `dusel` → Settings → Builds: production branch = `main`, build command = bo'sh, output directory = `/` (ildiz). Keyin Deployments → "Retry deployment". Kerak bo'lsa yangi bo'sh commit: `git commit --allow-empty -m redeploy && git push`.

## 5. Monitoring

- `.github/workflows/qr-uptime.yml` — kuniga 2 marta (07:17 va 19:17 Toshkent) bilet, GOLD, SILVER va GAL sahifalarini tekshiradi; xato bo'lsa GitHub repo egasiga email yuboradi. `main`ga qo'shilgandan keyin ishlaydi. Qo'lda: GitHub → Actions → "QR sahifalari tekshiruvi" → Run workflow.
- Ixtiyoriy: tashqi bepul monitor (masalan, UptimeRobot) — `https://dusel.pages.dev/gal?code=000001` uchun 5 daqiqalik tekshiruv. Bu sizning qaroringiz; men hisob ochmadim.
- GitHub 60 kun faoliyatsiz repo'larda rejalashtirilgan workflow'larni to'xtatib qo'yishi mumkin — email kelsa, Actions sahifasida qayta yoqing.

## 6. Xavflar (halol baho)

Hech bir hosting abadiy ishlashni kafolatlamaydi. Cloudflare Pages bepul tarifi bugun bunday loyiha uchun yetarli (statik sahifa, so'rovlar soni cheklanmagan), lekin shartlar kelajakda o'zgarishi mumkin.

| Xavf | Oqibat | Oldini olish |
|---|---|---|
| Cloudflare hisobiga kirish yo'qolishi | Deploy/rollback qilib bo'lmaydi (sayt ishlashda davom etadi) | 2FA + tiklash kodlarini saqlash; ishonchli ikkinchi admin qo'shish |
| Pages loyihasi `dusel` o'chirilishi | `dusel.pages.dev` nomi bo'shaydi — **barcha bosilgan QR'lar ishlamaydi**, nomni boshqa birov egallashi mumkin | Loyihani hech qachon o'chirmang yoki qayta nomlamang |
| GitHub hisobi/repo yo'qolishi | Yangi deploy qilib bo'lmaydi | `git clone --mirror` zaxirasi; Cloudflare oxirgi deployni baribir xizmat qiladi |
| Fayl qayta nomlanishi / yo'l o'zgarishi | Tegishli QR'lar xato beradi | 1-bo'limdagi reyestr; PR'da testlar; kunlik monitoring |
| Cloudflare bepul tarif shartlari o'zgarishi | Tarifni almashtirish kerak bo'lishi mumkin | Monitoring emaillari va Cloudflare xabarlarini kuzatish |
| QR qog'ozda shikastlanishi | Skanerlanmasligi mumkin | QR xato tuzatish Q (~25%), yetarli o'lcham va oq hoshiya; sahifada raqam qo'lda ham tekshiriladi |

**Muhim cheklov:** QR ichiga `dusel.pages.dev` yozilgan. Agar bu domen ishlamay qolsa, boshqa domendagi zaxira sayt **bosilgan QR'larni avtomatik qutqara olmaydi** — telefon baribir `dusel.pages.dev`ga murojaat qiladi. `*.pages.dev` manzilini boshqa hostingga yo'naltirib bo'lmaydi.

Kelajakdagi yangi tirajlar uchun variant (faqat sizning tasdig'ingiz bilan): o'z domeningiz (masalan, `dusel.uz`) — u holda hosting almashsa ham DNS orqali yangi joyga yo'naltirish mumkin. Mavjud bilet/kupon/GAL QR'lari `dusel.pages.dev`da qoladi; domen o'zgartirilmagan.
