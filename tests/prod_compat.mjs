// Production'ni FAQAT O'QISH rejimida tekshirish (hech narsa yozmaydi): tarixiy bilet QR formatlari, kuponlar, /checkin holati.
// GitHub Actions'da ishlaydi (bu muhitdan *.pages.dev ga to'g'ridan-to'g'ri kirib bo'lmaydi).
import { chromium } from 'playwright';
import fs from 'fs';
const out = process.argv[2] || 'compat'; fs.mkdirSync(out, { recursive: true });
const PREVIEW = process.env.PREVIEW_URL || 'https://feature-checkin.dusel.pages.dev';
const R = []; const ok = (n, c, d = '') => { R.push({ test: n, ok: !!c, detail: String(d).slice(0, 300) }); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? ' — ' + d : '')); };
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
const p = await ctx.newPage();
async function ticket(url) {
  const resp = await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await p.waitForFunction(() => { const t = document.getElementById('ticket'); return t && (t.classList.contains('done') || t.classList.contains('invalid')); }, null, { timeout: 20000 }).catch(() => {});
  const num = ((await p.textContent('#srnum').catch(() => '')) || '').replace(/\D/g, '');
  const txt = await p.locator('body').innerText().catch(() => '');
  return { status: resp && resp.status(), num, invalid: await p.evaluate(() => document.getElementById('ticket')?.classList.contains('invalid')), txt, final: p.url() };
}
const FORMATS = [
  ['dusel.pages.dev/?code= (V4–V6 bosmalar, duseeeeeel_1.pdf)', 'https://dusel.pages.dev/?code='],
  ['dusel.pages.dev/ticket?code= (V7)', 'https://dusel.pages.dev/ticket?code='],
  ['github.io/dusel/?code= (22-oktabr birinchi to\'plam)', 'https://ravshanrakhmatullaev.github.io/dusel/?code='],
];
for (const [label, prefix] of FORMATS) {
  for (const n of ['00001', '00330', '06114', '10000', '11222']) {
    const r = await ticket(prefix + n);
    ok(`${label} ${n} → bilet sahifasi, raqam ${n}`, r.status === 200 && r.num === n && !r.invalid, `HTTP ${r.status}, ko'rsatilgan ${r.num}, ${r.final}`);
    if (n === '06114') await p.screenshot({ path: `${out}/${label.split(' ')[0].replace(/[^a-z0-9]/gi, '_')}_06114.png` });
    if (prefix.includes('github.io') && n === '06114') {
      ok('github.io eski sahifasida "Joy ma\'lumoti hali tasdiqlanmagan" yozuvi hali bormi (ma\'lumot uchun)', true, /tasdiqlanmagan/i.test(r.txt) ? 'HA — eski matn ko\'rinmoqda' : 'yo\'q');
    }
  }
  const bad = await ticket(prefix + '11223');
  ok(`${label} 11223 → "topilmadi" (boshqa mahsulot ochilmaydi)`, bad.invalid === true, bad.final);
}
for (const [u, exp] of [['https://dusel.pages.dev/gold?code=0001', 'GOLD'], ['https://dusel.pages.dev/silver?code=0001', 'SILVER'], ['https://dusel.pages.dev/gal?code=0001', 'ISHONCHLI'],
                        ['https://dusel.pages.dev/coupon?type=gold&code=0001', 'GOLD']]) {
  await p.goto(u, { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(800);
  ok(`Kupon/vaucher ${u} o'zgarmagan`, (await p.locator('body').innerText()).includes(exp));
}
const pc = await p.goto('https://dusel.pages.dev/checkin', { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(600);
ok('Production /checkin hali yo\'q (tasdiqsiz chiqarilmagan)', pc.status() === 404 || /Sahifa topilmadi/.test(await p.locator('body').innerText()), `HTTP ${pc.status()}`);
// staging preview: sahifa yuklanadi, CSP xatosiz
const cons = [];
const pp = await ctx.newPage(); pp.on('console', (m) => { if (m.type() === 'error') cons.push(m.text()); }); pp.on('pageerror', (e) => cons.push(e.message));
const pr = await pp.goto(PREVIEW + '/checkin', { waitUntil: 'networkidle' }).catch((e) => null);
await pp.waitForTimeout(1500);
const h = pr ? pr.headers() : {};
ok('Staging preview /checkin yuklanadi', pr && pr.status() === 200, pr && pr.status());
ok('Staging /checkin xavfsizlik sarlavhalari (CSP, frame-ancestors, no-store, kamera faqat o\'zi)', /frame-ancestors 'none'/.test(h['content-security-policy'] || '') && /no-store/.test(h['cache-control'] || '') && /camera=\(self\)/.test(h['permissions-policy'] || ''), JSON.stringify({ csp: (h['content-security-policy'] || '').slice(0, 80), cc: h['cache-control'] }));
ok('Staging /checkin konsolda CSP/JS xatolari yo\'q', cons.length === 0, cons.slice(0, 3).join(' | '));
await pp.screenshot({ path: `${out}/staging_checkin.png` });
await b.close();
fs.writeFileSync(`${out}/compat_results.json`, JSON.stringify(R, null, 1));
console.log(`\n${R.filter((r) => r.ok).length}/${R.length} PASS`);
