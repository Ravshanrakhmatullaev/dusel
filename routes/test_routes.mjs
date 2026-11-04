// DUSEL — to'liq yo'l izolyatsiyasi testi: /ticket, /gal, /gold, /silver (+ eski /?code, /coupon), 404, QR → sahifa
// node test_routes.mjs <base_url> <shots_dir> <qr_manifest.json>
import { chromium } from 'playwright';
import fs from 'fs';
const base = process.argv[2] || 'http://127.0.0.1:8790';
const out = process.argv[3] || '/home/claude/work/routes/shots'; fs.mkdirSync(out, { recursive: true });
const manifest = process.argv[4] ? JSON.parse(fs.readFileSync(process.argv[4], 'utf8')) : null;
const b = await chromium.launch().catch(() => chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }));
const R = []; const ok = (sec, n, c, d = '') => { R.push({ section: sec, test: n, ok: !!c, detail: String(d) }); console.log((c ? 'PASS ' : 'FAIL ') + `[${sec}] ` + n + (d ? ' — ' + d : '')); };
const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
const p = await ctx.newPage();
const errors = []; p.on('pageerror', e => errors.push(p.url() + ' ' + e.message));

// Sahifa qaysi mahsulotni ko'rsatayotganini DOM bo'yicha aniqlash (bir vaqtda faqat bittasi bo'lishi kerak)
async function detect() {
  return p.evaluate(() => {
    const d = document, txt = d.body ? d.body.innerText : '';
    const prod = [];
    const t = d.getElementById('ticket');
    if (t) prod.push({ product: 'ticket', valid: !t.classList.contains('invalid'), number: ((d.getElementById('srnum') || {}).textContent || '').replace(/\D/g, '') });
    if (d.documentElement.hasAttribute('data-state') && d.querySelector('.box')) {
      const st = d.documentElement.getAttribute('data-state');
      prod.push({ product: 'gal', valid: st === 'ok', number: st === 'ok' ? d.getElementById('num').textContent : '' });
    }
    if (d.getElementById('ttl') && d.documentElement.hasAttribute('data-type')) {
      const ty = d.documentElement.getAttribute('data-type');
      prod.push({ product: ty === 'none' ? 'coupon' : ty, valid: ty !== 'none', number: ty !== 'none' ? d.getElementById('num').textContent : '' });
    }
    if (/Sahifa topilmadi/.test(d.title)) prod.push({ product: '404', valid: false, number: '' });
    // boshqa mahsulot belgilarining matnda borligi
    const marks = {
      ticket: /BILET RAQAMI|YULDUZLI KECHA|HUMO ARENA/i.test(txt),
      gal: /ISHONCHLI HAMKORLAR|SO'MLIK VAUCHER|Vaucher topilmadi/i.test(txt),
      gold: /\bGOLD\b/.test(txt), silver: /\bSILVER\b/.test(txt),
    };
    return { prod, marks, path: location.pathname, search: location.search, title: d.title };
  });
}
async function open(u, wait = 350) {
  await p.goto(base + u);
  await p.waitForTimeout(wait);
  // bilet sahifasi g'ildirak animatsiyasini tugatsin
  await p.waitForFunction(() => { const t = document.getElementById('ticket'); return !t || t.classList.contains('done') || t.classList.contains('invalid'); }, null, { timeout: 15000 }).catch(() => {});
  return detect();
}
const FOREIGN = { ticket: ['gal', 'gold', 'silver'], gal: ['ticket', 'gold', 'silver'], gold: ['ticket', 'gal', 'silver'], silver: ['ticket', 'gal', 'gold'] };
function only(s, prod) { return s.prod.length === 1 && s.prod[0].product === prod && FOREIGN[prod].every(k => !s.marks[k]); }

