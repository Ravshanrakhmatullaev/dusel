// DUSEL — HTTP(S) orqali ko'p darvozali yuklama testi (Supabase Auth + PostgREST /rpc, xuddi telefonlar kabi).
// FAQAT STAGING yoki lokal sinov bazasida. PRODUCTION muhitida o'zini to'xtatadi.
//
// Muhit o'zgaruvchilari:
//   BASE=https://<staging-ref>.supabase.co   ANON_KEY=<publishable key>
//   GATES='[{"email":"load-g1@...","password":"...","gate":"G1"}, ...]'   (har darvoza uchun alohida sinov xodimi)
//   ADMIN='{"email":"...","password":"..."}'                               (yakuniy tekshiruv uchun)
//   TICKETS=1-11222  DUP=0.10  FOREIGN=0.02  RETRY=0.01  PACE_MS=0  RACE=20  OUT=http_load.json
// node http_load_test.mjs
import fs from 'fs';
import crypto from 'crypto';
const E = process.env;
const BASE = (E.BASE || 'http://127.0.0.1:8800').replace(/\/$/, ''), KEY = E.ANON_KEY || 'local-test-anon-key';
const GATES = JSON.parse(E.GATES || '[]'), ADMIN = JSON.parse(E.ADMIN || 'null');
const [T0, T1] = (E.TICKETS || '1-11222').split('-').map(Number);
const DUP = +(E.DUP ?? 0.10), FOREIGN = +(E.FOREIGN ?? 0.02), RETRY = +(E.RETRY ?? 0.01), PACE = +(E.PACE_MS ?? 0), RACE = +(E.RACE ?? 20);
if (!GATES.length || !ADMIN) { console.error('GATES va ADMIN kerak'); process.exit(2); }

const H = (tok) => ({ apikey: KEY, 'content-type': 'application/json', ...(tok ? { authorization: 'Bearer ' + tok } : {}) });
async function login(u) {
  const r = await fetch(BASE + '/auth/v1/token?grant_type=password', { method: 'POST', headers: H(), body: JSON.stringify({ email: u.email, password: u.password }) });
  const j = await r.json(); if (!r.ok) throw new Error('login ' + u.email + ': ' + JSON.stringify(j)); return j.access_token;
}
const lat = {}; const add = (k, ms) => (lat[k] = lat[k] || []).push(ms);
const errs = {}; const err = (k) => (errs[k] = (errs[k] || 0) + 1);
async function rpc(tok, fn, args, kind) {
  const t = performance.now();
  try {
    const r = await fetch(BASE + '/rest/v1/rpc/' + fn, { method: 'POST', headers: H(tok), body: JSON.stringify(args), signal: AbortSignal.timeout(15000) });
    const j = await r.json().catch(() => null); add(kind || fn, performance.now() - t);
    if (!r.ok) { err(fn + ':' + ((j && j.message) || r.status)); return { error: (j && j.message) || String(r.status) }; }
    return j;
  } catch (e) { add(kind || fn, performance.now() - t); err(fn + ':NETWORK/' + e.name); return { error: 'NETWORK' }; }
}
const pct = (a, p) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); return +s[Math.min(s.length - 1, Math.floor(p / 100 * s.length))].toFixed(1); };

