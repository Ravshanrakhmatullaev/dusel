// DUSEL GAL vaucher sahifasi + boshqa QR tizimlari bilan izolyatsiya testlari (Playwright)
// node test_gal_web.mjs [base_url] [screenshots_dir]
import { chromium } from 'playwright';
import fs from 'fs';
const base = process.argv[2] || 'http://127.0.0.1:8788';
const out = process.argv[3] || '/home/claude/work/gal/shots'; fs.mkdirSync(out, { recursive: true });
const b = await chromium.launch().catch(() => chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }));
const R = []; const ok = (n, c, d = '') => { R.push({ test: n, ok: !!c, detail: String(d) }); console.log((c ? 'PASS ' : 'FAIL ') + n + (d ? ' — ' + d : '')); };
const errors = [];
const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
const p = await ctx.newPage();
p.on('pageerror', e => errors.push(e.message));
const st = () => p.evaluate(() => ({
  state: document.documentElement.getAttribute('data-state'), num: (document.getElementById('num') || {}).textContent,
  txt: document.body.innerText, path: location.pathname, search: location.search,
  errVis: !!document.querySelector('.err') && getComputedStyle(document.querySelector('.err')).display !== 'none',
  numVis: !!document.getElementById('num') && document.getElementById('num').getBoundingClientRect().height > 0,
}));
const FORBID = /SEKTOR|QATOR|JOY №|BILET RAQAMI|HUMO ARENA|GOLD|SILVER|KUPON|LOTOTRON|TEST NAMUNA|haqiqiy vaucher|tasdiqlangan|ishlatilmagan/i;

