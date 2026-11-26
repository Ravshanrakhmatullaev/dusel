// DUSEL — STAGING tutun testi (HTTPS, haqiqiy Supabase Auth + /rpc). Faqat SINOV QR'lari ishlatiladi.
//   BASE=https://<branch-ref>.supabase.co ANON_KEY=... ACCOUNTS='{"admin":{"email":"…","password":"…"},"sup":{…},"gate":{…},"inv":{…}}' node tests/staging_smoke.mjs
// Muhit STAGING bo'lmasa — darhol to'xtaydi. Kirish yopiq bo'lsa vaqtincha ochadi va oxirida qayta yopadi.
import fs from 'fs';
import crypto from 'crypto';
const E = process.env, BASE = (E.BASE || '').replace(/\/$/, ''), KEY = E.ANON_KEY || '', A = JSON.parse(E.ACCOUNTS || '{}');
const N = +(E.SMOKE_TICKET || 9950);   // sinov raqamlari: N, N+1
if (!BASE || !KEY || !A.admin || !A.sup || !A.gate || !A.inv) { console.error('BASE, ANON_KEY, ACCOUNTS (admin, sup, gate, inv) kerak'); process.exit(2); }
const R = []; const lat = [];
const ok = (n, c, d = '') => { R.push({ test: n, ok: !!c, detail: String(d).slice(0, 240) }); console.log((c ? 'PASS ' : 'FAIL ') + n + (d !== '' ? ' — ' + d : '')); };
const H = (t) => ({ apikey: KEY, 'content-type': 'application/json', ...(t ? { authorization: 'Bearer ' + t } : {}) });
async function login(u) { const r = await fetch(BASE + '/auth/v1/token?grant_type=password', { method: 'POST', headers: H(), body: JSON.stringify(u) }); const j = await r.json(); if (!r.ok) throw new Error('login ' + u.email); return j.access_token; }
async function rpc(t, fn, args = {}) {
  const t0 = performance.now(); const r = await fetch(BASE + '/rest/v1/rpc/' + fn, { method: 'POST', headers: H(t), body: JSON.stringify(args), signal: AbortSignal.timeout(15000) });
  lat.push([fn, performance.now() - t0]); const j = await r.json().catch(() => null); return r.ok ? j : { error: (j && j.message) || String(r.status) };
}
const T = (n, shape = 0) => [`https://dusel.pages.dev/?code=${String(n).padStart(5, '0')}&t=SINOV`, `https://dusel.pages.dev/ticket?code=${String(n).padStart(5, '0')}&t=SINOV`,
                             `https://ravshanrakhmatullaev.github.io/dusel/?code=${String(n).padStart(5, '0')}&t=SINOV`][shape];
