// DUSEL — konsert kuni real vaqt monitoringi (nazoratchi ish stoli / noutbukda ishlaydi). Faqat o'qiydi.
//   SITE=https://dusel.pages.dev BASE=https://<ref>.supabase.co ANON_KEY=... MON_EMAIL=... MON_PASS=... node tools/monitor.mjs
// MON_* — SUPERVISOR rolidagi alohida "monitor" xodim. Har INTERVAL soniyada:
//   1) /checkin sahifasi (Cloudflare) 2) Supabase Auth sog'ligi 3) RPC kechikishi (ci_me)
//   4) ci_dashboard: kirish holati, darvozalar oxirgi skan vaqti, ochiq holatlar 5) ci_capacity_status invarianti
// Muammo bo'lsa: qizil qator + ovozli signal (terminal bell) + monitor_log.csv
import fs from 'fs';
const E = process.env, SITE = E.SITE || 'https://dusel.pages.dev', BASE = (E.BASE || '').replace(/\/$/, ''), KEY = E.ANON_KEY || '';
const INTERVAL = +(E.INTERVAL || 15) * 1000, STALE_MIN = +(E.STALE_MIN || 3), SLOW_MS = +(E.SLOW_MS || 1500);
if (!BASE || !KEY || !E.MON_EMAIL) { console.error('BASE, ANON_KEY, MON_EMAIL, MON_PASS kerak'); process.exit(2); }
const H = (t) => ({ apikey: KEY, 'content-type': 'application/json', ...(t ? { authorization: 'Bearer ' + t } : {}) });
let tok = null, tokAt = 0;
async function token() {
  if (tok && Date.now() - tokAt < 30 * 60 * 1000) return tok;
  const r = await fetch(BASE + '/auth/v1/token?grant_type=password', { method: 'POST', headers: H(), body: JSON.stringify({ email: E.MON_EMAIL, password: E.MON_PASS }), signal: AbortSignal.timeout(8000) });
  const j = await r.json(); if (!r.ok) throw new Error('login'); tok = j.access_token; tokAt = Date.now(); return tok;
}
async function timed(fn) { const t = performance.now(); try { const v = await fn(); return [v, performance.now() - t, null]; } catch (e) { return [null, performance.now() - t, e.message || String(e)]; } }
const rpc = async (fn, args = {}) => { const r = await fetch(BASE + '/rest/v1/rpc/' + fn, { method: 'POST', headers: H(await token()), body: JSON.stringify(args), signal: AbortSignal.timeout(8000) }); const j = await r.json(); if (!r.ok) throw new Error(j.message || r.status); return j; };
const log = fs.createWriteStream('monitor_log.csv', { flags: 'a' });
const minutesAgo = (s) => { if (!s) return Infinity; const [d, t] = s.split(' '); const [dd, mm, yy] = d.split('.'); return (Date.now() - new Date(`${yy}-${mm}-${dd}T${t}+05:00`).getTime()) / 60000; };
async function once() {
  const probs = [], info = [];
  const [site, ms1, e1] = await timed(async () => (await fetch(SITE + '/checkin', { signal: AbortSignal.timeout(8000) })).status);
  if (e1 || site !== 200) probs.push('SAYT /checkin ' + (e1 || site)); else info.push(`sayt ${ms1.toFixed(0)}ms`);
  const [auth, ms2, e2] = await timed(async () => (await fetch(BASE + '/auth/v1/health', { headers: H(), signal: AbortSignal.timeout(8000) })).status);
  if (e2 || auth !== 200) probs.push('AUTH ' + (e2 || auth)); else info.push(`auth ${ms2.toFixed(0)}ms`);
  const [me, ms3, e3] = await timed(() => rpc('ci_me'));
  if (e3) probs.push('BAZA/RPC ' + e3); else { info.push(`rpc ${ms3.toFixed(0)}ms`); if (ms3 > SLOW_MS) probs.push(`SEKIN RPC ${ms3.toFixed(0)}ms`); }
  if (!e3) {
    const [d, , e4] = await timed(() => rpc('ci_dashboard'));
    const [c, , e5] = await timed(() => rpc('ci_capacity_status'));
    if (d) {
      const open = JSON.parse(String(d.admission_open));
      info.push(`kirish ${open ? 'OCHIQ' : 'yopiq'} · kirgan ${d.admission.admitted_tickets + d.admission.admitted_replacements} · takror ${d.admission.duplicate_scans} · ochiq holat ${d.cases.open + d.cases.escalated}`);
      if (open) for (const g of d.gates) { const m = minutesAgo(g.last_scan); if (m > STALE_MIN && g.admitted > 0) probs.push(`DARVOZA ${g.gate} ${m === Infinity ? 'hech skan yo\'q' : m.toFixed(0) + ' daq skan yo\'q'}`); }
    } else probs.push('PANEL ' + e4);
    if (c && !c.invariant_ok) probs.push('SIG\'IM INVARIANTI BUZILGAN!'); else if (c) info.push(`ruxsat ${c.entitlements}/${c.approved_capacity}`);
    if (e5) probs.push('SIG\'IM ' + e5);
  }
  const ts = new Date().toLocaleTimeString('uz-UZ', { hour12: false });
  if (probs.length) process.stdout.write(`\x07\x1b[41;97m ${ts} MUAMMO: ${probs.join(' | ')} \x1b[0m  ${info.join(' · ')}\n`);
  else process.stdout.write(`\x1b[32m${ts} OK\x1b[0m  ${info.join(' · ')}\n`);
  log.write([new Date().toISOString(), probs.length ? 'PROBLEM' : 'OK', '"' + probs.join('; ') + '"', '"' + info.join('; ') + '"'].join(',') + '\n');
}
for (;;) { await once().catch((e) => console.log('monitor xatosi', e.message)); await new Promise((s) => setTimeout(s, INTERVAL)); }
