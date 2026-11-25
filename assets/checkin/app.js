/* DUSEL — Kirish nazorati (faqat xodimlar). Barcha qarorlar serverda; bu ilova faqat interfeys.
 * - Kirish: skan → server tekshiradi → KIRITISH (atomik, idempotent request_id bilan)
 * - Yashil "KIRISH TASDIQLANDI" faqat server muvaffaqiyatli yozganini tasdiqlagandan keyin chiqadi (optimistik natija yo'q)
 * - Inventar alohida ilovada: /inventory (bu ilova inventar qilmaydi)
 * - Nazorat: bahsli holatlar, zaxira joylar, almashtirish biletlari
 * - Panel / Admin: statistika, hisobotlar, sozlamalar
 */
(function () {
  'use strict';
  var CFG = window.DUSEL_CHECKIN_CONFIG || { disabled: true };
  var $app = document.getElementById('app');
  var LS = {
    get: function (k, d) { try { var v = localStorage.getItem('dusel_ci_' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem('dusel_ci_' + k, JSON.stringify(v)); } catch (e) {} },
    del: function (k) { try { localStorage.removeItem('dusel_ci_' + k); } catch (e) {} }
  };
  function uuid() {
    if (crypto.randomUUID) return crypto.randomUUID();
    var b = crypto.getRandomValues(new Uint8Array(16)); b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
    var h = Array.prototype.map.call(b, function (x) { return (x + 256).toString(16).slice(1); }).join('');
    return h.slice(0, 8) + '-' + h.slice(8, 12) + '-' + h.slice(12, 16) + '-' + h.slice(16, 20) + '-' + h.slice(20);
  }
  var S = { me: null, gate: LS.get('gate', ''), device: LS.get('device', null), tab: 'admit', quick: LS.get('quick', false),
            online: navigator.onLine, offlineMode: false, queue: LS.get('queue', []), batch: LS.get('batch', null) };
  if (!S.device) { S.device = 'dev-' + uuid().slice(0, 8); LS.set('device', S.device); }

  // ---------------------------------------------------------------- DOM yordamchilari (XSS'dan himoya: faqat textContent)
  function el(tag, attrs) {
    var n = document.createElement(tag), i, k;
    attrs = attrs || {};
    for (k in attrs) {
      if (!Object.prototype.hasOwnProperty.call(attrs, k) || attrs[k] == null || attrs[k] === false) continue;
      if (k === 'on') { for (var ev in attrs.on) n.addEventListener(ev, attrs.on[ev]); }
      else if (k === 'class') n.className = attrs[k];
      else if (k === 'text') n.textContent = attrs[k];
      else n.setAttribute(k, attrs[k] === true ? '' : attrs[k]);
    }
    for (i = 2; i < arguments.length; i++) add(n, arguments[i]);
    return n;
  }
  function add(n, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) { c.forEach(function (x) { add(n, x); }); return; }
    n.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
  }
  function render() { var args = Array.prototype.slice.call(arguments); $app.replaceChildren(); args.forEach(function (a) { add($app, a); }); }
  function toast(msg) {
    var t = el('div', { class: 'toast', role: 'status', text: msg }); document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 2600);
  }
  var audio;
  function beep(ok) {
    try {
      if (navigator.vibrate) navigator.vibrate(ok ? 80 : [200, 80, 200]);
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      var o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = ok ? 1046 : 220; g.gain.value = 0.15; o.connect(g); g.connect(audio.destination);
      o.start(); o.stop(audio.currentTime + (ok ? 0.12 : 0.45));
    } catch (e) {}
  }

  // ---------------------------------------------------------------- server bilan aloqa
  if (CFG.disabled) {
    render(el('section', { class: 'card center' }, el('h1', { text: 'Kirish nazorati faollashtirilmagan' }),
      el('p', { class: 'muted', text: 'Bu muhit (' + (CFG.env || '?') + ') uchun server sozlamasi yo\'q. Tashkilotchi tasdig\'idan keyin yoqiladi.' })));
    return;
  }
  var sb = window.supabase.createClient(CFG.url, CFG.key, {
    auth: { persistSession: true, autoRefreshToken: true, storageKey: 'dusel_ci_auth_' + CFG.env, detectSessionInUrl: false }
  });
  var ERR = {
    AUTH_DENIED: 'Siz xodimlar ro\'yxatida yo\'qsiz yoki hisobingiz o\'chirilgan', SESSION_REVOKED: 'Sessiya tugagan — qayta kiring',
    ROLE_DENIED: 'Bu amal uchun huquqingiz yo\'q', RATE_LIMIT: 'Juda tez — 5 soniya kuting', GATE_INVALID: 'Darvozani tanlang',
    SEAT_NOT_AVAILABLE: 'Joy bo\'sh emas yoki zaxirada yo\'q', SEAT_OCCUPIED: 'Joy band', CAPACITY_EXCEEDED: 'Sig\'im to\'lgan',
    CASE_NOT_FOUND_OR_CLOSED: 'Holat topilmadi yoki yopilgan', TICKET_NOT_ADMISSIBLE: 'Bilet allaqachon kiritilgan yoki bekor qilingan',
    BATCH_NOT_OPEN: 'Inventar to\'plami yopiq', NOTE_REQUIRED: 'Izoh yozing (kamida 5 belgi)', REASON_REQUIRED: 'Sababni yozing',
    REASON_AND_EVIDENCE_REQUIRED: 'Sabab va dalilni yozing', SEAT_NOT_RESERVED_FOR_CASE: 'Avval joyni shu holat uchun band qiling',
    CONFIRMATION_MISMATCH: 'Tasdiq matni noto\'g\'ri', CONTINGENCY_DEVICE_ONLY: 'Faqat belgilangan nazoratchi qurilmasi',
    NO_DISTRIBUTION_PROOF: 'Tarqatilmaganligi hujjat bilan tasdiqlanmagan (HELD/RETURNED yozuvi yo\'q)',
    NOT_PHYSICALLY_VERIFIED: 'Bilet yopilgan inventar partiyasida skanerlanmagan', DUPLICATE_COPIES_RISK: 'Bu raqamning bir necha nusxasi bor — zaxira bo\'lmaydi',
    SHEET_REPRINT_RISK: 'Varaqda dublikat bor — zaxira bo\'lmaydi', GATE_ACTIVITY_EXISTS: 'Bilet darvozada ko\'rilgan — zaxira bo\'lmaydi',
    EVIDENCE_REQUIRED: 'Isbotni batafsil yozing', ORIGINAL_NOT_SUPERSEDABLE: 'Asl bilet kiritilgan — uning o\'rnini bosib bo\'lmaydi',
    USE_STOCK_RETIREMENT: 'Asl joy faqat "zaxiradagi biletdan" bo\'limi orqali', USE_CAPACITY_CHANGE: 'Sig\'im faqat tashkilotchi qarori bilan'
  };
  function errText(e) {
    if (!e) return 'Noma\'lum xato';
    if (e.network) return 'Server bilan aloqa yo\'q';
    var m = (e.message || '').split('\n')[0];
    return ERR[m] || e.hint || m || 'Xato';
  }
  function call(fn, args, timeoutMs) {
    return new Promise(function (resolve, reject) {
      var done = false;
      var timer = setTimeout(function () { if (!done) { done = true; reject({ network: true, timeout: true }); } }, timeoutMs || 9000);
      sb.rpc(fn, args || {}).then(function (r) {
        if (done) return; done = true; clearTimeout(timer);
        if (r.error) {
          var code = (r.error.message || '').split('\n')[0];
          if (code === 'SESSION_REVOKED' || code === 'AUTH_DENIED' || r.status === 401) { signOut(code); }
          if (!r.error.code && /fetch|network/i.test(r.error.message || '')) reject({ network: true }); else reject(r.error);
        } else { setOnline(true); resolve(r.data); }
      }, function (e) { if (done) return; done = true; clearTimeout(timer); setOnline(false); reject({ network: true, err: e }); });
    });
  }
  function setOnline(v) {
    S.online = v;
    var n = document.getElementById('net');
    if (v) { n.hidden = true; if (S.queue.length) syncQueue(); }
    else { n.hidden = false; n.textContent = 'SERVER BILAN ALOQA YO\'Q — avtomatik ruxsat berilmaydi'; }
  }
  window.addEventListener('online', function () { setOnline(true); });
  window.addEventListener('offline', function () { setOnline(false); });

  function banner() {
    var b = document.getElementById('env');
    b.hidden = false; b.textContent = CFG.env === 'PRODUCTION' ? 'PRODUCTION — HAQIQIY KIRISH' : (CFG.env + ' — SINOV MUHITI, haqiqiy kirish emas');
    b.className = 'env' + (CFG.env === 'PRODUCTION' ? ' prod' : '');
  }
  banner();

  // ---------------------------------------------------------------- kirish / chiqish
  function signOut(reason) {
    Scanner.stop();
    sb.auth.signOut().catch(function () {});
    try { localStorage.removeItem('dusel_ci_auth_' + CFG.env); } catch (e) {}
    S.me = null; LS.del('roster');
    loginView(reason ? (ERR[reason] || reason) : null);
  }
  function loginView(msg) {
    var email = el('input', { type: 'email', autocomplete: 'username', placeholder: 'login@dusel', required: true });
    var pass = el('input', { type: 'password', autocomplete: 'current-password', required: true });
    var err = el('p', { class: 'small', style: 'color:#ff8a8a', text: msg || '' });
    var btn = el('button', { class: 'primary big', type: 'submit', text: 'Kirish' });
    render(el('section', { class: 'card' }, el('h1', { text: 'DUSEL · Kirish nazorati' }),
      el('p', { class: 'muted small', text: 'Faqat ruxsat berilgan xodimlar uchun. Mijozlar bilet sahifasini oddiy QR orqali ochadi.' }),
      el('form', { on: { submit: function (e) {
        e.preventDefault(); btn.disabled = true; err.textContent = '';
        sb.auth.signInWithPassword({ email: email.value.trim(), password: pass.value }).then(function (r) {
          btn.disabled = false;
          if (r.error) { err.textContent = 'Login yoki parol noto\'g\'ri'; return; }
          pass.value = ''; boot();
        }, function () { btn.disabled = false; err.textContent = 'Server bilan aloqa yo\'q'; });
      } } }, el('label', { text: 'Login (email)' }), email, el('label', { text: 'Parol' }), pass, el('div', { style: 'height:12px' }), btn, err)));
  }

  function boot() {
    call('ci_me').then(function (me) {
      if (me.role === 'INVENTORY') {
        return render(el('section', { class: 'card' }, el('h1', { text: 'Bu kirish nazorati emas' }),
          el('p', { text: 'Siz inventar xodimisiz. Inventar ilovasi: /inventory. Kirish nazoratiga ruxsatingiz yo\'q.' }),
          el('a', { href: 'inventory', class: 'pill', text: '/inventory ga o\'tish' }), ' ', el('button', { class: 'stop', on: { click: function () { signOut(); } }, text: 'Chiqish' })));
      }
      S.me = me;
      if (!me.gates.some(function (g) { return g.gate_id === S.gate; })) S.gate = '';
      if (!S.gate) return gateView();
      shell();
    }, function (e) { if (e.network) loginView('Server bilan aloqa yo\'q'); else signOut((e.message || '').split('\n')[0]); });
  }
  function gateView() {
    render(el('section', { class: 'card' }, el('h1', { text: 'Darvozani tanlang' }),
      el('p', { class: 'muted small', text: S.me.display_name + ' · ' + S.me.role + ' · qurilma ' + S.device }),
      S.me.gates.map(function (g) {
        return el('button', { class: 'big', style: 'margin-top:8px', on: { click: function () { S.gate = g.gate_id; LS.set('gate', g.gate_id); shell(); } } }, g.name + ' (' + g.gate_id + ')');
      }),
      el('div', { style: 'height:16px' }), el('button', { class: 'stop', on: { click: function () { signOut(); } }, text: 'Chiqish' })));
  }

  // ---------------------------------------------------------------- QR skaner: umumiy modul (kamera + tashqi skaner + yo'riqnoma)
  var Scanner = {
    start: function (box, cb) { window.DuselScanner.mount(box, function (v) { cb(v); }, { status: document.getElementById('camstatus') }); },
    stop: function () { window.DuselScanner.unmount(); }, reset: function () { window.DuselScanner.reset(); }
  };

  // ---------------------------------------------------------------- umumiy qobiq va yorliqlar
  function shell() {
    var tabs = [['admit', 'Kirish']];
    if (S.me.role !== 'GATE') tabs.push(['cases', 'Nazorat'], ['dash', 'Panel']);
    if (S.me.role === 'ADMIN') tabs.push(['admin', 'Admin']);
    var bar = document.querySelector('.tabs');
    if (!bar) { bar = el('nav', { class: 'tabs' }); document.body.appendChild(bar); }
    bar.replaceChildren();
    tabs.forEach(function (t) {
      bar.appendChild(el('button', { class: S.tab === t[0] ? 'on' : '', on: { click: function () { S.tab = t[0]; shell(); } }, text: t[1] }));
    });
    var head = el('div', { class: 'top' },
      el('div', {}, el('b', { text: S.me.display_name }), ' ', el('span', { class: 'pill', text: S.me.role }), ' ',
        el('span', { class: 'pill', text: S.gate }), ' ', S.me.admission_open ? el('span', { class: 'pill', style: 'background:var(--ok)', text: 'KIRISH OCHIQ' })
          : el('span', { class: 'pill', style: 'background:var(--bad)', text: 'KIRISH YOPIQ' })),
      el('div', {}, el('button', { class: 'small', on: { click: function () { S.gate = ''; LS.del('gate'); Scanner.stop(); gateView(); } }, text: 'Darvoza' }), ' ',
        el('button', { class: 'small', on: { click: function () { signOut(); } }, text: 'Chiqish' })));
    Scanner.stop();
    ({ admit: admitView, cases: casesView, dash: dashView, admin: adminView }[S.tab] || admitView)(head);
  }

  function seatGrid(c) {
    return el('div', { class: 'seat' },
      el('div', {}, el('span', { text: 'Bilet' }), el('b', { text: c.ticket_no || ('…' + (c.token_hint || '')) })),
      el('div', {}, el('span', { text: c.kind === 'BLITCHER' ? 'Blitcher' : 'Sektor' }), el('b', { text: c.sector })),
      el('div', {}, el('span', { text: 'Qator' }), el('b', { text: c.row })),
      el('div', {}, el('span', { text: 'Joy' }), el('b', { text: c.seat })));
  }
  function warnList(ws) {
    if (!ws || !ws.length) return null;
    return el('ul', { class: 'warns' }, ws.map(function (w) { return el('li', { text: '⚠ ' + w.text }); }));
  }

  // ---------------------------------------------------------------- KIRISH
  var current = null;   // { payload, request_id }
  function admitView(head) {
    var cam = el('div'), out = el('div');
    var manual = el('input', { inputmode: 'numeric', placeholder: '5 xonali bilet raqami', maxlength: 60, autocomplete: 'off' });
    var quick = el('input', { type: 'checkbox' }); quick.checked = !!S.quick;
    quick.addEventListener('change', function () { S.quick = quick.checked; LS.set('quick', S.quick); });
    render(head, S.offlineMode ? offlineBanner() : null, cam, out,
      el('section', { class: 'card' },
        el('form', { class: 'row', on: { submit: function (e) { e.preventDefault(); var v = window.DuselScanner.normalize(manual.value); if (v) { handle(v, out); manual.value = ''; } } } },
          manual, el('button', { class: 'primary', type: 'submit', style: 'flex:0 0 auto', text: 'Tekshirish' })),
        el('label', { style: 'display:flex;gap:8px;align-items:center;margin-top:10px' }, quick,
          el('span', { text: 'Tezkor rejim: skan = darhol kiritish (faqat ruxsat bo\'lsa)' })),
        el('p', { class: 'muted small', text: 'Tashqi 2D skaner (USB/Bluetooth) ham ishlaydi — maydonni bo\'sh qoldirib skanerlang.' }),
        el('p', { class: 'small', id: 'camstatus' }),
        S.queue.length ? el('p', { class: 'small', text: 'Sinxronlanmagan favqulodda yozuvlar: ' + S.queue.length }) : null,
        el('p', { class: 'muted small', text: 'Xodim: ' + S.me.username + ' · qurilma ' + S.device + ' · server vaqti ' + S.me.server_time })));
    Scanner.start(cam, function (code) { handle(code, out); });
  }
  function handle(payload, out) {
    if (S.offlineMode) return offlineAdmit(payload, out);
    current = { payload: payload, request_id: uuid() };
    if (S.quick) return doAdmit(current, out);
    out.replaceChildren(el('div', { class: 'result info' }, el('div', { class: 'big', text: 'Tekshirilmoqda…' })));
    call('ci_lookup', { p_payload: payload, p_gate: S.gate, p_device: S.device }).then(function (r) {
      showLookup(r, current, out);
    }, function (e) { showError(e, out, function () { handle(payload, out); }); });
  }
  function showLookup(r, req, out) {
    if (r.result === 'FOREIGN' || r.result === 'INVALID' || r.result === 'NOT_FOUND') {
      beep(false);
      return out.replaceChildren(el('div', { class: 'result bad' }, el('div', { class: 'big', text: r.result === 'FOREIGN' ? 'BU KONSERT BILETI EMAS' : 'YAROQSIZ QR' }),
        el('p', { text: r.message || 'Bilet topilmadi' })));
    }
    var c = r.credential, ok = r.admissible;
    var cls = ok ? (r.warnings.length ? 'warn' : 'ok') : 'bad';
    out.replaceChildren(el('div', { class: 'result ' + cls },
      el('div', { class: 'big', text: ok ? 'KIRITISH MUMKIN' : (c.status === 'ADMITTED' ? 'ALLAQACHON KIRITILGAN' : 'KIRITIB BO\'LMAYDI') }),
      seatGrid(c), el('div', { class: 'small', text: c.zone + ' · holat: ' + c.status + (c.admitted_at ? ' · ' + c.admitted_at + ' ' + c.admitted_gate : '') }),
      warnList(r.warnings),
      el('div', { class: 'row', style: 'margin-top:12px' },
        ok ? el('button', { class: 'go big', on: { click: function () { doAdmit(req, out); } }, text: 'KIRITISH' }) : null,
        c.type === 'TICKET' ? el('button', { class: 'warn', on: { click: function () { refer(req.payload, out); } }, text: 'Nazoratchiga' }) : null,
        el('button', { on: { click: function () { out.replaceChildren(); Scanner.reset(); } }, text: 'Bekor' }))));
    if (!ok) beep(false);
  }
  function doAdmit(req, out, attempt) {
    attempt = attempt || 1;
    out.replaceChildren(el('div', { class: 'result info' }, el('div', { class: 'big', text: attempt > 1 ? 'Qayta yuborilmoqda (' + attempt + ')…' : 'Kiritilmoqda…' })));
    call('ci_admit', { p_request: req.request_id, p_payload: req.payload, p_gate: S.gate, p_device: S.device }).then(function (r) {
      showAdmit(r, req, out);
    }, function (e) {
      // tarmoq xatosi: AYNAN o'sha request_id bilan qayta urinish — ikki marta kiritish mumkin emas
      if (e.network && attempt < 3) return setTimeout(function () { doAdmit(req, out, attempt + 1); }, 700 * attempt);
      showError(e, out, function () { doAdmit(req, out, 1); }, true);
    });
  }
  function showAdmit(r, req, out) {
    var d = r.decision, c = r.credential || {};
    var MAP = {
      ADMITTED: ['ok', 'KIRISH TASDIQLANDI'], DENIED_ALREADY_ADMITTED: ['bad', 'ALLAQACHON KIRITILGAN / TAKROR SKAN'],
      DENIED_HELD_FOR_REVIEW: ['warn', 'TO\'XTATILGAN — NAZORATCHIGA'], DENIED_CANCELLED: ['bad', 'BEKOR QILINGAN BILET'],
      REFER_HELD_STOCK: ['warn', 'NAZORATCHIGA YUBORING'], DENIED_FOREIGN_SYSTEM: ['bad', 'BU KONSERT BILETI EMAS'],
      DENIED_INVALID: ['bad', 'YAROQSIZ QR'], DENIED_NOT_FOUND: ['bad', 'BILET TOPILMADI'], DENIED_ADMISSION_CLOSED: ['bad', 'KIRISH HALI OCHILMAGAN']
    };
    var m = MAP[d] || ['bad', d];
    beep(d === 'ADMITTED');
    out.replaceChildren(el('div', { class: 'result ' + m[0] },
      el('div', { class: 'big', text: m[1] }),
      c.sector ? seatGrid(c) : null,
      r.previous ? el('p', { text: 'Avvalgi kirish: ' + r.previous.at + ' · ' + r.previous.gate + '-darvoza' }) : null,
      d === 'DENIED_ALREADY_ADMITTED' ? el('p', { text: 'Mijozni ayblamang — muammo bosmaxona dublikati bo\'lishi mumkin. Nazorat stoliga yuboring' + (r.case_id ? ' (holat #' + r.case_id + ')' : '') + '.' }) : null,
      (d === 'REFER_HELD_STOCK' || d === 'DENIED_HELD_FOR_REVIEW') && r.case_id ? el('p', { text: 'Holat #' + r.case_id + ' ochildi — nazoratchi hal qiladi.' }) : null,
      r.message ? el('p', { text: r.message }) : null,
      r.replay ? el('p', { class: 'small', text: '(Takroriy so\'rov — natija serverdan qayta olindi, ikkinchi kirish yozilmadi)' }) : null,
      el('button', { style: 'margin-top:10px', on: { click: function () { out.replaceChildren(); Scanner.reset(); } }, text: 'Keyingi bilet' })));
    if (d === 'ADMITTED') setTimeout(function () { if (out.firstChild && out.firstChild.classList.contains('ok')) { out.replaceChildren(); Scanner.reset(); } }, 4000);
  }
  function refer(payload, out) {
    var reason = prompt('Sabab (masalan: "mijoz biletni distribyutordan olgan, chek bor")');
    if (reason === null) return;
    call('ci_refer', { p_payload: payload, p_gate: S.gate, p_reason: reason || 'Darvozadan yuborildi' }).then(function (r) {
      out.replaceChildren(el('div', { class: 'result warn' }, el('div', { class: 'big', text: 'Holat #' + r.case_id + ' ochildi' }),
        el('p', { text: 'Mijozni nazorat stoliga yo\'naltiring.' })));
    }, function (e) { toast(errText(e)); });
  }
  function showError(e, out, retry, unknown) {
    beep(false);
    out.replaceChildren(el('div', { class: 'result bad' },
      el('div', { class: 'big', text: e.network ? (unknown ? 'NATIJA NOMA\'LUM — KIRITMANG' : 'ALOQA YO\'Q') : 'XATO' }),
      el('p', { text: e.network ? (unknown ? 'Server javob bermadi. Mijozni o\'tkazmang. "Qayta urinish" xavfsiz — bir xil so\'rov ikki marta kiritmaydi.' : 'Internet aloqasini tekshiring.') : errText(e) }),
      e.network ? el('p', { style: 'font-weight:800', text: 'Avtomatik kirish TO\'XTATILDI. Nazoratchini chaqiring.' }) : null,
      el('div', { class: 'row' }, el('button', { class: 'primary', on: { click: retry }, text: 'Qayta urinish' }),
        e.network && contingencyAllowed() ? el('button', { class: 'warn', on: { click: startOffline }, text: 'Nazoratli favqulodda rejim' }) : null)));
  }

  // ---------------------------------------------------------------- FAVQULODDA (oflayn) rejim — nazoratchi kodi bilan
  function offlineBanner() {
    return el('div', { class: 'result warn offline' }, el('div', { class: 'big', text: 'NAZORATLI FAVQULODDA REJIM' }),
      el('p', { text: 'Faqat shu belgilangan nazoratchi qurilmasi. Qolgan darvozalar YOPIQ turadi. Har bir yozuv server tasdig\'isiz — aloqa tiklangach serverga yuboriladi; ziddiyatlar nazorat holatiga tushadi.' }),
      el('button', { on: { click: function () { S.offlineMode = false; shell(); } }, text: 'Oflayn rejimdan chiqish' }));
  }
  function contingencyAllowed() {
    var conf = LS.get('contingency', null);
    return !!(conf && conf.allowed && conf.salt && S.me && (S.me.role === 'SUPERVISOR' || S.me.role === 'ADMIN'));
  }
  function pbkdf2hex(code, salt, iter) {
    var enc = new TextEncoder();
    return crypto.subtle.importKey('raw', enc.encode(code), 'PBKDF2', false, ['deriveBits']).then(function (k) {
      return crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: enc.encode(salt), iterations: iter }, k, 256);
    }).then(function (b) { return Array.prototype.map.call(new Uint8Array(b), function (x) { return (x + 256).toString(16).slice(1); }).join(''); });
  }
  function startOffline() {
    var conf = LS.get('contingency', null);
    if (!contingencyAllowed()) { alert('Bu qurilma favqulodda rejim uchun belgilanmagan. Faqat Admin belgilagan nazoratchi qurilmasi ishlaydi.'); return; }
    var code = prompt('Nazoratchi favqulodda kodi (10–12 raqam)');
    if (!code) return;
    pbkdf2hex(code, conf.salt, conf.iter).then(function (h) {
      if (h !== conf.hash) { alert('Kod noto\'g\'ri'); return; }
      S.offlineMode = true; LS.set('offline_started', new Date().toISOString()); shell();
    });
  }
  function offlineAdmit(payload, out) {
    var m = /^(?:https?:\/\/(?:dusel\.pages\.dev\/(?:ticket(?:\.html)?|index\.html)?|ravshanrakhmatullaev\.github\.io\/dusel\/(?:index\.html)?)\?code=)?([0-9]{5})$/i.exec(payload.trim());
    var n = m && +m[1];
    if (!m || n < 1 || n > 11222) { beep(false); return out.replaceChildren(el('div', { class: 'result bad' }, el('div', { class: 'big', text: 'KONSERT BILETI EMAS' }))); }
    var t = m[1];
    var dup = S.queue.some(function (q) { return q.ticket === t; }) || (LS.get('local_admitted', []).indexOf(t) >= 0);
    if (dup) { beep(false); return out.replaceChildren(el('div', { class: 'result bad' }, el('div', { class: 'big', text: 'BU QURILMADA ALLAQACHON QABUL QILINGAN' }), el('p', { text: 'Nazoratchiga yuboring.' }))); }
    var roster = LS.get('roster', null), info = roster && roster[t];
    S.queue.push({ request_id: uuid(), payload: payload.trim(), ticket: t, offline_at: new Date().toISOString(), gate: S.gate });
    LS.set('queue', S.queue);
    beep(false);
    out.replaceChildren(el('div', { class: 'result warn' }, el('div', { class: 'big', text: 'NAZORAT OSTIDA QAYD ETILDI № ' + t }),
      el('p', { style: 'font-weight:800', text: 'Server tasdiqlamagan — bu "KIRISH TASDIQLANDI" emas.' }),
      info ? el('p', { text: info[1] + ' ' + info[2] + ' · qator ' + info[3] + ' · joy ' + info[4] }) : el('p', { text: 'Joy ma\'lumoti yuklanmagan (biletdagi yozuvga qarang)' }),
      el('p', { class: 'small', text: 'Navbatda: ' + S.queue.length })));
  }
  var syncing = false;
  function syncQueue() {
    if (syncing || !S.queue.length || !S.me) return; syncing = true;
    var conflicts = [];
    (function next() {
      if (!S.queue.length) {
        syncing = false;
        if (conflicts.length) alert('Favqulodda yozuvlar sinxron tugadi. ' + conflicts.length + ' ta ziddiyat (boshqa joyda allaqachon kiritilgan): ' + conflicts.join(', ') + '. Ular nazoratchi holatlariga tushdi.');
        else toast('Oflayn yozuvlar serverga yuborildi');
        return;
      }
      var q = S.queue[0];
      call('ci_admit', { p_request: q.request_id, p_payload: q.payload, p_gate: q.gate, p_device: S.device, p_offline_at: q.offline_at }).then(function (r) {
        if (r.decision !== 'ADMITTED') conflicts.push(q.ticket + ' (' + r.decision + ')');
        var la = LS.get('local_admitted', []); la.push(q.ticket); LS.set('local_admitted', la.slice(-5000));
        S.queue.shift(); LS.set('queue', S.queue); next();
      }, function () { syncing = false; });
    })();
  }

  // ---------------------------------------------------------------- NAZORAT: holatlar, zaxira joylar, almashtirish
  function casesView(head) {
    var list = el('div'), detail = el('div');
    var filter = el('select', {}, [['ACTIVE', 'Ochiq'], ['', 'Hammasi'], ['ESCALATED_NO_SEAT', 'Joy yo\'q'], ['RESOLVED_REPLACEMENT', 'Almashtirilgan'], ['RESOLVED_ADMITTED', 'Kiritilgan'], ['RESOLVED_REJECTED', 'Rad etilgan']]
      .map(function (o) { return el('option', { value: o[0], text: o[1] }); }));
    function load() {
      call('ci_cases', { p_status: filter.value || null }).then(function (cs) {
        list.replaceChildren(el('ul', { class: 'list' }, cs.length ? cs.map(function (c) {
          return el('li', {}, el('button', { style: 'width:100%;text-align:left', on: { click: function () { openCase(c.id, detail); } } },
            '#' + c.id + ' · № ' + (c.ticket_no || '—') + ' · ' + (c.sector || '') + ' q' + (c.row || '') + ' j' + (c.seat || '') + ' · ' + c.status + ' · ' + c.source + ' · urinish ' + c.attempts));
        }) : el('li', { class: 'muted', text: 'Holatlar yo\'q' })));
      }, function (e) { toast(errText(e)); });
    }
    filter.addEventListener('change', load);
    var tk = el('input', { placeholder: 'Bilet raqami yoki QR', inputmode: 'numeric' });
    render(head, el('section', { class: 'card' }, el('h2', { text: 'Ko\'rib chiqish holatlari' }), filter,
      el('form', { class: 'row', style: 'margin-top:8px', on: { submit: function (e) {
        e.preventDefault(); if (!tk.value.trim()) return;
        call('ci_refer', { p_payload: tk.value.trim(), p_gate: S.gate, p_reason: 'Nazoratchi ochdi' }).then(function (r) { openCase(r.case_id, detail); load(); }, function (er) { toast(errText(er)); });
      } } }, tk, el('button', { class: 'primary', style: 'flex:0 0 auto', text: 'Holat ochish' }))), list, detail);
    load();
  }
  function openCase(id, box) {
    call('ci_case', { p_id: id }).then(function (d) {
      var c = d.case, t = d.ticket;
      var cref = el('input', { placeholder: 'Mijoz (ism, telefon — maxfiy)', value: c.customer_ref || '' });
      var ev = el('textarea', { placeholder: 'Dalillar: asl bilet, chek, to\'lov, distribyutor yozuvi…' }); ev.value = c.evidence_summary || '';
      var note = el('textarea', { placeholder: 'Qaror izohi' });
      var spares = el('div');
      var active = ['OPEN', 'IN_REVIEW', 'ESCALATED_NO_SEAT'].indexOf(c.status) >= 0;
      box.replaceChildren(el('section', { class: 'card' },
        el('h2', { text: 'Holat #' + c.id + ' — ' + c.status }),
        el('p', { class: 'small muted', text: 'Manba: ' + c.source + ' · ochilgan ' + c.opened_at + ' · urinishlar ' + c.attempts + (c.reason ? ' · ' + c.reason : '') }),
        t ? el('div', { class: 'result ' + (t.status === 'ADMITTED' ? 'bad' : 'info') }, seatGrid(t), el('div', { class: 'small', text: 'Holat: ' + t.status + (t.admitted_at ? ' · kirgan ' + t.admitted_at + ' ' + t.admitted_gate + ' (' + (t.admitted_by || '') + ')' : '') + ' · tarqatish: ' + t.distribution + ' · inventar nusxalari: ' + t.inventory_copies }), warnList(d.warnings)) : null,
        el('h3', { text: 'Kirish urinishlari' }),
        el('ul', { class: 'list small' }, d.admissions.map(function (a) { return el('li', { text: a.at + ' · ' + a.gate + ' · ' + a.decision + ' · ' + (a.staff || '') }); })),
        d.inventory.length ? [el('h3', { text: 'Inventar' }), el('ul', { class: 'list small' }, d.inventory.map(function (s) { return el('li', { text: s.at + ' · ' + s.batch + (s.seat_note ? ' · ' + s.seat_note : '') + (s.voided ? ' (bekor)' : '') }); }))] : null,
        d.distribution.length ? [el('h3', { text: 'Tarqatish yozuvlari' }), el('ul', { class: 'list small' }, d.distribution.map(function (x) { return el('li', { text: x.at + ' · ' + x.status + ' · ' + x.source + (x.recipient_ref ? ' · ' + x.recipient_ref : '') }); }))] : null,
        d.replacements.length ? [el('h3', { text: 'Almashtirishlar' }), el('ul', { class: 'list small' }, d.replacements.map(function (r) { return el('li', { text: r.sector + ' q' + r.row + ' j' + r.seat + ' · ' + r.status + ' · …' + r.token_hint }); }))] : null,
        el('p', { class: 'small', style: 'color:var(--warn)', text: 'Eslatma: birinchi bo\'lib kirgan odam haqiqiy egasi ekanini anglatmaydi — nusxa (klon) ham birinchi kirishi mumkin. Qarorni dalillar asosida qiling.' }),
        active ? [el('label', { text: 'Mijoz' }), cref, el('label', { text: 'Dalillar' }), ev, el('label', { text: 'Izoh' }), note,
          el('div', { class: 'row', style: 'margin-top:8px' },
            el('button', { on: { click: function () { upd('IN_REVIEW'); } }, text: 'Saqlash (ko\'rib chiqilmoqda)' }),
            t && (t.status === 'NOT_ADMITTED' || t.status === 'HELD_FOR_REVIEW') ? el('button', { class: 'go', on: { click: function () {
              if (!confirm('Asl bilet № ' + t.ticket_no + ' bilan KIRITILSINMI?')) return;
              call('ci_supervisor_admit', { p_case: c.id, p_request: uuid(), p_gate: S.gate, p_device: S.device, p_note: note.value || ev.value }).then(function () { toast('Kiritildi'); openCase(id, box); }, function (e) { toast(errText(e)); });
            } }, text: 'Asl bilet bilan kiritish' }) : null,
            t && t.status === 'NOT_ADMITTED' ? el('button', { class: 'warn', on: { click: function () {
              call('ci_ticket_set_status', { p_ticket: t.ticket_no, p_status: 'HELD_FOR_REVIEW', p_reason: note.value || 'Tekshiruv uchun to\'xtatildi' }).then(function () { openCase(id, box); }, function (e) { toast(errText(e)); });
            } }, text: 'Biletni to\'xtatish' }) : null,
            t && t.status === 'HELD_FOR_REVIEW' ? el('button', { on: { click: function () {
              call('ci_ticket_set_status', { p_ticket: t.ticket_no, p_status: 'NOT_ADMITTED', p_reason: note.value || 'Tekshiruvdan keyin qayta ochildi' }).then(function () { openCase(id, box); }, function (e) { toast(errText(e)); });
            } }, text: 'To\'xtatishni bekor qilish' }) : null,
            el('button', { class: 'stop', on: { click: function () { if (confirm('Holat RAD ETILSINMI?')) upd('RESOLVED_REJECTED'); } }, text: 'Rad etish' }),
            el('button', { on: { click: function () { upd('ESCALATED_NO_SEAT'); } }, text: 'Tashkilotchiga' })),
          t && (t.status === 'NOT_ADMITTED' || t.status === 'HELD_FOR_REVIEW') ? [el('h3', { text: 'Asl bilet o\'rniga yangi QR (o\'sha joy)' }),
            el('p', { class: 'small muted', text: 'Asl bilet hali kiritilmagan (shikastlangan, yo\'qolgan, QR o\'qilmaydi). Asl bilet bekor qilinadi, yangi xavfsiz QR o\'sha joyga beriladi — jami ruxsatlar o\'zgarmaydi.' }),
            el('button', { class: 'warn', on: { click: function () {
              if (!ev.value.trim() || !note.value.trim()) { toast('Dalil va izohni yozing'); return; }
              if (prompt('Asl bilet № ' + t.ticket_no + ' BEKOR qilinadi. Tasdiqlash uchun bilet raqamini yozing') !== t.ticket_no) { toast('Bekor qilindi'); return; }
              call('ci_issue_replacement', { p_case: c.id, p_seat_key: t.seat_key, p_reason: note.value, p_evidence: ev.value, p_supersede: true }).then(function (r) {
                if (r.error) { toast(r.message); return openCase(id, box); }
                showReplacement(r, box);
              }, function (e) { toast(errText(e)); });
            } }, text: 'Asl bilet o\'rniga yangi QR berish' })] : null,
          el('h3', { text: 'Ikkinchi xaridor uchun zaxira joy' }),
          el('p', { class: 'small muted', text: 'Faqat tasdiqlangan zaxira joylar. Dublikat qog\'oz — qo\'shimcha joy EMAS. Joy yo\'q bo\'lsa — "Tashkilotchiga".' }), spares] : null));
      function upd(st) {
        call('ci_case_update', { p_id: c.id, p_status: st, p_customer_ref: cref.value, p_evidence: ev.value, p_note: note.value }).then(function () { toast('Saqlandi'); openCase(id, box); }, function (e) { toast(errText(e)); });
      }
      if (active) call('ci_spares', { p_sector: null }).then(function (sp) {
        if (!sp.length) return spares.replaceChildren(el('p', { class: 'muted small', text: 'Tasdiqlangan zaxira joy yo\'q. Joy bo\'lmasa — "Tashkilotchiga" (sig\'imdan oshib kiritilmaydi).' }));
        spares.replaceChildren(el('ul', { class: 'list' }, sp.map(function (s) {
          var mine = s.spare_status === 'RESERVED' && s.reserved_case === c.id;
          return el('li', {}, s.sector + ' · qator ' + s.row + ' · joy ' + s.seat + ' (' + s.zone + ', ' + s.origin + ') ',
            s.spare_status === 'AVAILABLE' ? el('button', { on: { click: function () {
              call('ci_spare_reserve', { p_case: c.id, p_seat_key: s.seat_key }).then(function () { openCase(id, box); }, function (e) { toast(errText(e)); });
            } }, text: 'Band qilish' }) : null,
            mine ? [el('button', { class: 'go', on: { click: function () {
              if (!ev.value.trim() || !note.value.trim()) { toast('Dalil va izohni yozing'); return; }
              if (!confirm('Yangi almashtirish bileti berilsinmi? (' + s.sector + ' q' + s.row + ' j' + s.seat + ')')) return;
              call('ci_issue_replacement', { p_case: c.id, p_seat_key: s.seat_key, p_reason: note.value, p_evidence: ev.value, p_supersede: false }).then(function (r) {
                if (r.error) { toast(r.message); return openCase(id, box); }
                showReplacement(r, box);
              }, function (e) { toast(errText(e)); });
            } }, text: 'Almashtirish bileti berish' }), el('button', { on: { click: function () {
              call('ci_spare_release', { p_seat_key: s.seat_key }).then(function () { openCase(id, box); });
            } }, text: 'Bo\'shatish' })] : (s.spare_status === 'RESERVED' ? el('span', { class: 'pill', text: 'holat #' + s.reserved_case + ' band qilgan' }) : null));
        })));
      });
    }, function (e) { toast(errText(e)); });
  }
  function qrSvg(text) {
    var q = window.qrcode(0, 'M'); q.addData(text); q.make();
    var holder = el('div'); holder.innerHTML = q.createSvgTag({ cellSize: 6, margin: 4, scalable: true });   // kutubxona chiqargan SVG — foydalanuvchi matni emas
    return holder.firstChild;
  }
  function showReplacement(r, box) {
    box.replaceChildren(el('section', { class: 'card' }, el('h2', { text: 'Almashtirish bileti berildi' }),
      el('p', { style: 'color:var(--warn)', text: r.notice }),
      el('div', { class: 'qrbox' }, el('div', { style: 'font-weight:900;font-size:18px', text: 'DUSEL · Yulduzli Kecha · 23.12.2026 · Humo Arena' }),
        qrSvg(r.payload), el('div', { style: 'font-size:20px;font-weight:800', text: (r.kind === 'BLITCHER' ? 'Blitcher ' : 'Sektor ') + r.sector + ' · Qator ' + r.row + ' · Joy ' + r.seat }),
        el('div', { class: 'small', text: 'Almashtirish № …' + r.token_hint + ' · asl bilet № ' + (r.original_ticket || '—') + ' · holat #' + r.case_id })),
      el('div', { class: 'row noprint', style: 'margin-top:10px' }, el('button', { class: 'primary', on: { click: function () { window.print(); } }, text: 'Chop etish' }),
        el('button', { on: { click: function () { shell(); } }, text: 'Yopish' }))));
  }

  // ---------------------------------------------------------------- PANEL
  function stat(n, label) { return el('div', { class: 'stat' }, el('b', { text: n == null ? '—' : n }), el('span', { text: label })); }
  function csv(rows, name) {
    if (!rows || !rows.length) { toast('Ma\'lumot yo\'q'); return; }
    var keys = Object.keys(rows[0]);
    var esc = function (v) { v = v == null ? '' : (typeof v === 'object' ? JSON.stringify(v) : String(v)); if (/^[=+\-@]/.test(v)) v = "'" + v; return '"' + v.replace(/"/g, '""') + '"'; };
    var text = '﻿' + keys.join(',') + '\n' + rows.map(function (r) { return keys.map(function (k) { return esc(r[k]); }).join(','); }).join('\n');
    var a = el('a', { href: URL.createObjectURL(new Blob([text], { type: 'text/csv' })), download: name + '.csv' });
    document.body.appendChild(a); a.click(); a.remove();
  }
  function dashView(head) {
    var box = el('div'), sect = el('div'), capbox = el('div');
    render(head, box, capbox, sect);
    function load() {
      call('ci_dashboard').then(function (d) {
        var a = d.admission;
        box.replaceChildren(el('section', { class: 'card' }, el('h2', { text: 'Kirish statistikasi · ' + d.server_time }),
          el('div', { class: 'stats' }, stat(d.allocated, 'Ajratilgan biletlar'), stat(a.admitted_tickets + a.admitted_replacements, 'Kiritilgan'),
            stat(a.remaining, 'Qolgan ruxsatlar'), stat(a.duplicate_scans, 'Takroriy skanlar (' + a.duplicate_scan_tickets + ' bilet)'),
            stat(a.held_for_review, 'To\'xtatilgan'), stat(d.cases.open + d.cases.escalated, 'Ochiq holatlar'), stat(d.cases.resolved, 'Hal qilingan'),
            stat(d.replacements.issued, 'Almashtirish biletlari'), stat(d.spares.available, 'Bo\'sh zaxira joylar'), stat(a.entitlements + ' / ' + d.capacity, 'Ruxsatlar / tasdiqlangan sig\'im'),
            stat(a.foreign_rejected, 'Kupon/vaucher rad'), stat(a.invalid_rejected, 'Yaroqsiz QR'))),
          el('section', { class: 'card' }, el('h2', { text: 'Jismoniy inventar (kirishdan alohida)' }),
            el('div', { class: 'stats' }, stat(d.inventory.scans, 'Skanlangan nusxalar'), stat(d.inventory.distinct_tickets, 'Turli raqamlar'),
              stat(d.inventory.duplicate_tickets, 'Dublikat raqamlar'), stat(d.inventory.surplus_copies, 'Ortiqcha nusxalar'),
              stat(d.distribution.DISTRIBUTED, 'Tarqatilgan (yozuv)'), stat(d.distribution.HELD, 'Zaxirada (yozuv)'), stat(d.distribution.UNKNOWN, 'Noma\'lum'), stat(d.inventory.seat_mismatch, 'Joy farqi'))),
          el('section', { class: 'card' }, el('h2', { text: 'Darvozalar' }), el('div', { class: 'tablewrap' }, el('table', {},
            el('tr', {}, ['Darvoza', 'Kiritildi', 'Rad', '15 daq', 'Oxirgi skan'].map(function (h) { return el('th', { text: h }); })),
            d.gates.map(function (g) { return el('tr', {}, [g.name, g.admitted, g.denied, g.last_15min, g.last_scan || '—'].map(function (v) { return el('td', { text: v }); })); })))),
          el('section', { class: 'card' }, el('h2', { text: 'Hisobotlar (CSV)' }), el('div', { class: 'row' },
            [['sector_summary', 'Sektorlar'], ['inventory_duplicates', 'Dublikatlar'], ['inventory_missing', 'Inventarda yo\'q'], ['seat_conflicts', 'Joy ziddiyatlari'],
             ['distribution', 'Tarqatish'], ['admissions', 'Kirishlar'], ['cases', 'Holatlar'], ['replacements', 'Almashtirishlar']].map(function (r) {
              return el('button', { class: 'small', on: { click: function () { call('ci_report', { p_name: r[0] }, 30000).then(function (rows) { csv(rows, 'dusel_' + r[0]); }, function (e) { toast(errText(e)); }); } }, text: r[1] });
            }),
            el('button', { class: 'small warn', on: { click: function () {
              call('ci_roster', {}, 30000).then(function (r) {
                var m = {}; r.rows.forEach(function (x) { m[x[0]] = x; }); LS.set('roster', m);
                csv(r.rows.map(function (x) { return { bilet: x[0], tur: x[1], sektor: x[2], qator: x[3], joy: x[4], holat: x[5], kirgan: x[6] || '', darvoza: x[7] || '' }; }), 'dusel_roster_' + Date.now());
                toast('Ro\'yxat yuklandi va qurilmada saqlandi (oflayn uchun)');
              }, function (e) { toast(errText(e)); });
            } }, text: 'Favqulodda ro\'yxat' }))));
      }, function (e) { box.replaceChildren(el('div', { class: 'result bad', text: errText(e) })); });
      call('ci_capacity_status').then(function (c) {
        capbox.replaceChildren(el('section', { class: 'card' }, el('h2', { text: 'Sig\'im nazorati' }),
          el('div', { class: 'result ' + (c.invariant_ok ? 'info' : 'bad') }, el('div', { class: 'stats' },
            stat(c.approved_capacity, 'Tasdiqlangan sig\'im'), stat(c.original_tickets, 'Asl biletlar'), stat(c.original_active, 'Amaldagi asl'),
            stat(c.retired_to_spare, 'Isbotli zaxiraga o\'tgan'), stat(c.superseded, 'O\'rni bosilgan'), stat(c.replacements_live, 'Almashtirishlar'),
            stat(c.entitlements, 'Jami ruxsatlar'), stat(c.headroom, 'Bo\'sh o\'rin')),
            el('p', { class: 'small', text: c.invariant_ok ? 'Invariant butun: ruxsatlar ≤ sig\'im, bir joyga bitta huquq.' : 'DIQQAT: invariant buzilgan — adminga xabar bering!' }),
            c.capacity_changes.length ? el('p', { class: 'small', text: 'Sig\'im o\'zgarishlari: ' + c.capacity_changes.map(function (x) { return x.at + ' ' + x.old + '→' + x.new + ' (' + x.approval_ref + ')'; }).join('; ') }) : null)));
      }, function () {});
      call('ci_report', { p_name: 'sector_summary' }, 30000).then(function (rows) {
        sect.replaceChildren(el('section', { class: 'card' }, el('h2', { text: 'Sektorlar bo\'yicha' }), el('div', { class: 'tablewrap' }, el('table', {},
          el('tr', {}, ['Sektor', 'Ajratilgan', 'Kirgan', 'Inventar nusxa', 'Dublikat №', 'Ortiqcha', 'Tarqatilgan', 'Noma\'lum'].map(function (h) { return el('th', { text: h }); })),
          rows.map(function (r) { return el('tr', {}, [(r.kind === 'BLITCHER' ? 'Bl ' : '') + r.sector, r.allocated, r.admitted, r.physical_copies, r.duplicate_numbers, r.surplus_copies, r.distributed, r.distribution_unknown].map(function (v) { return el('td', { text: v }); })); })))));
      });
    }
    load();
    var iv = setInterval(function () { if (S.tab === 'dash' && document.body.contains(box)) load(); else clearInterval(iv); }, 15000);
  }

  // ---------------------------------------------------------------- ADMIN
  function adminView(head) {
    var box = el('div');
    var em = el('input', { type: 'email', placeholder: 'xodim email' }), dn = el('input', { placeholder: 'Ismi' });
    var role = el('select', {}, ['GATE', 'INVENTORY', 'SUPERVISOR', 'ADMIN'].map(function (r) { return el('option', { value: r, text: r }); }));
    var file = el('input', { type: 'file', accept: '.csv,text/csv' }), src = el('input', { placeholder: 'Manba (masalan: "Diler jadvali 25.11")' });
    var gid = el('input', { placeholder: 'G5' }), gname = el('input', { placeholder: '5-kirish' });
    var capInfo = el('div');
    var code = el('input', { inputmode: 'numeric', placeholder: '10–12 raqam' });
    var stk = el('input', { inputmode: 'numeric', placeholder: 'Bilet raqami (5 xona)', maxlength: 5 }), stkEv = el('textarea', { placeholder: 'Isbot: tarqatish hujjati (HELD/RETURNED), inventar partiyasi raqami, kim tekshirdi, qayerda saqlanadi' });
    var cdev = el('input', { placeholder: 'Qurilma ID (shu qurilma: ' + S.device + ')', value: '' });
    var sp = { kind: el('select', {}, ['SEKTOR', 'BLITCHER'].map(function (k) { return el('option', { value: k, text: k }); })), zone: el('input', { placeholder: '2-qavat' }),
               sector: el('input', { placeholder: 'B206' }), row: el('input', { type: 'number', placeholder: 'qator' }), seat: el('input', { type: 'number', placeholder: 'joy' }), note: el('input', { placeholder: 'Qanday tekshirildi' }) };
    render(head, box,
      el('section', { class: 'card' }, el('h2', { text: 'Kirish holati' }), el('div', { class: 'row' },
        el('button', { class: 'go', on: { click: function () {
          var t = prompt('HAQIQIY KIRISH OCHILADI (' + CFG.env + '). Shundan keyin skanlar biletlarni kiritadi.\nTasdiqlash uchun aynan yozing: KIRISHNI OCHISH');
          if (t === null) return;
          call('ci_admission_set', { p_open: true, p_confirm: t.trim() }).then(function () { toast('Kirish ochildi'); boot(); }, function (e) { toast(errText(e)); });
        } }, text: 'Kirishni ochish' }),
        el('button', { class: 'stop', on: { click: function () { call('ci_admission_set', { p_open: false, p_confirm: null }).then(function () { toast('Kirish yopildi'); boot(); }, function (e) { toast(errText(e)); }); } }, text: 'Kirishni yopish' })),
        el('div', { class: 'row', style: 'margin-top:8px' },
          el('button', { on: { click: function () { setS('block_held_stock', true); } }, text: 'Zaxiradagi biletni nazoratchiga yuborish: YOQ' }),
          el('button', { on: { click: function () { setS('block_held_stock', false); } }, text: '…: O\'CHIR' })),
        el('h3', { text: 'Tasdiqlangan sig\'im' }), capInfo,
        el('p', { class: 'small muted', text: 'Sig\'im bu yerdan o\'zgartirilmaydi. Almashtirish bileti uchun sig\'im HECH QACHON oshirilmaydi. Faqat tashkilotchining yozma qarori bilan alohida protsedura (hujjat 04, ci_capacity_change).' })),
      el('section', { class: 'card' }, el('h2', { text: 'Xodimlar' }), el('p', { class: 'small muted', text: 'Foydalanuvchini avval Supabase → Authentication da yarating, keyin rolni shu yerda bering.' }),
        em, dn, role, el('div', { class: 'row', style: 'margin-top:8px' },
          el('button', { class: 'primary', on: { click: function () { staff(true); } }, text: 'Saqlash / faollashtirish' }),
          el('button', { class: 'stop', on: { click: function () { staff(false); } }, text: 'O\'chirish' }),
          el('button', { on: { click: function () { if (confirm('Bu xodimning barcha sessiyalari bekor qilinsinmi?')) call('ci_staff_revoke_sessions', { p_username: em.value.trim() }).then(function (r) { toast('Bekor qilindi: ' + r.revoked); }); } }, text: 'Sessiyalarni bekor qilish' })),
        el('div', { id: 'stafflist' })),
      el('section', { class: 'card' }, el('h2', { text: 'Darvozalar' }), el('div', { class: 'row' }, gid, gname, el('button', { on: { click: function () { call('ci_gate_set', { p_gate: gid.value, p_name: gname.value, p_active: true }).then(function () { toast('Saqlandi'); }, function (e) { toast(errText(e)); }); } }, text: 'Saqlash' }))),
      el('section', { class: 'card' }, el('h2', { text: 'Tarqatish yozuvlari importi (CSV)' }),
        el('p', { class: 'small muted', text: 'Ustunlar: ticket_no,status[,recipient_ref,note]. status = DISTRIBUTED | HELD | RETURNED. Bitta noto\'g\'ri qator bo\'lsa — hech narsa yozilmaydi. Taxminiy ma\'lumot kiritmang.' }),
        file, src, el('button', { class: 'primary', style: 'margin-top:8px', on: { click: importCsv }, text: 'Import' })),
      el('section', { class: 'card' }, el('h2', { text: 'Zaxiradagi biletdan zaxira joy (isbot bilan)' }),
        el('p', { class: 'small muted', text: 'Faqat: tarqatish yozuvida HELD/RETURNED, yopilgan inventar partiyasida 1 nusxa, varag\'ida dublikat yo\'q, darvozada ko\'rilmagan bilet. Asl bilet bekor qilinadi, joyi zaxiraga o\'tadi; jami ruxsatlar oshmaydi. Noma\'lum bilet zaxira bo\'lmaydi.' }),
        stk, stkEv, el('button', { class: 'warn', style: 'margin-top:8px', on: { click: function () {
          if (!/^[0-9]{5}$/.test(stk.value.trim())) { toast('5 xonali bilet raqami'); return; }
          if (prompt('Bilet № ' + stk.value + ' BEKOR qilinib, joyi zaxiraga o\'tadi. Tasdiqlash uchun raqamni qayta yozing') !== stk.value.trim()) return;
          call('ci_spare_from_stock', { p_ticket: stk.value.trim(), p_evidence: stkEv.value }).then(function (r) {
            alert('Zaxira joy: ' + r.seat.sector + ' qator ' + r.seat.row_no + ' joy ' + r.seat.seat_no + '\n' + r.notice); stk.value = ''; stkEv.value = '';
          }, function (e) { toast(errText(e)); });
        } }, text: 'Zaxira joyga o\'tkazish' })),
      el('section', { class: 'card' }, el('h2', { text: 'Masterda yo\'q qo\'shimcha joy (EXTRA)' }),
        el('p', { class: 'small muted', text: 'Zalda jismonan mavjud, lekin masterda yo\'q joy. Sig\'imni OSHIRMAYDI — unga almashtirish faqat sig\'imda bo\'sh o\'rin bo\'lsa beriladi.' }),
        el('div', { class: 'row' }, sp.kind, sp.zone, sp.sector), el('div', { class: 'row', style: 'margin-top:6px' }, sp.row, sp.seat), sp.note,
        el('button', { class: 'primary', style: 'margin-top:8px', on: { click: function () {
          call('ci_admin_spare_add', { p_kind: sp.kind.value, p_zone: sp.zone.value, p_sector: sp.sector.value.trim(), p_row: +sp.row.value, p_seat: +sp.seat.value, p_note: sp.note.value })
            .then(function () { toast('Zaxira joy qo\'shildi'); }, function (e) { toast(errText(e)); });
        } }, text: 'Qo\'shish' })),
      el('section', { class: 'card' }, el('h2', { text: 'Nazoratli favqulodda rejim' }),
        el('p', { class: 'small muted', text: 'Darvozalar mustaqil oflayn kirita olmaydi. Faqat bitta belgilangan nazoratchi qurilmasi, kod bilan. Server ishlamasa — darvozalar to\'xtaydi (hujjat 03).' }),
        el('div', { class: 'row' }, code,
        el('button', { on: { click: function () { call('ci_set_contingency_code', { p_code: code.value }, 20000).then(function () { code.value = ''; toast('Kod o\'rnatildi — nazoratchi qurilmasi qayta kirsin'); }, function (e) { toast(errText(e)); }); } }, text: 'Kodni o\'rnatish' })),
        el('div', { class: 'row', style: 'margin-top:6px' }, cdev,
        el('button', { on: { click: function () { var d = cdev.value.trim() || S.device; if (!confirm('Favqulodda qurilma: ' + d + ' ?')) return; call('ci_contingency_device_set', { p_device: d }).then(function () { toast('Belgilandi: ' + d); }, function (e) { toast(errText(e)); }); } }, text: 'Qurilmani belgilash' }),
        el('button', { on: { click: function () { call('ci_contingency_device_set', { p_device: null }).then(function () { toast('Favqulodda qurilma olib tashlandi'); }, function (e) { toast(errText(e)); }); } }, text: 'Olib tashlash' }))),
      el('section', { class: 'card' }, el('h2', { text: 'Audit jurnali' }), el('div', { class: 'row' },
        el('button', { on: { click: function () { call('ci_audit_verify', {}, 30000).then(function (r) { alert(r.ok ? 'Zanjir butun: ' + r.checked + ' yozuv' : 'BUZILISH! Birinchi noto\'g\'ri yozuv #' + r.first_bad_id); }); } }, text: 'Butunligini tekshirish' }),
        el('button', { on: { click: function () { call('ci_audit_tail', { p_limit: 1000 }).then(function (r) { csv(r, 'dusel_audit'); }); } }, text: 'CSV' }))));
    call('ci_capacity_status').then(function (c) { capInfo.replaceChildren(el('p', { text: c.approved_capacity + ' (ruxsatlar ' + c.entitlements + ', bo\'sh ' + c.headroom + ')' })); }, function () {});
    call('ci_dashboard').then(function (d) { box.replaceChildren(el('div', { class: 'result ' + (d.admission_open ? 'ok' : 'bad') }, el('div', { class: 'big', text: d.admission_open ? 'KIRISH OCHIQ' : 'KIRISH YOPIQ' }), el('div', { class: 'small', text: 'Muhit: ' + d.environment })) ); });
    loadStaff();
    function loadStaff() {
      call('ci_staff_list').then(function (l) {
        var h = document.getElementById('stafflist'); if (!h) return;
        h.replaceChildren(el('ul', { class: 'list small' }, l.map(function (s) { return el('li', { text: s.username + ' · ' + s.display_name + ' · ' + s.role + (s.active ? '' : ' · O\'CHIRILGAN') + ' · oxirgi skan ' + (s.last_scan || '—') }); })));
      });
    }
    function staff(active) {
      call('ci_staff_set', { p_email: em.value.trim(), p_display: dn.value.trim() || em.value.trim(), p_role: role.value, p_active: active }).then(function () { toast('Saqlandi'); loadStaff(); }, function (e) { toast(errText(e)); });
    }
    function setS(k, v) { call('ci_setting_set', { p_key: k, p_value: v }).then(function () { toast('Saqlandi'); shell(); }, function (e) { toast(errText(e)); }); }
    function importCsv() {
      var f = file.files[0]; if (!f) { toast('Fayl tanlang'); return; }
      f.text().then(function (t) {
        var lines = t.replace(/^﻿/, '').split(/\r?\n/).filter(function (l) { return l.trim(); });
        var hdr = lines.shift().split(',').map(function (h) { return h.trim().toLowerCase(); });
        var rows = lines.map(function (l) { var c = l.split(','); var o = {}; hdr.forEach(function (h, i) { o[h] = (c[i] || '').trim().replace(/^"|"$/g, ''); }); return o; });
        if (!confirm(rows.length + ' qator import qilinsinmi? Manba: ' + src.value)) return;
        call('ci_import_distribution', { p_rows: rows, p_source: src.value }, 60000).then(function (r) {
          alert(r.imported ? 'Import qilindi: ' + r.imported : (r.message + '\n' + JSON.stringify(r.errors).slice(0, 500)));
        }, function (e) { toast(errText(e)); });
      });
    }
  }

  // ---------------------------------------------------------------- ishga tushirish
  sb.auth.getSession().then(function (r) {
    if (r.data && r.data.session) {
      boot();
      call('ci_contingency', { p_device: S.device }).then(function (c) { LS.set('contingency', c && c.allowed ? c : { allowed: false }); }, function () {});
    } else loginView();
  }, function () { loginView(); });
  sb.auth.onAuthStateChange(function (ev) {
    if (ev === 'SIGNED_IN') call('ci_contingency', { p_device: S.device }).then(function (c) { LS.set('contingency', c && c.allowed ? c : { allowed: false }); }, function () {});
    if (ev === 'SIGNED_OUT' && S.me) { S.me = null; loginView(); }
  });
  // xavfsizlik: 12 soatdan keyin yoki 2 soat harakatsizlikdan keyin avtomatik chiqish
  var lastAct = Date.now(); ['click', 'keydown', 'touchstart'].forEach(function (e) { document.addEventListener(e, function () { lastAct = Date.now(); }, { passive: true }); });
  setInterval(function () { if (S.me && Date.now() - lastAct > 2 * 3600 * 1000 && !S.offlineMode) signOut('SESSION_REVOKED'); }, 60000);
  window.DUSEL_CI_DEBUG = { state: S, syncQueue: syncQueue };
})();