// ---------------------------------------------------------------- xavfsizlik: faqat STAGING/LOCAL
const adminTok = await login(ADMIN);
const me = await rpc(adminTok, 'ci_me', {});
const env = String(me.environment || '').replace(/"/g, '');
if (!/^(STAGING|LOCAL|LOCAL-TEST)$/.test(env)) { console.error('TO\'XTATILDI: muhit ' + env + ' — yuklama testi faqat STAGING da'); process.exit(3); }
const dash0 = await rpc(adminTok, 'ci_dashboard', {});
if (dash0.admission.admitted_tickets > 0 && E.ALLOW_DIRTY !== '1') { console.error('Staging bazasi toza emas (' + dash0.admission.admitted_tickets + ' kiritilgan). Avval tools/staging_reset.sh'); process.exit(4); }
if (!JSON.parse(String(dash0.admission_open))) { console.error('Staging\'da kirish yopiq — admin ci_admission_set(true, \'KIRISHNI OCHISH\') qilsin'); process.exit(5); }

const toks = await Promise.all(GATES.map(login));
const tickets = []; for (let i = T0; i <= T1; i++) tickets.push(String(i).padStart(5, '0'));
for (let i = tickets.length - 1; i > 0; i--) { const j = crypto.randomInt(i + 1); [tickets[i], tickets[j]] = [tickets[j], tickets[i]]; }
const U = (t) => 'https://dusel.pages.dev/?code=' + t;
const FOREIGNS = ['https://dusel.pages.dev/gold?code=0001', 'https://dusel.pages.dev/silver?code=0002', 'https://dusel.pages.dev/gal?code=0003'];
const admits = {};   // ticket -> [decisions]
const t0 = performance.now(); let ops = 0;

// ---------------------------------------------------------------- 1) 20 mijoz bir vaqtda bitta biletni kiritmoqchi
const raceTicket = tickets.pop();
const raceRes = await Promise.all(Array.from({ length: RACE }, (_, i) => rpc(toks[i % toks.length], 'ci_admit', { p_request: crypto.randomUUID(), p_payload: U(raceTicket), p_gate: GATES[i % GATES.length].gate, p_device: 'race-' + i }, 'admit_race')));
const raceOk = raceRes.filter((r) => r.decision === 'ADMITTED').length;

// ---------------------------------------------------------------- 2) ko'p darvoza: har biri o'z navbati
const slices = GATES.map((_, i) => tickets.filter((_, k) => k % GATES.length === i));
await Promise.all(GATES.map(async (g, gi) => {
  const tok = toks[gi];
  for (const t of slices[gi]) {
    const lk = await rpc(tok, 'ci_lookup', { p_payload: U(t), p_gate: g.gate, p_device: 'load-' + g.gate }); ops++;
    const rid = crypto.randomUUID();
    const a = await rpc(tok, 'ci_admit', { p_request: rid, p_payload: U(t), p_gate: g.gate, p_device: 'load-' + g.gate }); ops++;
    (admits[t] = admits[t] || []).push(a.decision || a.error);
    if (Math.random() < RETRY) { const a2 = await rpc(tok, 'ci_admit', { p_request: rid, p_payload: U(t), p_gate: g.gate, p_device: 'load-' + g.gate }, 'admit_retry'); ops++; if (a2.decision === 'ADMITTED' && !a2.replay) admits[t].push('RETRY_DOUBLE'); }
    if (Math.random() < DUP) { const o = (gi + 1) % GATES.length; const d = await rpc(toks[o], 'ci_admit', { p_request: crypto.randomUUID(), p_payload: U(t), p_gate: GATES[o].gate, p_device: 'load-dup' }, 'admit_dup'); ops++; admits[t].push('DUP:' + (d.decision || d.error)); }
    if (Math.random() < FOREIGN) { await rpc(tok, 'ci_admit', { p_request: crypto.randomUUID(), p_payload: FOREIGNS[crypto.randomInt(3)], p_gate: g.gate, p_device: 'load-' + g.gate }, 'admit_foreign'); ops++; }
    if (PACE) await new Promise((s) => setTimeout(s, PACE));
  }
}));
const secs = (performance.now() - t0) / 1000;

// ---------------------------------------------------------------- 3) yakuniy tekshiruv (server ma'lumotlari bo'yicha)
const dash = await rpc(adminTok, 'ci_dashboard', {}), cap = await rpc(adminTok, 'ci_capacity_status', {});
const doubles = Object.entries(admits).filter(([, d]) => d.filter((x) => x === 'ADMITTED' || x === 'DUP:ADMITTED' || x === 'RETRY_DOUBLE').length > 1).map(([t]) => t);
const notAdmitted = Object.entries(admits).filter(([, d]) => d[0] !== 'ADMITTED').length;
const report = {
  base: BASE.replace(/\/\/([^.]+)\./, '//***.'), environment: env, gates: GATES.length, tickets: tickets.length + 1, seconds: +secs.toFixed(1), operations: ops,
  ops_per_sec: +(ops / secs).toFixed(1),
  latency_ms: Object.fromEntries(Object.entries(lat).map(([k, a]) => [k, { n: a.length, p50: pct(a, 50), p95: pct(a, 95), p99: pct(a, 99), max: pct(a, 100) }])),
  race: { clients: RACE, ticket: raceTicket, successes: raceOk }, errors: errs,
  server: { admitted_tickets: dash.admission.admitted_tickets, duplicate_scans: dash.admission.duplicate_scans, entitlements: cap.entitlements, approved_capacity: cap.approved_capacity, invariant_ok: cap.invariant_ok },
  double_admissions: doubles.length, first_attempt_not_admitted: notAdmitted
};
const pass = raceOk === 1 && doubles.length === 0 && cap.invariant_ok && dash.admission.admitted_tickets === tickets.length + 1 - notAdmitted && dash.admission.admitted_tickets <= cap.approved_capacity;
report.result = pass ? 'PASS' : 'FAIL';
fs.writeFileSync(E.OUT || 'http_load.json', JSON.stringify(report, null, 1));
console.log(JSON.stringify(report, null, 1));
process.exit(pass ? 0 : 1);
