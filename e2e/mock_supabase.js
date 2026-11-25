// LOKAL TEST SERVERI: Supabase Auth (parol bilan kirish) va PostgREST /rpc ni lokal Postgres ustida taqlid qiladi,
// hamda saytni (Cloudflare Pages kabi "pretty URL") beradi. Faqat avtomatik testlar uchun — production'da ishlatilmaydi.
const http = require('http'), fs = require('fs'), path = require('path'), crypto = require('crypto');
const { Pool } = require('pg');
const SITE = process.argv[2] || '/home/claude/dusel';
const PORT = +(process.argv[3] || 8799);
const pool = new Pool({ host: process.env.PGHOST || '/tmp', port: +(process.env.PGPORT || 5433), user: process.env.PGUSER || 'postgres', password: process.env.PGPASSWORD, database: process.argv[4] || 'ci_e2e', max: 40 });
const SECRET = 'local-test-secret';
const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
function jwt(user, ttl) {
  const now = Math.floor(Date.now() / 1000);
  const p = { sub: user.id, email: user.email, role: 'authenticated', aud: 'authenticated', iat: now, exp: now + (ttl || 3600) };
  const h = b64({ alg: 'HS256', typ: 'JWT' }) + '.' + b64(p);
  return h + '.' + crypto.createHmac('sha256', SECRET).update(h).digest('base64url');
}
function verify(tok) {
  try {
    const [h, p, s] = tok.split('.');
    if (crypto.createHmac('sha256', SECRET).update(h + '.' + p).digest('base64url') !== s) return null;
    const c = JSON.parse(Buffer.from(p, 'base64url').toString()); if (c.exp < Date.now() / 1000) return null; return c;
  } catch (e) { return null; }
}
const refresh = new Map();
function session(u) {
  const rt = crypto.randomBytes(16).toString('hex'); refresh.set(rt, u);
  const at = jwt(u);
  return { access_token: at, token_type: 'bearer', expires_in: 3600, expires_at: Math.floor(Date.now() / 1000) + 3600, refresh_token: rt,
           user: { id: u.id, aud: 'authenticated', role: 'authenticated', email: u.email, app_metadata: {}, user_metadata: {}, created_at: '2026-01-01T00:00:00Z' } };
}
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2', '.json': 'application/json', '.jpg': 'image/jpeg' };
function send(res, code, body, type) { res.writeHead(code, { 'content-type': type || 'application/json', 'access-control-allow-origin': '*' }); res.end(typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body)); }
function stat(p) { try { const s = fs.statSync(p); return s.isFile() ? p : null; } catch (e) { return null; } }

http.createServer((req, res) => {
  let body = '';
  req.on('data', (c) => body += c);
  req.on('end', async () => {
    const u = new URL(req.url, 'http://x');
    if (req.method === 'OPTIONS') { res.writeHead(204, { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' }); return res.end(); }
    try {
      if (u.pathname === '/auth/v1/token') {
        const b = JSON.parse(body || '{}');
        if (u.searchParams.get('grant_type') === 'password') {
          const r = await pool.query("select id::text, email from auth.users where lower(email)=lower($1) and encrypted_password = extensions.crypt($2, encrypted_password)", [b.email, b.password]);
          if (!r.rows[0]) return send(res, 400, { error: 'invalid_grant', error_description: 'Invalid login credentials' });
          return send(res, 200, session(r.rows[0]));
        }
        const usr = refresh.get(b.refresh_token); if (!usr) return send(res, 400, { error: 'invalid_grant' });
        refresh.delete(b.refresh_token); return send(res, 200, session(usr));
      }
      if (u.pathname === '/auth/v1/user') {
        const c = verify((req.headers.authorization || '').replace(/^Bearer /, ''));
        if (!c) return send(res, 401, { msg: 'invalid' });
        return send(res, 200, { id: c.sub, email: c.email, aud: 'authenticated', role: 'authenticated', app_metadata: {}, user_metadata: {} });
      }
      if (u.pathname === '/auth/v1/logout') { res.writeHead(204, { 'access-control-allow-origin': '*' }); return res.end(); }
      const m = /^\/rest\/v1\/rpc\/([a-z_0-9]+)$/.exec(u.pathname);
      if (m) {
        const claims = verify((req.headers.authorization || '').replace(/^Bearer /, ''));
        const args = JSON.parse(body || '{}'), keys = Object.keys(args);
        const vals = keys.map((k) => args[k] !== null && typeof args[k] === 'object' ? JSON.stringify(args[k]) : (typeof args[k] === 'boolean' && k === 'p_value' ? JSON.stringify(args[k]) : args[k]));
        const sql = `select public.${m[1]}(${keys.map((k, i) => `${k} := $${i + 1}`).join(', ')}) as r`;
        const c = await pool.connect();
        try {
          await c.query('begin');
          await c.query(`set local role ${claims ? 'authenticated' : 'anon'}`);
          await c.query("select set_config('request.jwt.claims', $1, true)", [claims ? JSON.stringify(claims) : '']);
          const r = await c.query(sql, vals);
          await c.query('commit');
          return send(res, 200, r.rows[0].r);
        } catch (e) {
          await c.query('rollback').catch(() => {});
          const st = e.code === '42501' ? (claims ? 403 : 401) : e.code === '42883' ? 404 : 400;
          return send(res, st, { code: e.code, message: e.message, hint: e.hint || null, details: e.detail || null });
        } finally { c.release(); }
      }
      // statik sayt (Cloudflare Pages: /checkin -> checkin.html, topilmasa 404.html)
      let p = path.join(SITE, decodeURIComponent(u.pathname));
      if (!p.startsWith(SITE)) return send(res, 403, 'no');
      let f = stat(p) || stat(path.join(p, 'index.html')) || stat(p + '.html');
      let code = 200;
      if (!f) { f = path.join(SITE, '404.html'); code = 404; }
      const hdr = { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' };
      // Cloudflare _headers dagi CSP ni taqlid qilamiz — ilova CSP bilan ishlashini tekshirish uchun
      if (/^\/checkin(\.html)?$/.test(u.pathname)) {
        const rules = fs.readFileSync(path.join(SITE, '_headers'), 'utf8').split('\n');
        const i = rules.indexOf('/checkin');
        for (let j = i + 1; j < rules.length && /^\s/.test(rules[j]); j++) { const k = rules[j].trim(); const c = k.indexOf(':'); hdr[k.slice(0, c)] = k.slice(c + 1).trim(); }
      }
      res.writeHead(code, hdr);
      fs.createReadStream(f).pipe(res);
    } catch (e) { send(res, 500, { message: String(e) }); }
  });
}).listen(PORT, '127.0.0.1', () => console.log('mock on', PORT));