const tok = {}; for (const k of ['admin', 'sup', 'gate', 'inv']) tok[k] = await login(A[k]);
const me = {}; for (const k of Object.keys(tok)) me[k] = await rpc(tok[k], 'ci_me');
const env = String(me.admin.environment || '').replace(/"/g, '');
if (env !== 'STAGING') { console.error('TO\'XTATILDI: muhit ' + env); process.exit(3); }
ok('S1 4 rol HTTPS orqali kirdi, muhit STAGING', ['ADMIN', 'SUPERVISOR', 'GATE', 'INVENTORY'].every((r, i) => me[['admin', 'sup', 'gate', 'inv'][i]].role === r), Object.values(me).map((m) => m.role).join(','));
const d0 = await rpc(tok.admin, 'ci_dashboard'); const wasOpen = JSON.parse(String(d0.admission_open));
if (!wasOpen) await rpc(tok.admin, 'ci_admission_set', { p_open: true, p_confirm: 'KIRISHNI OCHISH' });
// kirish
const lk = await rpc(tok.gate, 'ci_lookup', { p_payload: T(N, 2), p_gate: 'G1', p_device: 'smoke' });
const a1 = await rpc(tok.gate, 'ci_admit', { p_request: crypto.randomUUID(), p_payload: T(N, 0), p_gate: 'G1', p_device: 'smoke' });
const a2 = await rpc(tok.gate, 'ci_admit', { p_request: crypto.randomUUID(), p_payload: T(N, 1), p_gate: 'G2', p_device: 'smoke' });
const rid = crypto.randomUUID();
const a3 = await rpc(tok.gate, 'ci_admit', { p_request: rid, p_payload: 'DUSELTEST:' + String(N + 2).padStart(5, '0'), p_gate: 'G1', p_device: 'smoke' });
const a3b = await rpc(tok.gate, 'ci_admit', { p_request: rid, p_payload: 'DUSELTEST:' + String(N + 2).padStart(5, '0'), p_gate: 'G1', p_device: 'smoke' });
const fg = await rpc(tok.gate, 'ci_admit', { p_request: crypto.randomUUID(), p_payload: 'https://dusel.pages.dev/gold?code=9999', p_gate: 'G1', p_device: 'smoke' });
ok('S2 Sinov bileti: ko\'rish → kiritish → boshqa URL formati bilan takror rad; qayta yuborish bitta yozuv; kupon rad',
   lk.result === 'FOUND' && a1.decision === 'ADMITTED' && a2.decision === 'DENIED_ALREADY_ADMITTED' && a3.decision === 'ADMITTED' && a3b.replay && fg.decision === 'DENIED_FOREIGN_SYSTEM',
   [lk.result, a1.decision, a2.decision, a3.decision, a3b.replay, fg.decision].join(' '));
// 10 parallel kiritish
const par = await Promise.all(Array.from({ length: 10 }, () => rpc(tok.gate, 'ci_admit', { p_request: crypto.randomUUID(), p_payload: T(N + 3, 0), p_gate: 'G3', p_device: 'smoke-par' })));
ok('S3 Bir sinov biletiga 10 parallel so\'rov → aynan 1 kiritildi', par.filter((x) => x.decision === 'ADMITTED').length === 1, par.map((x) => x.decision || x.error).join(','));
// rollar
const r1 = await rpc(tok.gate, 'ci_inventory_batches'); const r2 = await rpc(tok.inv, 'ci_admit', { p_request: crypto.randomUUID(), p_payload: T(N + 4), p_gate: 'G1', p_device: 'x' });
const r3 = await rpc(tok.sup, 'ci_setting_set', { p_key: 'capacity', p_value: 11300 });
ok('S4 Rollar va sig\'im qulfi: darvoza inventar qila olmaydi, inventar kirita olmaydi, sig\'im o\'zgarmaydi', r1.error === 'ROLE_DENIED' && r2.error === 'ROLE_DENIED' && /ROLE_DENIED|USE_CAPACITY_CHANGE/.test(r3.error || ''), [r1.error, r2.error, r3.error].join(' '));
// inventar: takror → qaror → konvert → muhr
const b = await rpc(tok.inv, 'ci_inventory_batch_open', { p_name: 'smoke', p_location: 'smoke', p_sector: null, p_box: null, p_stack: null, p_device: 'smoke' });
const s1 = await rpc(tok.inv, 'ci_inventory_scan', { p_request: crypto.randomUUID(), p_batch: b.id, p_payload: T(N + 5), p_seat_note: null, p_source: 'SCANNER', p_device: 'smoke', p_client_at: null });
const s2 = await rpc(tok.inv, 'ci_inventory_scan', { p_request: crypto.randomUUID(), p_batch: b.id, p_payload: T(N + 5, 1), p_seat_note: null, p_source: 'SCANNER', p_device: 'smoke', p_client_at: null });
const env1 = await rpc(tok.inv, 'ci_envelope_open', { p_location: 'smoke', p_note: 'tutun testi' });
const v = await rpc(tok.inv, 'ci_inventory_verdict', { p_scan: s2.scan_id, p_verdict: 'SECOND_COPY', p_note: null, p_envelope: env1.code });
const sl = await rpc(tok.inv, 'ci_envelope_seal', { p_code: env1.code, p_counted: 1 });
await rpc(tok.inv, 'ci_inventory_batch_close', { p_batch: b.id });
const st = await rpc(tok.sup, 'ci_lookup', { p_payload: T(N + 5), p_gate: 'G1', p_device: 'smoke' });
ok('S5 Inventar: takror qaror kutadi → ikkinchi qog\'oz konvertga → muhr; bilet holati o\'zgarmagan, darvozada belgi ko\'rinadi',
   s1.result === 'RECORDED' && s2.needs_verdict && v.confirmed_copies === 2 && sl.status === 'SEALED' && st.credential && st.credential.status === 'NOT_ADMITTED' && st.admissible
   && (st.warnings || []).some((w) => w.code === 'FLAG_DUPLICATE_PRINT_CONFIRMED'), [s2.needs_verdict, v.confirmed_copies, sl.status, st.credential && st.credential.status].join(' '));
const cap = await rpc(tok.sup, 'ci_capacity_status');
ok('S6 Sig\'im invarianti butun, ruxsatlar ≤ 11 222', cap.invariant_ok && cap.entitlements <= cap.approved_capacity && cap.approved_capacity === 11222, cap.entitlements + '/' + cap.approved_capacity);
if (!wasOpen) await rpc(tok.admin, 'ci_admission_set', { p_open: false, p_confirm: null });
const d1 = await rpc(tok.admin, 'ci_dashboard');
ok('S7 Kirish holati tutun testidan oldingi holatga qaytdi', JSON.parse(String(d1.admission_open)) === wasOpen, String(d1.admission_open));
const by = {}; for (const [f, ms] of lat) (by[f] = by[f] || []).push(ms);
const p = (a, q) => { const s = [...a].sort((x, y) => x - y); return +s[Math.min(s.length - 1, Math.floor(q * s.length))].toFixed(0); };
const latency = Object.fromEntries(Object.entries(by).map(([f, a]) => [f, { n: a.length, p50: p(a, 0.5), max: p(a, 1) }]));
console.log('Kechikish (ms):', JSON.stringify(latency));
fs.writeFileSync(E.OUT || 'staging_smoke.json', JSON.stringify({ base: BASE.replace(/\/\/([^.]+)\./, '//***.'), results: R, latency }, null, 1));
console.log(`\n${R.filter((r) => r.ok).length}/${R.length} PASS`);
process.exit(R.every((r) => r.ok) ? 0 : 1);