// 1. To'g'ri GAL kodlari
for (const c of ['000001', '000002', '000500', '000999', '001000']) {
  await p.goto(`${base}/gal?code=${c}`); await p.waitForTimeout(250); const s = await st();
  ok(`/gal?code=${c} → GAL vaucher № ${c}`, s.state === 'ok' && s.num === c && s.numVis && !s.errVis
    && /ISHONCHLI HAMKORLAR AKSIYASI/.test(s.txt) && /1\s250\s000/.test(s.txt) && /SO'MLIK VAUCHER/.test(s.txt) && /VAUCHER RAQAMI/i.test(s.txt), `${s.num}`);
  ok(`  ${c}: bilet/kupon/test bloklari va soxta "tasdiqlandi" da'volari yo'q`, !FORBID.test(s.txt));
}
// 1b. Asl dizayn elementlari va shartlar
await p.goto(`${base}/gal?code=000001`); await p.waitForTimeout(1500);
{
  const r = await p.evaluate(() => ({
    imgs: [...document.querySelectorAll('img')].map(i => [i.getAttribute('src'), i.complete && i.naturalWidth > 0]),
    txt: document.body.innerText }));
  const need = ['assets/logo.svg', 'assets/gal/title.webp', 'assets/gal/hero.webp', 'assets/gal/amount.webp'];
  ok('Asl dizayndan olingan rasmlar (logo, sarlavha, bino+sovg\'alar, summa) yuklandi', need.every(n => r.imgs.some(([s, ok]) => s === n && ok)), r.imgs.map(x => x[0] + ':' + x[1]).join(', '));
  ok('Dizayndagi shartlar so\'zma-so\'z: "15 KUN ICHIDA AMAL QILADI" va "01.06.2026–31.12.2026 … ELEKTRIKLAR UCHUN AMAL QILADI"',
     /BERILGAN SANADAN USHBU VAUCHER 15 KUN ICHIDA AMAL QILADI!/.test(r.txt) && /01\.06\.2026–31\.12\.2026/.test(r.txt) && /ISHTIROK ETGAN ELEKTRIKLAR UCHUN AMAL QILADI!/i.test(r.txt) && /SERIYA NOMER/i.test(r.txt) && /Nº\s*000001/.test(r.txt));
}
// 2. Barcha 1000 raqam sahifada aynan shu raqamni ko'rsatadi
{
  const bad = [];
  for (let i = 1; i <= 1000; i++) {
    const c = String(i).padStart(6, '0');
    await p.goto(`${base}/gal?code=${c}`, { waitUntil: 'domcontentloaded' });
    const n = await p.evaluate(() => document.documentElement.getAttribute('data-state') + ':' + document.getElementById('num').textContent);
    if (n !== 'ok:' + c) bad.push(c);
  }
  ok('Barcha 1000 kod (000001–001000) sahifada o\'z raqamini ko\'rsatadi', bad.length === 0, bad.length ? 'xato: ' + bad.slice(0, 5) : '1000/1000');
}
// 3. Noto'g'ri kodlar — rad etiladi, bilet sahifasiga o'tib ketmaydi
for (const q of ['code=000000', 'code=001001', 'code=ABCDEF', '', 'code=', 'code=00001', 'code=0000001', 'code=1000', 'code=1', 'code=%20000001', 'code=000001x', 'code=-00001', 'code=0001e3', 'type=gold&code=0001']) {
  await p.goto(`${base}/gal?${q}`); await p.waitForTimeout(250); const s = await st();
  ok(`Noto'g'ri "/gal?${q}" → "Vaucher topilmadi", /gal da qoladi`, s.state === 'invalid' && s.errVis && /Vaucher topilmadi/.test(s.txt) && s.path === '/gal' && !/BILET RAQAMI/i.test(s.txt));
}
// 4. Yangilash (refresh) va to'g'ridan-to'g'ri kirish (yangi, bo'sh brauzer sessiyasi)
await p.goto(`${base}/gal?code=000777`); await p.reload(); await p.waitForTimeout(250);
{ const s = await st(); ok('Sahifani yangilash (refresh) — raqam saqlanadi', s.state === 'ok' && s.num === '000777'); }
{
  const c2 = await b.newContext({ viewport: { width: 375, height: 667 }, isMobile: true }); const p2 = await c2.newPage();
  await p2.goto(`${base}/gal?code=000123`); await p2.waitForTimeout(250);
  const s = await p2.evaluate(() => ({ st: document.documentElement.getAttribute('data-state'), n: document.getElementById('num').textContent, ck: document.cookie, ls: localStorage.length }));
  ok('Nusxa olingan havola yangi brauzer sessiyasida ochiladi (cookie/localStorage talab qilinmaydi)', s.st === 'ok' && s.n === '000123' && s.ck === '' && s.ls === 0);
  await c2.close();
}
// 5. Boshqa tizimlar o'zgarmagan va izolyatsiya
for (const c of ['00001', '11222']) {
  await p.goto(`${base}/?code=${c}`);
  await p.waitForFunction(() => document.getElementById('ticket') && document.getElementById('ticket').classList.contains('done'), null, { timeout: 20000 });
  const r = await p.evaluate(() => ({ w: document.querySelectorAll('.wheel').length, txt: document.body.innerText, path: location.pathname }));
  ok(`Bilet /?code=${c} → bilet sahifasi (o'zgarmagan)`, r.w === 5 && /BILET RAQAMI/i.test(r.txt) && !/VAUCHER/i.test(r.txt) && r.path === '/');
}
await p.goto(`${base}/?code=000001`); await p.waitForTimeout(400);
ok('GAL raqami bilet sahifasida bilet sifatida qabul qilinmaydi (/?code=000001 → xato)', await p.evaluate(() => document.getElementById('ticket').classList.contains('invalid')));
for (const [t, c, name] of [['gold', '0001', 'GOLD'], ['silver', '0001', 'SILVER'], ['gold', '2000', 'GOLD'], ['silver', '4000', 'SILVER']]) {
  await p.goto(`${base}/coupon?type=${t}&code=${c}`); await p.waitForTimeout(300);
  const r = await p.evaluate(() => ({ ty: document.documentElement.getAttribute('data-type'), n: document.getElementById('num').textContent, ttl: document.getElementById('ttl').textContent, txt: document.body.innerText }));
  ok(`Kupon /coupon?type=${t}&code=${c} → ${name} kupon sahifasi (o'zgarmagan)`, r.ty === t && r.n === c && r.ttl === name && !/VAUCHER/i.test(r.txt));
}
await p.goto(`${base}/coupon?type=gold&code=000001`); await p.waitForTimeout(300);
ok('GAL raqami kupon sahifasida qabul qilinmaydi (/coupon?type=gold&code=000001 → xato)', await p.evaluate(() => document.documentElement.getAttribute('data-type') === 'none'));
// 6. 404 yo'naltirish: /gal… va /coupon… hech qachon bilet sahifasiga tushmaydi
for (const [u, expPath, expNum] of [['/GAL?code=000001', '/gal', '000001'], ['/gal/?code=000002', '/gal', '000002'], ['/gal/000003', '/gal', null], ['/Gal?code=001000', '/gal', '001000']]) {
  await p.goto(base + u); await p.waitForURL(x => new URL(x).pathname === expPath, { timeout: 5000 }).catch(() => {}); await p.waitForTimeout(300);
  const s = await st();
  ok(`"${u}" → ${expPath} sahifasida qoladi${expNum ? ' (№ ' + expNum + ')' : ' (xato xabari)'}, bilet sahifasiga o'tmaydi`, s.path === expPath && (expNum ? s.state === 'ok' && s.num === expNum : s.state === 'invalid'), s.path + s.search);
}
await p.goto(base + '/COUPON?type=gold&code=0001'); await p.waitForURL(x => new URL(x).pathname === '/coupon', { timeout: 5000 }).catch(() => {}); await p.waitForTimeout(300);
ok('"/COUPON?type=gold&code=0001" → /coupon sahifasi', await p.evaluate(() => location.pathname === '/coupon' && document.documentElement.getAttribute('data-type') === 'gold'));
await p.goto(base + '/boshqa-sahifa'); await p.waitForURL(x => new URL(x).search === '?code=invalid', { timeout: 5000 }).catch(() => {});
ok('Boshqa noma\'lum yo\'l avvalgidek bilet sahifasiga "?code=invalid" bilan boradi (o\'zgarmagan)', await p.evaluate(() => location.pathname === '/' && location.search === '?code=invalid'));
// 7. Animatsiya: jonli, raqamni to'smaydi, scrollga xalaqit bermaydi
await p.goto(`${base}/gal?code=000001`); await p.waitForTimeout(1800);
const f1 = await p.evaluate(() => document.getElementById('fx').toDataURL()); await p.waitForTimeout(400);
const f2 = await p.evaluate(() => document.getElementById('fx').toDataURL());
ok('Fon effekti (canvas) jonli — kadrlar o\'zgaradi', f1 !== f2);
const lay = await p.evaluate(() => {
  const n = document.getElementById('num').getBoundingClientRect(); const el = document.elementFromPoint(n.left + n.width / 2, n.top + n.height / 2);
  const cv = getComputedStyle(document.getElementById('fx')); const ov = [...document.querySelectorAll('.shine')].map(e => getComputedStyle(e, '::after').pointerEvents);
  return { top: el && (el.id === 'num' || el.closest('.num') !== null), pe: cv.pointerEvents, ovpe: ov.every(v => v === 'none'), z: cv.zIndex };
});
ok('Raqam ustida hech narsa yo\'q; effektlar pointer-events:none (scroll/teginishga xalaqit bermaydi)', lay.top && lay.pe === 'none' && lay.ovpe);
const fps = await p.evaluate(() => new Promise(r => { let n = 0; const t0 = performance.now(); (function k() { n++; if (performance.now() - t0 < 2000) requestAnimationFrame(k); else r(n / 2); })(); }));
ok('Animatsiya kadr tezligi (headless, taxminiy)', fps >= 20, `${Math.round(fps)} fps`);
await p.screenshot({ path: out + '/gal_000001_390.png' });
// 8. Reduced motion, JS animatsiyasi buzilganda, JS o'chirilganda
{
  const c = await b.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' }); const pg = await c.newPage();
  await pg.goto(`${base}/gal?code=000010`); await pg.waitForTimeout(300);
  const r = await pg.evaluate(() => ({ cv: getComputedStyle(document.getElementById('fx')).display, n: document.getElementById('num').textContent, op: getComputedStyle(document.querySelector('.box')).opacity }));
  ok('prefers-reduced-motion: effektlar o\'chadi, raqam darhol ko\'rinadi', r.cv === 'none' && r.n === '000010' && r.op === '1'); await c.close();
}
{
  const c = await b.newContext({ viewport: { width: 390, height: 844 } }); const pg = await c.newPage();
  await pg.addInitScript(() => { HTMLCanvasElement.prototype.getContext = function () { throw new Error('canvas yo\'q'); }; });
  await pg.goto(`${base}/gal?code=000011`); await pg.waitForTimeout(1500);
  const r = await pg.evaluate(() => ({ s: document.documentElement.getAttribute('data-state'), n: document.getElementById('num').textContent }));
  ok('Canvas ishlamasa ham (eski qurilma) vaucher ma\'lumoti to\'liq ko\'rinadi', r.s === 'ok' && r.n === '000011'); await c.close();
}
{
  const c = await b.newContext({ viewport: { width: 390, height: 844 }, javaScriptEnabled: false }); const pg = await c.newPage();
  await pg.goto(`${base}/gal?code=000012`); await pg.waitForTimeout(1200);
  const t = await pg.evaluate(() => document.body.innerText);
  ok('JavaScript o\'chiq: brend, aksiya nomi, summa va izoh ko\'rinadi', /ISHONCHLI HAMKORLAR AKSIYASI/.test(t) && /1\s250\s000/.test(t) && /JavaScript/.test(t)); await c.close();
}
// 9. Ekran o'lchamlari
for (const [n, vp] of [['320x568', { width: 320, height: 568 }], ['360x740', { width: 360, height: 740 }], ['375x667', { width: 375, height: 667 }], ['390x844', { width: 390, height: 844 }], ['412x915', { width: 412, height: 915 }], ['768x1024', { width: 768, height: 1024 }], ['1366x900', { width: 1366, height: 900 }]]) {
  const c = await b.newContext({ viewport: vp, isMobile: vp.width < 700, hasTouch: vp.width < 700 }); const pg = await c.newPage();
  await pg.goto(`${base}/gal?code=001000`); await pg.waitForTimeout(1400);
  const m = await pg.evaluate(() => {
    const r = document.getElementById('num').getBoundingClientRect(), a = document.getElementById('amt'), pl = document.querySelector('.box');
    return { sw: document.documentElement.scrollWidth, bottom: r.bottom, right: r.right, ov: a.scrollWidth > a.clientWidth + 1 || document.querySelector('.num').getBoundingClientRect().right > pl.getBoundingClientRect().right - 4 };
  });
  ok(`${n}: gorizontal siljish yo'q, matn sig'adi, raqam birinchi ekranda`, m.sw <= vp.width && m.right <= vp.width && !m.ov && m.bottom <= vp.height, `raqam pastki ${Math.round(m.bottom)}px`);
  if (vp.width === 320) await pg.screenshot({ path: out + '/gal_320.png' });
  await c.close();
}
await p.goto(`${base}/gal?code=001001`); await p.waitForTimeout(400); await p.screenshot({ path: out + '/gal_xato_001001.png' });
ok('Sahifada JavaScript xatolari yo\'q', errors.length === 0, errors.slice(0, 3).join(' | '));
await b.close();
fs.writeFileSync(out + '/web_results.json', JSON.stringify(R, null, 1));
console.log(`\n${R.filter(r => r.ok).length}/${R.length} PASS`);
process.exit(R.every(r => r.ok) ? 0 : 1);
