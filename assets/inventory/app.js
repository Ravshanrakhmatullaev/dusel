/* DUSEL — Jismoniy bilet INVENTARI (faqat xodimlar). KIRISHGA TA'SIR QILMAYDI.
 * - Har bir skan serverda ci_inventory_scan orqali qayd etiladi; baza INVENTORY rejimida bilet holatiga yozishni taqiqlaydi.
 * - Aloqa bo'lmasa skanlar qurilmada (IndexedDB) navbatda saqlanadi va keyin bir xil request_id bilan yuboriladi (takror sanalmaydi).
 * - Kamera, tashqi USB/Bluetooth 2D skaner va qo'lda kiritish.
 */
(function () {
  'use strict';
  var CFG = window.DUSEL_CHECKIN_CONFIG || { disabled: true };
  var $app = document.getElementById('app');
  var LS = {
    get: function (k, d) { try { var v = localStorage.getItem('dusel_inv_' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem('dusel_inv_' + k, JSON.stringify(v)); } catch (e) {} },
    del: function (k) { try { localStorage.removeItem('dusel_inv_' + k); } catch (e) {} }
  };
  function uuid() {
    if (crypto.randomUUID) return crypto.randomUUID();
    var b = crypto.getRandomValues(new Uint8Array(16)); b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
    var x = Array.prototype.map.call(b, function (v) { return (v + 256).toString(16).slice(1); }).join('');
    return x.slice(0, 8) + '-' + x.slice(8, 12) + '-' + x.slice(12, 16) + '-' + x.slice(16, 20) + '-' + x.slice(20);
  }
  function el(tag, attrs) {
    var n = document.createElement(tag), k; attrs = attrs || {};
    for (k in attrs) {
      if (!Object.prototype.hasOwnProperty.call(attrs, k) || attrs[k] == null || attrs[k] === false) continue;
      if (k === 'on') { for (var ev in attrs.on) n.addEventListener(ev, attrs.on[ev]); }
      else if (k === 'class') n.className = attrs[k]; else if (k === 'text') n.textContent = attrs[k];
      else n.setAttribute(k, attrs[k] === true ? '' : attrs[k]);
    }
    for (var i = 2; i < arguments.length; i++) add(n, arguments[i]);
    return n;
  }
  function add(n, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) { c.forEach(function (x) { add(n, x); }); return; }
    n.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
  }
  function render() { var a = Array.prototype.slice.call(arguments); $app.replaceChildren(); a.forEach(function (x) { add($app, x); }); }
  function toast(m) { var t = el('div', { class: 'toast', role: 'status', text: m }); document.body.appendChild(t); setTimeout(function () { t.remove(); }, 2600); }
  var audio;
  function beep(kind) {   // 'ok' | 'dup' | 'bad'
    try {
      if (navigator.vibrate) navigator.vibrate(kind === 'ok' ? 40 : kind === 'dup' ? [300, 100, 300, 100, 300] : [200, 80, 200]);
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      var o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = kind === 'ok' ? 1320 : kind === 'dup' ? 330 : 220; g.gain.value = 0.15; o.connect(g); g.connect(audio.destination);
      o.start(); o.stop(audio.currentTime + (kind === 'ok' ? 0.06 : 0.5));
    } catch (e) {}
  }

  if (!CFG.disabled && CFG.apps && CFG.apps.indexOf('inventory') < 0) { render(el('section', { class: 'card center' }, el('h1', { text: 'Bu manzilda inventar o\'chirilgan' }))); return; }
  if (CFG.disabled) {
    render(el('section', { class: 'card center' }, el('h1', { text: 'Inventar faollashtirilmagan' }),
      el('p', { class: 'muted', text: 'Bu muhit (' + (CFG.env || '?') + ') uchun server sozlamasi yo\'q.' })));
    return;
  }
  var sb = window.supabase.createClient(CFG.url, CFG.key, { auth: { persistSession: true, autoRefreshToken: true, storageKey: 'dusel_inv_auth_' + CFG.env, detectSessionInUrl: false } });
  var ERR = { NOT_YOUR_SCAN: 'Bu skan boshqa xodimniki — nazoratchi qaror beradi', ALREADY_DECIDED: 'Qaror allaqachon berilgan — o\'zgartirish faqat nazoratchi orqali',
              NOTE_REQUIRED: 'Ikkinchi qog\'oz qayerga qo\'yilganini yozing', NOT_A_REPEAT: 'Bu birinchi skan — qaror kerak emas', AUTH_DENIED: 'Siz xodimlar ro\'yxatida yo\'qsiz', SESSION_REVOKED: 'Sessiya tugagan — qayta kiring', ROLE_DENIED: 'Bu ilova faqat inventar xodimlari uchun',
              RATE_LIMIT: 'Juda tez — bir necha soniya kuting', BATCH_NOT_OPEN: 'Partiya yopiq', NAME_REQUIRED: 'Partiya nomini yozing' };
  function errText(e) { if (!e) return 'Xato'; if (e.network) return 'Server bilan aloqa yo\'q'; var m = (e.message || '').split('\n')[0]; return ERR[m] || e.hint || m || 'Xato'; }
  function call(fn, args, ms) {
    return new Promise(function (res, rej) {
      var done = false, tm = setTimeout(function () { if (!done) { done = true; setOnline(false); rej({ network: true, timeout: true }); } }, ms || 9000);
      sb.rpc(fn, args || {}).then(function (r) {
        if (done) return; done = true; clearTimeout(tm);
        if (r.error) {
          var code = (r.error.message || '').split('\n')[0];
          if (code === 'SESSION_REVOKED' || code === 'AUTH_DENIED' || r.status === 401) signOut(code);
          if (!r.error.code && /fetch|network/i.test(r.error.message || '')) { setOnline(false); rej({ network: true }); } else rej(r.error);
        } else { setOnline(true); res(r.data); }
      }, function (e) { if (done) return; done = true; clearTimeout(tm); setOnline(false); rej({ network: true, err: e }); });
    });
  }
  var S = { me: null, device: LS.get('device', null), batch: LS.get('batch', null), tab: 'scan', online: navigator.onLine, queue: [], recent: [], local: {}, stats: { ok: 0, dup: 0, bad: 0, rep: 0 }, pendingN: 0 };
  if (!S.device) { S.device = 'inv-' + uuid().slice(0, 8); LS.set('device', S.device); }
  function setOnline(v) {
    S.online = v; var n = document.getElementById('net');
    if (v) { n.hidden = true; pump(); } else { n.hidden = false; n.textContent = 'ALOQA YO\'Q — skanlar qurilmada saqlanmoqda (' + S.queue.length + ')'; }
    updQueue();
  }
  window.addEventListener('online', function () { setOnline(true); });
  window.addEventListener('offline', function () { setOnline(false); });
  (function () { var b = document.getElementById('env'); b.hidden = false; b.className = 'env inv' + (CFG.env === 'PRODUCTION' ? ' prod' : '');
    b.textContent = 'INVENTAR — kirishga ta\'sir qilmaydi · ' + (CFG.env === 'PRODUCTION' ? 'PRODUCTION' : CFG.env + ' (sinov)'); })();

  // ---------------------------------------------------------------- qurilmadagi navbat (IndexedDB, bo'lmasa localStorage)
  var DB = (function () {
    var dbp = null;
    function open() {
      if (dbp) return dbp;
      dbp = new Promise(function (res) {
        if (!window.indexedDB) return res(null);
        var r = indexedDB.open('dusel_inventory_' + CFG.env, 1);
        r.onupgradeneeded = function () { r.result.createObjectStore('queue', { keyPath: 'request_id' }); };
        r.onsuccess = function () { res(r.result); }; r.onerror = function () { res(null); };
      });
      return dbp;
    }
    function tx(mode, fn) { return open().then(function (db) { if (!db) return null; return new Promise(function (res) { var t = db.transaction('queue', mode); var out = fn(t.objectStore('queue')); t.oncomplete = function () { res(out && out.result); }; t.onerror = function () { res(null); }; }); }); }
    return {
      all: function () { return open().then(function (db) { if (!db) return LS.get('queue', []); return new Promise(function (res) { var q = db.transaction('queue').objectStore('queue').getAll(); q.onsuccess = function () { res((q.result || []).sort(function (a, b) { return a.seq - b.seq; })); }; q.onerror = function () { res([]); }; }); }); },
      put: function (it) { return tx('readwrite', function (s) { return s.put(it); }).then(function (r) { if (r === null) LS.set('queue', S.queue); }); },
      del: function (id) { return tx('readwrite', function (s) { return s.delete(id); }).then(function (r) { if (r === null) LS.set('queue', S.queue); }); }
    };
  })();
  var seq = Date.now();
  function enqueue(payload, source, note) {
    if (!S.batch) { toast('Avval partiyani tanlang'); beep('bad'); return; }
    var it = { request_id: uuid(), seq: seq++, batch: +S.batch, payload: payload, source: source, note: note || null, client_at: new Date().toISOString(), tries: 0 };
    S.queue.push(it); DB.put(it);
    // qurilmadagi tezkor ko'rsatkich (server javobidan oldin): shu partiyada shu raqam necha marta
    var key = it.batch + '|' + payload; S.local[key] = (S.local[key] || 0) + 1;
    showPending(it, S.local[key]);
    updQueue(); pump();
  }
  var pumping = false;
  function pump() {
    if (pumping || !S.queue.length || !S.me) return; pumping = true;
    (function next() {
      if (!S.queue.length) { pumping = false; updQueue(); return; }
      var it = S.queue[0];
      call('ci_inventory_scan', { p_request: it.request_id, p_batch: it.batch, p_payload: it.payload, p_seat_note: it.note, p_source: it.source, p_device: S.device, p_client_at: it.client_at })
        .then(function (r) { S.queue.shift(); DB.del(it.request_id); showResult(it, r); updQueue(); next(); },
              function (e) {
                if (e.network) { pumping = false; updQueue(); setTimeout(pump, 3000); return; }       // keyinroq aynan shu request_id bilan
                S.queue.shift(); DB.del(it.request_id); showFailed(it, e); updQueue(); next();
              });
    })();
  }
  function updQueue() { var q = document.getElementById('qcount'); if (q) q.textContent = S.queue.length ? 'Yuborilmagan: ' + S.queue.length + (S.online ? ' (yuborilmoqda…)' : ' (aloqa yo\'q — saqlangan)') : 'Hammasi serverga yuborilgan'; }

  // ---------------------------------------------------------------- kirish / chiqish
  function signOut(reason) {
    window.DuselScanner.unmount(); sb.auth.signOut().catch(function () {});
    try { localStorage.removeItem('dusel_inv_auth_' + CFG.env); } catch (e) {}
    S.me = null; loginView(reason ? (ERR[reason] || reason) : null);
  }
  function loginView(msg) {
    var email = el('input', { type: 'email', autocomplete: 'username', placeholder: 'login@dusel', required: true }), pass = el('input', { type: 'password', autocomplete: 'current-password', required: true });
    var err = el('p', { class: 'small', style: 'color:#ff8a8a', text: msg || '' }), btn = el('button', { class: 'primary big', type: 'submit', text: 'Kirish' });
    render(el('section', { class: 'card' }, el('h1', { text: 'DUSEL · Bilet inventari' }),
      el('p', { class: 'muted small', text: 'Qolgan qog\'oz biletlarni sanash. Bu ilova hech kimni kiritmaydi va biletni ishlatmaydi.' }),
      el('form', { on: { submit: function (e) {
        e.preventDefault(); btn.disabled = true; err.textContent = '';
        sb.auth.signInWithPassword({ email: email.value.trim(), password: pass.value }).then(function (r) {
          btn.disabled = false; if (r.error) { err.textContent = 'Login yoki parol noto\'g\'ri'; return; } pass.value = ''; boot();
        }, function () { btn.disabled = false; err.textContent = 'Server bilan aloqa yo\'q'; });
      } } }, el('label', { text: 'Login (email)' }), email, el('label', { text: 'Parol' }), pass, el('div', { style: 'height:12px' }), btn, err)));
  }
  function boot() {
    call('ci_me').then(function (me) {
      var se = String(me.environment == null ? '' : me.environment).replace(/"/g, '');
      if (CFG.expectServerEnv && se !== CFG.expectServerEnv) {
        return render(el('section', { class: 'card' }, el('div', { class: 'result bad' }, el('div', { class: 'big', text: 'MUHIT MOS EMAS — ISHLATMANG' }),
          el('p', { text: 'Sayt: ' + CFG.env + ', baza: ' + (se || '?') + '. Adminga xabar bering.' })), el('button', { class: 'stop', on: { click: function () { signOut(); } }, text: 'Chiqish' })));
      }
      if (['INVENTORY', 'SUPERVISOR', 'ADMIN'].indexOf(me.role) < 0) {
        return render(el('section', { class: 'card' }, el('h1', { text: 'Ruxsat yo\'q' }), el('p', { text: 'Bu ilova faqat inventar xodimlari uchun. Darvoza xodimlari /checkin dan foydalanadi.' }),
          el('button', { class: 'stop', on: { click: function () { signOut(); } }, text: 'Chiqish' })));
      }
      S.me = me; shell(); pump();
    }, function (e) { if (e.network) { if (S.me) shell(); else loginView('Server bilan aloqa yo\'q'); } else signOut((e.message || '').split('\n')[0]); });
  }

  // ---------------------------------------------------------------- qobiq
  function shell() {
    var tabs = [['scan', 'Skanerlash'], ['pending', 'Qarorlar' + (S.pendingN ? ' (' + S.pendingN + ')' : '')], ['batches', 'Partiyalar'], ['report', 'Solishtiruv']];
    var bar = document.querySelector('.tabs'); if (!bar) { bar = el('nav', { class: 'tabs' }); document.body.appendChild(bar); }
    bar.replaceChildren(); tabs.forEach(function (t) { bar.appendChild(el('button', { class: S.tab === t[0] ? 'on' : '', on: { click: function () { S.tab = t[0]; shell(); } }, text: t[1] })); });
    var head = el('div', { class: 'top' }, el('div', {}, el('b', { text: S.me.display_name }), ' ', el('span', { class: 'pill', text: S.me.role }), ' ', el('span', { class: 'pill', text: 'INVENTAR' })),
      el('button', { class: 'small', on: { click: function () { signOut(); } }, text: 'Chiqish' }));
    window.DuselScanner.unmount();
    ({ scan: scanView, pending: pendingView, batches: batchesView, report: reportView }[S.tab] || scanView)(head);
  }

  // ---------------------------------------------------------------- skanerlash
  var $out, $feed;
  function scanView(head) {
    var cam = el('div'); $out = el('div'); $feed = el('ul', { class: 'list' });
    var manual = el('input', { placeholder: 'Raqam yoki QR matni (skaner shu yerga ham yozadi)', autocomplete: 'off', maxlength: 300 });
    var note = el('input', { placeholder: 'Qog\'ozdagi joy QR\'dan farq qilsa yozing (keyingi skanga)', maxlength: 80 });
    var bsel = el('div', { class: 'small', text: S.batch ? 'Partiya #' + S.batch : 'Partiya tanlanmagan' });
    render(head,
      el('section', { class: 'card' }, el('div', { class: 'row', style: 'justify-content:space-between;align-items:center' }, bsel,
        el('button', { class: 'small', on: { click: function () { S.tab = 'batches'; shell(); } }, text: 'Partiyani almashtirish' })),
        el('div', { class: 'stats', style: 'margin-top:8px' }, el('div', { class: 'stat' }, el('b', { id: 'st_ok', text: S.stats.ok }), el('span', { text: 'Qayd etildi (sessiya)' })),
          el('div', { class: 'stat' }, el('b', { id: 'st_rep', text: S.stats.rep || 0 }), el('span', { text: 'Takror (qaror kerak)' })),
          el('div', { class: 'stat' }, el('b', { id: 'st_dup', text: S.stats.dup }), el('span', { text: 'Tasdiqlangan 2-qog\'oz' })),
          el('div', { class: 'stat' }, el('b', { id: 'st_bad', text: S.stats.bad }), el('span', { text: 'Noto\'g\'ri QR' })),
          el('div', { class: 'stat' }, el('b', { id: 'qcount', class: 'small', text: '' }), el('span', { text: 'Navbat' })))),
      $out, cam,
      el('section', { class: 'card' },
        el('form', { class: 'row', on: { submit: function (e) { e.preventDefault(); var v = window.DuselScanner.normalize(manual.value); if (v) { enqueue(v, /^\d{1,5}$/.test(v) ? 'MANUAL' : 'SCANNER', takeNote()); manual.value = ''; } } } },
          manual, el('button', { class: 'primary', type: 'submit', style: 'flex:0 0 auto', text: 'Qayd' })),
        el('label', { text: 'Joy izohi' }), note,
        el('p', { class: 'small', id: 'camstatus' }),
        el('p', { class: 'muted small', text: 'Tashqi 2D skaner: maydonni bo\'sh qoldirib ketma-ket skanerlang (Enter avtomatik). Bir qog\'ozni kamera oldida ushlab tursangiz — bir marta sanaladi.' })),
      el('section', { class: 'card' }, el('h3', { text: 'So\'nggi skanlar' }), $feed));
    S.recent.slice(0, 40).forEach(function (li) { $feed.appendChild(li); });
    function takeNote() { var n = note.value.trim(); note.value = ''; return n || null; }
    updQueue();
    if (!S.batch) $out.replaceChildren(el('div', { class: 'result warn' }, el('div', { class: 'big', text: 'Avval partiya oching yoki tanlang' })));
    window.DuselScanner.mount(cam, function (v, src) { enqueue(v, src, takeNote()); }, { status: document.getElementById('camstatus') });
  }
  function short(p) { var m = /code=(\d{1,6})/.exec(p); return m ? m[1] : (p.length > 40 ? p.slice(0, 40) + '…' : p); }
  function showPending(it, localCount) {
    if (!$out || !document.body.contains($out)) return;
    $out.replaceChildren(el('div', { class: 'result info' }, el('div', { class: 'big', text: (S.online ? 'Yuborilmoqda… ' : 'Saqlandi (oflayn) ') + short(it.payload) }),
      localCount > 1 ? el('p', { style: 'font-weight:800', text: 'Bu qurilmada shu partiyada ' + localCount + '-marta (server tasdiqlaydi)' }) : null));
    if (localCount > 1) beep('dup');
  }
  function feedItem(text, cls) { var li = el('li', { class: cls || '', text: text }); S.recent.unshift(li); S.recent = S.recent.slice(0, 60); if ($feed && document.body.contains($feed)) { $feed.prepend(li); while ($feed.children.length > 40) $feed.lastChild.remove(); } }
  function setStat(k) { S.stats[k]++; var n = document.getElementById('st_' + k); if (n) n.textContent = S.stats[k]; }
  function showResult(it, r) {
    var vis = $out && document.body.contains($out);
    if (r.result !== 'RECORDED') {
      setStat('bad'); beep('bad');
      feedItem('✕ ' + short(it.payload) + ' — ' + (r.message || r.result), 'bad');
      if (vis) $out.replaceChildren(el('div', { class: 'result bad' }, el('div', { class: 'big', text: r.result === 'FOREIGN' ? 'KUPON/VAUCHER — BILET EMAS' : 'NOTO\'G\'RI / NOMA\'LUM QR' }), el('p', { text: r.message || '' }), el('p', { class: 'small', text: 'Alohida qayd etildi (rad etilgan skanlar).' })));
      return;
    }
    var c = r.credential, dup = r.confirmed_copies > 1;
    if (r.needs_verdict) { if (!r.replay) { setStat('rep'); beep('dup'); } feedItem(c.ticket_no + ' · TAKROR (' + r.observation_no + '-kuzatuv) — qaror kerak', 'bad');
      S.pendingN = (S.pendingN || 0) + (r.replay ? 0 : 1); if (vis) askVerdict(r); return; }
    if (dup) setStat('dup'); else setStat('ok');
    if (!r.replay) beep(dup ? 'dup' : 'ok');
    feedItem(c.ticket_no + ' · ' + (c.kind === 'BLITCHER' ? 'Bl ' : '') + c.sector + ' q' + c.row + ' j' + c.seat + ' · varaq ' + (r.print_sheet || '—') + ' · nusxa ' + r.copies_total + (r.replay ? ' (qayta yuborildi)' : ''), dup ? 'bad' : '');
    if (!vis) return;
    $out.replaceChildren(el('div', { class: 'result ' + (dup ? 'bad' : (r.warnings.length ? 'warn' : 'ok')) },
      el('div', { class: 'big', text: dup ? 'TASDIQLANGAN DUBLIKAT № ' + c.ticket_no + ' (' + r.confirmed_copies + ' qog\'oz)' : 'Qayd etildi № ' + c.ticket_no }),
      el('div', { class: 'seat' }, el('div', {}, el('span', { text: 'Bilet' }), el('b', { text: c.ticket_no })), el('div', {}, el('span', { text: c.kind === 'BLITCHER' ? 'Blitcher' : 'Sektor' }), el('b', { text: c.sector })),
        el('div', {}, el('span', { text: 'Qator' }), el('b', { text: c.row })), el('div', {}, el('span', { text: 'Joy' }), el('b', { text: c.seat }))),
      el('div', { class: 'small', text: 'Bosma varaq ' + (r.print_sheet || '—') + ' · tasdiqlangan qog\'oz ' + r.confirmed_copies + (r.pending_repeats ? ' · qarorsiz takror ' + r.pending_repeats : '') + ' · kirish holati o\'zgarmadi' }),
      r.warnings.length ? el('ul', { class: 'warns' }, r.warnings.map(function (w) { return el('li', { text: '⚠ ' + w.text }); })) : null));
  }
  // ---------------------------------------------------------------- takror: o'sha qog'ozmi yoki ikkinchi qog'ozmi? (operator qarori, tarix saqlanadi)
  function verdictButtons(scanId, ticket, done) {
    var B = 'width:100%;font-size:18px;padding:14px;text-align:left';
    return el('div', { style: 'display:flex;flex-direction:column;gap:8px;margin-top:10px' },
      el('button', { style: B, on: { click: function () { decide(scanId, 'SAME_PAPER', null, ticket, done); } }, text: 'YO\'Q — o\'sha qog\'ozni qayta skanerladim' }),
      el('button', { class: 'stop', style: B, on: { click: function () {
        var where = prompt('Ikkinchi qog\'oz № ' + ticket + ' — uni "DUBLIKAT" konvertiga soling va konvert raqamini yozing (masalan: D-3)');
        if (where && where.trim()) decide(scanId, 'SECOND_COPY', where.trim(), ticket, done);
      } }, text: 'HA — qo\'limda IKKINCHI qog\'oz bor' }),
      el('button', { style: 'width:100%', on: { click: function () { if (done) done(); else $out.replaceChildren(); } }, text: 'Keyinroq ("Qarorlar" bo\'limida qoladi)' }));
  }
  function askVerdict(r) {
    var c = r.credential;
    $out.replaceChildren(el('div', { class: 'result warn', role: 'alert' },
      el('div', { class: 'big', text: 'TAKROR SKAN № ' + c.ticket_no }),
      el('p', { style: 'font-weight:800', text: 'Bu raqam avval ham skanerlangan (' + r.observation_no + '-kuzatuv). Qo\'lingizda IKKI xil qog\'oz bormi?' }),
      el('p', { class: 'small', text: c.sector + ' · qator ' + c.row + ' · joy ' + c.seat + ' · varaq ' + (r.print_sheet || '—') + '. Qaror berilmaguncha bu skan nusxa hisoblanmaydi.' }),
      verdictButtons(r.scan_id, c.ticket_no)));
  }
  function decide(scanId, verdict, note, ticket, done) {
    call('ci_inventory_verdict', { p_scan: scanId, p_verdict: verdict, p_note: note }).then(function (v) {
      S.pendingN = Math.max(0, (S.pendingN || 0) - 1);
      if (verdict === 'SECOND_COPY') { setStat('dup'); beep('dup'); } else beep('ok');
      feedItem(ticket + ' · ' + (verdict === 'SECOND_COPY' ? 'IKKINCHI QOG\'OZ tasdiqlandi (' + note + ')' : 'o\'sha qog\'oz — nusxa emas'), verdict === 'SECOND_COPY' ? 'bad' : '');
      if (done) return done();
      if ($out && document.body.contains($out)) $out.replaceChildren(el('div', { class: 'result ' + (verdict === 'SECOND_COPY' ? 'bad' : 'ok') },
        el('div', { class: 'big', text: verdict === 'SECOND_COPY' ? 'TASDIQLANGAN DUBLIKAT № ' + ticket : 'Qayta skan — nusxa hisoblanmadi' }),
        el('p', { class: 'small', text: 'Tasdiqlangan qog\'ozlar: ' + v.confirmed_copies + (verdict === 'SECOND_COPY' ? ' · nazoratchiga belgi yuborildi · bilet bekor qilinmaydi' : '') })));
    }, function (e) { toast(errText(e)); });
  }
  function pendingView(head) {
    var list = el('div');
    render(head, el('section', { class: 'card' }, el('h2', { text: 'Qaror kutilayotgan takror skanlar' }),
      el('p', { class: 'small muted', text: 'Har bir takror uchun: qog\'ozlarni yonma-yon qo\'yib tekshiring. Ikkinchi qog\'oz bo\'lsa — "DUBLIKAT" konvertiga soling. Skan tarixi hech qachon o\'chmaydi.' })), list);
    function load() {
      call('ci_inventory_pending', { p_batch: null }).then(function (ps) {
        S.pendingN = ps.filter(function (p) { return p.mine; }).length;
        list.replaceChildren(el('section', { class: 'card' }, el('ul', { class: 'list' }, ps.length ? ps.map(function (p) {
          return el('li', {}, el('b', { text: '№ ' + p.ticket_no + ' · ' + p.sector + ' q' + p.row + ' j' + p.seat + ' · varaq ' + (p.print_sheet || '—') }),
            el('div', { class: 'small muted', text: p.observation_no + '-kuzatuv · partiya #' + p.batch + ' ' + p.batch_name + ' · ' + p.at + ' · ' + p.operator + ' (birinchi skan: partiya #' + p.first_batch + ')' }),
            (p.mine || S.me.role !== 'INVENTORY') ? verdictButtons(p.scan_id, p.ticket_no, load) : el('div', { class: 'small', text: 'Boshqa xodimning skani — o\'sha xodim yoki nazoratchi qaror beradi' }));
        }) : el('li', { class: 'muted', text: 'Qaror kutilayotgan takror yo\'q' }))));
      }, function (e) { list.replaceChildren(el('div', { class: 'result bad', text: errText(e) })); });
    }
    load();
  }
  function showFailed(it, e) {
    setStat('bad'); beep('bad'); feedItem('✕ ' + short(it.payload) + ' — ' + errText(e), 'bad');
    if ($out && document.body.contains($out)) $out.replaceChildren(el('div', { class: 'result bad' }, el('div', { class: 'big', text: 'QAYD ETILMADI' }), el('p', { text: errText(e) })));
  }

  // ---------------------------------------------------------------- partiyalar
  function batchesView(head) {
    var list = el('div');
    var f = { name: el('input', { placeholder: 'Nomi: masalan "A403 qoldiq, 1-quti"' }), sector: el('input', { placeholder: 'Sektor (A403)', maxlength: 8 }),
              box: el('input', { placeholder: 'Quti' }), stack: el('input', { placeholder: 'Dasta' }), loc: el('input', { placeholder: 'Joylashuv (ombor/stol)' }) };
    render(head, el('section', { class: 'card' }, el('h2', { text: 'Yangi partiya' }), f.name, el('div', { class: 'row', style: 'margin-top:6px' }, f.sector, f.box, f.stack), f.loc,
      el('button', { class: 'primary', style: 'margin-top:8px', on: { click: function () {
        call('ci_inventory_batch_open', { p_name: f.name.value, p_location: f.loc.value, p_sector: f.sector.value, p_box: f.box.value, p_stack: f.stack.value, p_device: S.device })
          .then(function (b) { S.batch = b.id; LS.set('batch', b.id); S.tab = 'scan'; shell(); }, function (e) { toast(errText(e)); });
      } }, text: 'Ochish va skanerlashni boshlash' })), list);
    call('ci_inventory_batches').then(function (bs) {
      list.replaceChildren(el('section', { class: 'card' }, el('h2', { text: 'Partiyalar' }), el('ul', { class: 'list' }, bs.length ? bs.map(function (b) {
        return el('li', {}, el('b', { text: '#' + b.id + ' ' + b.name }), ' ', el('span', { class: 'pill', text: b.open ? 'OCHIQ' : 'YOPIQ' }),
          el('div', { class: 'small muted', text: [b.sector, b.box && 'quti ' + b.box, b.stack && 'dasta ' + b.stack, b.location, b.operator, b.created_at].filter(Boolean).join(' · ') + ' · ' + b.scans + ' skan' + (b.rejected ? ' · ' + b.rejected + ' rad' : '') }),
          b.open ? el('div', { class: 'row', style: 'margin-top:6px' },
            el('button', { class: 'small primary', on: { click: function () { S.batch = b.id; LS.set('batch', b.id); S.tab = 'scan'; shell(); } }, text: 'Tanlash' }),
            (b.mine || S.me.role !== 'INVENTORY') ? el('button', { class: 'small', on: { click: function () {
              if (S.queue.some(function (q) { return q.batch === b.id; })) { toast('Avval yuborilmagan skanlar yuborilsin'); return; }
              if (confirm('Partiya #' + b.id + ' yopilsinmi? Yopilgandan keyin unga skan qo\'shilmaydi.')) call('ci_inventory_batch_close', { p_batch: b.id }).then(function () { if (String(S.batch) === String(b.id)) { S.batch = null; LS.del('batch'); } shell(); }, function (e) { toast(errText(e)); });
            } }, text: 'Yopish' }) : null) : null);
      }) : el('li', { class: 'muted', text: 'Partiya yo\'q' }))));
    }, function (e) { list.replaceChildren(el('div', { class: 'result bad', text: errText(e) })); });
  }

  // ---------------------------------------------------------------- solishtiruv (sektorlar, varaqlar, eksport)
  var CAT = { admitted: 'Kirgan', distributed_confirmed: 'Tarqatilgan (hujjat)', in_stock_confirmed: 'Zaxirada (hujjat+skan)', in_stock_no_record: 'Skanlangan, hujjat yo\'q',
              conflict_distributed_in_stock: 'Ziddiyat: tarqatilgan, lekin qo\'lda', held_but_not_found: 'Zaxirada (hujjat), topilmadi', retired_to_spare: 'Zaxira joyga o\'tgan', cancelled: 'Bekor', unknown: 'Noma\'lum (ko\'rilmagan, hujjat yo\'q)' };
  var SHEET = { REPRINTED_SUSPECTED: ['bad', 'Ikkinchi qog\'oz tasdiqlangan (varaq qayta bosilgan bo\'lishi mumkin)'], REPEAT_UNVERIFIED: ['warn', 'Takror skan — qaror kutilmoqda'], FULL_SHEET_IN_STOCK: ['ok', 'To\'liq qo\'lda'], PARTIAL_SHEET_IN_STOCK: ['warn', 'Qisman qo\'lda'],
                SHEET_ACCOUNTED_OUTSIDE: ['info', 'Tarqatilgan/kirgan'], SHEET_NOT_FOUND_NO_RECORD: ['', 'Ko\'rilmagan, hujjat yo\'q'], SHEET_NOT_FOUND_PARTIAL_RECORD: ['', 'Ko\'rilmagan, qisman hujjat'] };
  function csv(rows, name) {
    if (!rows || !rows.length) { toast('Ma\'lumot yo\'q'); return; }
    var keys = Object.keys(rows[0]);
    var esc = function (v) { v = v == null ? '' : (typeof v === 'object' ? JSON.stringify(v) : String(v)); if (/^[=+\-@]/.test(v)) v = "'" + v; return '"' + v.replace(/"/g, '""') + '"'; };
    var text = '﻿' + keys.join(';') + '\r\n' + rows.map(function (r) { return keys.map(function (k) { return esc(r[k]); }).join(';'); }).join('\r\n');
    var a = el('a', { href: URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' })), download: name + '.csv' }); document.body.appendChild(a); a.click(); a.remove();
  }
  function reportView(head) {
    var top = el('div'), detail = el('div');
    render(head, el('section', { class: 'card' }, el('h2', { text: 'Fizik bilet solishtiruvi' }),
      el('p', { class: 'small muted', text: '"Ko\'rilmagan" ≠ "bosilmagan" ≠ "tarqatilgan". Noma\'lum biletlar sotilmagan deb hisoblanmaydi va zaxira joy bo\'lmaydi. Ikki marta bosilgan varaq — taxmin: 6 ta nusxaning hammasi mavjudligini anglatmaydi.' })), top, detail);
    call('ci_reconciliation', { p_sector: null }, 30000).then(function (rows) {
      rows.sort(function (a, b) { return (a.sector === 'A403' ? -1 : 0) - (b.sector === 'A403' ? -1 : 0) || (a.kind + a.sector).localeCompare(b.kind + b.sector); });
      var tot = rows.reduce(function (t, r) { Object.keys(CAT).concat(['allocated', 'physical_copies_scanned', 'duplicate_numbers', 'surplus_copies']).forEach(function (k) { t[k] = (t[k] || 0) + (+r[k] || 0); }); return t; }, {});
      top.replaceChildren(el('section', { class: 'card' }, el('h3', { text: 'Jami (barcha sektorlar)' }), el('div', { class: 'stats' },
          [['allocated', 'Ajratilgan'], ['physical_copies_scanned', 'Skanlangan nusxa'], ['duplicate_numbers', 'Dublikat raqam'], ['surplus_copies', 'Ortiqcha nusxa'],
           ['in_stock_confirmed', CAT.in_stock_confirmed], ['in_stock_no_record', CAT.in_stock_no_record], ['distributed_confirmed', CAT.distributed_confirmed], ['unknown', CAT.unknown]]
            .map(function (k) { return el('div', { class: 'stat' }, el('b', { text: tot[k[0]] }), el('span', { text: k[1] })); })),
        el('div', { class: 'row', style: 'margin-top:10px' },
          el('button', { class: 'small', on: { click: function () { csv(rows.map(function (r) { var o = Object.assign({}, r); o.sheets_by_status = JSON.stringify(r.sheets_by_status); o.reprinted_sheets = (r.reprinted_sheets || []).join(' '); o.sheets_not_found_no_record = (r.sheets_not_found_no_record || []).join(' '); return o; }), 'dusel_solishtiruv_sektorlar'); } }, text: 'Sektorlar CSV' }),
          [['observed', 'Ko\'rilganlar'], ['not_observed', 'Ko\'rilmaganlar'], ['duplicates', 'Dublikatlar'], ['rejected_scans', 'Rad etilgan skanlar'], ['scans', 'Barcha skanlar']].map(function (x) {
            return el('button', { class: 'small', on: { click: function () { call('ci_inventory_report', { p_name: x[0], p_sector: null }, 60000).then(function (r) { csv(r, 'dusel_inventar_' + x[0]); }, function (e) { toast(errText(e)); }); } }, text: x[1] + ' CSV' });
          })),
        el('div', { class: 'tablewrap', style: 'margin-top:10px' }, el('table', {},
          el('tr', {}, ['Sektor', 'Ajrat.', 'Tasdiq. qog\'oz', 'Dubl. №', 'Ortiqcha', 'Qarorsiz takror', 'Zaxira (hujjat)', 'Hujjatsiz skan', 'Tarqat.', 'Kirgan', 'Noma\'lum', 'Shubhali varaq'].map(function (x) { return el('th', { text: x }); })),
          rows.map(function (r) {
            return el('tr', { class: r.sector === 'A403' ? 'hl' : '', style: 'cursor:pointer', on: { click: function () { sheets(r, detail); } } },
              [(r.kind === 'BLITCHER' ? 'Bl ' : '') + r.sector, r.allocated, r.physical_copies_scanned, r.duplicate_numbers, r.surplus_copies, r.pending_repeats, r.in_stock_confirmed, r.in_stock_no_record,
               r.distributed_confirmed, r.admitted, r.unknown, (r.reprinted_sheets || []).length].map(function (v) { return el('td', { text: v }); }));
          })))));
      var a403 = rows.filter(function (r) { return r.sector === 'A403'; })[0]; if (a403) sheets(a403, detail);
    }, function (e) { top.replaceChildren(el('div', { class: 'result bad', text: errText(e) })); });
  }
  function sheets(r, box) {
    call('ci_reconciliation_sheets', { p_sector: r.sector }, 30000).then(function (sh) {
      box.replaceChildren(el('section', { class: 'card' }, el('h2', { text: 'Sektor ' + r.sector + ' — ' + r.allocated + ' bilet, ' + r.first_ticket + '–' + r.last_ticket + ', varaqlar ' + r.first_sheet + '–' + r.last_sheet + ' (' + r.sheets + ')' }),
        el('div', { class: 'stats' }, Object.keys(CAT).map(function (k) { return el('div', { class: 'stat' }, el('b', { text: r[k] }), el('span', { text: CAT[k] })); })),
        el('h3', { text: 'Bosma varaqlar (6 bilet/varaq)' }),
        el('div', { class: 'sheets' }, sh.map(function (s) {
          var m = SHEET[s.status] || ['', s.status];
          return el('div', { class: 'sheet ' + m[0], title: m[1] }, el('b', { text: s.sheet }), el('span', { text: s.in_stock + '/' + s.tickets.length + (s.max_copies > 1 ? ' ×' + s.max_copies : '') }),
            el('small', { text: s.tickets.map(function (t) { return t.ticket_no.slice(-3) + (t.copies > 1 ? '×' + t.copies : t.pending ? '?' : t.copies ? '✓' : '·'); }).join(' ') }));
        })),
        el('p', { class: 'small muted', text: Object.keys(SHEET).map(function (k) { return SHEET[k][1]; }).join(' · ') }),
        el('button', { class: 'small', on: { click: function () {
          var flat = []; sh.forEach(function (s) { s.tickets.forEach(function (t) { flat.push({ varaq: s.sheet, varaq_holati: s.status, bilet: t.ticket_no, sektor: t.sector, qator: t.row, joy: t.seat, orin: t.slot, nusxa: t.copies, tarqatish: t.distribution, toifa: t.category }); }); });
          csv(flat, 'dusel_varaqlar_' + r.sector);
        } }, text: 'Varaqlar CSV' })));
    }, function (e) { toast(errText(e)); });
  }

  // ---------------------------------------------------------------- ishga tushirish
  DB.all().then(function (q) { S.queue = q || []; updQueue(); });
  sb.auth.getSession().then(function (r) { if (r.data && r.data.session) boot(); else loginView(); }, function () { loginView(); });
  sb.auth.onAuthStateChange(function (ev) { if (ev === 'SIGNED_OUT' && S.me) { S.me = null; loginView(); } });
  window.DUSEL_INV_DEBUG = { state: S, pump: pump };
})();