const rnd = (n, max, w) => { const s = new Set(); let x = 12345; while (s.size < n) { x = (x * 1103515245 + 12345) % 2147483648; s.add(String(1 + (x % max)).padStart(w, '0')); } return [...s]; };
const VALID = {
  ticket: { path: '/ticket', codes: ['00001', '00330', '10000', '11222', ...rnd(16, 11222, 5)] },
  gal: { path: '/gal', codes: ['0001', '0100', '1000', ...rnd(12, 1000, 4)] },
  gold: { path: '/gold', codes: ['0001', '2000', ...rnd(12, 2000, 4)] },
  silver: { path: '/silver', codes: ['0001', '4000', ...rnd(12, 4000, 4)] },
};
// 1. To'g'ri kodlar — faqat o'z sahifasi, to'g'ri raqam, boshqa mahsulot belgisi yo'q
for (const [prod, v] of Object.entries(VALID)) {
  const bad = [];
  for (const c of v.codes) {
    const s = await open(`${v.path}?code=${c}`);
    if (!(only(s, prod) && s.prod[0].valid && s.prod[0].number === c && s.path === v.path)) bad.push(c + ':' + JSON.stringify(s.prod) + JSON.stringify(s.marks));
  }
  ok('TO\'G\'RI', `${v.path}: ${v.codes.length} ta kod (${v.codes.slice(0, prod === 'ticket' ? 4 : 3).join(', ')} + tasodifiy) → faqat ${prod.toUpperCase()} sahifasi, raqam to'g'ri`, !bad.length, bad.slice(0, 2).join(' | '));
}
// 2. Noto'g'ri kodlar — o'sha sahifaning o'zida xato, boshqa joyga yo'naltirilmaydi
const INVALID = {
  ticket: ['11223', '00000', '000005', '000001', '0001', '1', 'abcde', '', '99999', '1e3'],
  gal: ['1001', '0000', '000001', '001000', '00001', '11222', 'ABCD', '', '1'],
  gold: ['2001', '0000', '00001', '000001', '4000', 'abcd', '', '1'],
  silver: ['4001', '0000', '00001', '000001', '11222', 'abcd', '', '1'],
};
for (const [prod, codes] of Object.entries(INVALID)) {
  const path = VALID[prod].path, bad = [];
  for (const c of codes) {
    const s = await open(`${path}?code=${encodeURIComponent(c)}`);
    // xato holatida kupon sahifasi data-type=none bo'ladi — u ham o'sha sahifa (GOLD/SILVER matni ko'rinmaydi)
    const same = s.prod.length === 1 && (s.prod[0].product === prod || (s.prod[0].product === 'coupon' && (prod === 'gold' || prod === 'silver')));
    if (!(same && !s.prod[0].valid && s.path === path && FOREIGN[prod].every(k => !s.marks[k]))) bad.push(c + ':' + JSON.stringify(s));
  }
  ok('NOTO\'G\'RI', `${path}: ${codes.map(c => c || "(bo'sh)").join(', ')} → o'sha sahifada xato, yo'naltirish yo'q`, !bad.length, bad.slice(0, 2).join(' | '));
}
// 3. Maxsus kesishuvlar
const CROSS = [
  ['/gal?code=11222', 'gal', false], ['/ticket?code=0001', 'ticket', false], ['/gal?code=000001', 'gal', false], ['/gal?code=2000', 'gal', false], ['/gold?code=4000', 'gold', false],
  ['/silver?code=2000', 'silver', true], ['/gold?code=0001&type=silver', 'gold', true], ['/silver?code=0001&type=gold', 'silver', true],
  ['/gold?code=1000', 'gold', true], ['/gal?code=0001', 'gal', true],
];
for (const [u, prod, valid] of CROSS) {
  const s = await open(u);
  const prodOk = s.prod.length === 1 && (s.prod[0].product === prod || (!valid && s.prod[0].product === 'coupon' && (prod === 'gold' || prod === 'silver')));
  ok('KESISHUV', `${u} → ${prod.toUpperCase()} sahifasi, ${valid ? 'to\'g\'ri' : 'xato'}`, prodOk && s.prod[0].valid === valid && FOREIGN[prod].every(k => !s.marks[k]), JSON.stringify(s.prod));
}
// 4. Eski (legacy) havolalar — faqat o'z mahsuloti (avval chop etilgan QR'lar uchun)
for (const [u, prod, num] of [['/?code=00001', 'ticket', '00001'], ['/?code=11222', 'ticket', '11222'], ['/coupon?type=gold&code=0001', 'gold', '0001'], ['/coupon?type=silver&code=4000', 'silver', '4000']]) {
  const s = await open(u);
  ok('ESKI HAVOLA', `${u} → faqat ${prod.toUpperCase()} № ${num}`, only(s, prod) && s.prod[0].valid && s.prod[0].number === num, JSON.stringify(s.prod));
}
for (const u of ['/?code=000001', '/?code=0001', '/coupon?type=gal&code=000001', '/coupon?code=0001']) {
  const s = await open(u);
  ok('ESKI HAVOLA', `${u} → boshqa mahsulot ochilmaydi (o'sha sahifada xato)`, s.prod.length === 1 && !s.prod[0].valid && !s.marks.gal, JSON.stringify(s.prod));
}
// 5. 404 — boshqa mahsulotga yo'naltirmaydi; faqat o'sha yo'lning yozilishini to'g'rilaydi
for (const [u, expPath, prod, num] of [['/GAL?code=0001', '/gal', 'gal', '0001'], ['/Ticket/?code=00001', '/ticket', 'ticket', '00001'], ['/GOLD?code=0001', '/gold', 'gold', '0001'], ['/silver/?code=0001', '/silver', 'silver', '0001']]) {
  await p.goto(base + u); await p.waitForURL(x => new URL(x).pathname === expPath, { timeout: 5000 }).catch(() => {});
  const s = await open(expPath + new URL(p.url()).search);
  ok('404', `${u} → ${expPath} (o'sha mahsulot, № ${num})`, only(s, prod) && s.prod[0].number === num, s.path + s.search);
}
for (const u of ['/xyz', '/tickets?code=00001', '/gal2?code=0001', '/coupon/gold?code=0001', '/assets/nope']) {
  await p.goto(base + u); await p.waitForTimeout(700);
  const s = await detect();
  ok('404', `${u} → neytral "Sahifa topilmadi", hech qayerga yo'naltirilmaydi`, s.prod.length === 1 && s.prod[0].product === '404' && !Object.values(s.marks).some(Boolean) && (base + u).endsWith(s.path + s.search), s.path + s.search);
}
// 6. QR → sahifa: arxivlardagi QR'lar dekod qilingan URL'lar shu sahifani ochadi
if (manifest) {
  for (const [prod, urls] of Object.entries(manifest)) {
    const bad = [];
    for (const u of urls) {
      const U = new URL(u);
      if (U.host !== 'dusel.pages.dev' || U.protocol !== 'https:') { bad.push('host ' + u); continue; }
      const s = await open(U.pathname + U.search);
      const code = U.searchParams.get('code');
      if (!(only(s, prod) && s.prod[0].valid && s.prod[0].number === code)) bad.push(u);
    }
    ok('QR→SAHIFA', `${prod.toUpperCase()}: dekod qilingan ${urls.length} ta QR URL → faqat ${prod.toUpperCase()} sahifasi, raqam QR bilan bir xil`, !bad.length, bad.slice(0, 3).join(' | '));
  }
}
// 7. Skrinshotlar
for (const [u, name, w] of [['/ticket?code=00001', 'ticket_00001', 3000], ['/ticket?code=11222', 'ticket_11222', 3000], ['/ticket?code=11223', 'ticket_11223_xato', 600],
  ['/gal?code=0001', 'gal_0001', 1800], ['/gal?code=1000', 'gal_1000', 1800], ['/gal?code=1001', 'gal_1001_xato', 600],
  ['/gold?code=0001', 'gold_0001', 1800], ['/gold?code=2001', 'gold_2001_xato', 600], ['/silver?code=0001', 'silver_0001', 1800], ['/silver?code=4001', 'silver_4001_xato', 600], ['/xyz', '404_neytral', 600]]) {
  await p.goto(base + u); await p.waitForTimeout(w); await p.screenshot({ path: `${out}/${name}.png` });
}
ok('UMUMIY', 'Sahifalarda JavaScript xatolari yo\'q', errors.length === 0, errors.slice(0, 3).join(' | '));
await b.close();
fs.writeFileSync(out + '/route_results.json', JSON.stringify(R, null, 1));
console.log(`\n${R.filter(r => r.ok).length}/${R.length} PASS`);
process.exit(R.every(r => r.ok) ? 0 : 1);
