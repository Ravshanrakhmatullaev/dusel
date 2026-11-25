/* DUSEL — umumiy QR skaner moduli (/checkin va /inventory).
 * 1) Telefon kamerasi: BarcodeDetector yoki jsQR. Ruxsat berilmasa — platformaga mos yo'riqnoma va tiklash tugmalari.
 * 2) Tashqi 2D skaner (USB/Bluetooth, "klaviatura" rejimi): tez kelgan belgilar + Enter = bitta skan.
 *    Klaviatura kirill (ЙЦУКЕН) tartibida bo'lsa ham URL avtomatik tiklanadi.
 * 3) Qo'lda kiritish — har doim mavjud.
 * Modul hech qanday qaror qabul qilmaydi: faqat matnni ilovaga uzatadi; qarorni server beradi.
 */
(function () {
  'use strict';
  var UA = navigator.userAgent || '';
  var P = {
    ios: /iPhone|iPad|iPod/.test(UA) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1),
    android: /Android/.test(UA),
    inApp: /Telegram|Instagram|FBAN|FBAV|Line\/|WhatsApp/i.test(UA),
    iosNotSafari: /CriOS|FxiOS|EdgiOS|OPiOS/.test(UA),
    secure: window.isSecureContext || location.hostname === 'localhost' || location.hostname === '127.0.0.1'
  };

  function h(tag, attrs, kids) {
    var n = document.createElement(tag), k;
    for (k in (attrs || {})) {
      if (attrs[k] == null || attrs[k] === false) continue;
      if (k === 'text') n.textContent = attrs[k]; else if (k === 'class') n.className = attrs[k];
      else if (k === 'onclick') n.addEventListener('click', attrs[k]); else n.setAttribute(k, attrs[k] === true ? '' : attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }

  // ---------------------------------------------------------------- kirill tartibida yozilgan skanerni tiklash
  var RU = 'йцукенгшщзхъфывапролджэячсмитьбю.ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,ё"№;:?Ё';
  var US = "qwertyuiop[]asdfghjkl;'zxcvbnm,./QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?`@#$^&~";
  function normalize(s) {
    s = String(s == null ? '' : s).replace(/[\u0000-\u001f​-‏﻿]/g, '').trim();
    if (/[Ѐ-ӿ№]/.test(s)) {
      var out = '';
      for (var i = 0; i < s.length; i++) { var j = RU.indexOf(s[i]); out += j >= 0 ? US[j] : s[i]; }
      s = out;
    }
    return s;
  }

  // ---------------------------------------------------------------- ruxsat bo'yicha yo'riqnoma
  function guidance(err) {
    var name = err && err.name || '';
    var title, steps = [];
    if (!P.secure) {
      title = 'Kamera faqat HTTPS orqali ishlaydi';
      steps.push('Manzil https:// bilan boshlanishi kerak (masalan https://dusel.pages.dev/checkin).');
    } else if (P.inApp) {
      title = 'Ilova ichidagi brauzer kamerani bermaydi';
      steps.push(P.ios ? 'Sahifani Safari’da oching: ⋯ / ulashish → «Safari’da ochish».' : 'Sahifani Chrome’da oching: ⋮ → «Brauzerda ochish».');
    } else if (name === 'NotAllowedError' || name === 'SecurityError' || name === 'PermissionDeniedError') {
      title = 'Kameraga ruxsat berilmagan';
      if (P.ios) {
        steps.push('Safari manzil satridagi «aA» (yoki «⋯») → «Veb-sayt sozlamalari» → «Kamera» → «Ruxsat berish».');
        steps.push('Yoki: iPhone Sozlamalar → Safari → Kamera → «So‘rash» yoki «Ruxsat».');
        if (P.iosNotSafari) steps.push('iPhone’da Chrome ishlatilsa: Sozlamalar → Chrome → Kamera → yoqing.');
      } else if (P.android) {
        steps.push('Chrome manzil satridagi qulf/sozlama belgisi → «Ruxsatlar» → «Kamera» → «Ruxsat berish».');
        steps.push('Yoki: Chrome ⋮ → Sozlamalar → Sayt sozlamalari → Kamera → dusel.pages.dev → Ruxsat.');
        steps.push('Telefon Sozlamalar → Ilovalar → Chrome → Ruxsatlar → Kamera yoqilganini tekshiring.');
      } else {
        steps.push('Brauzer manzil satridagi kamera/qulf belgisi → Kamera → Ruxsat berish.');
      }
      steps.push('So‘ng «Kamerani qayta yoqish» tugmasini bosing.');
    } else if (name === 'NotFoundError' || name === 'OverconstrainedError' || name === 'DevicesNotFoundError') {
      title = 'Kamera topilmadi';
      steps.push('Tashqi 2D skanerdan foydalaning yoki raqamni qo‘lda kiriting.');
    } else if (name === 'NotReadableError' || name === 'TrackStartError' || name === 'AbortError') {
      title = 'Kamera boshqa ilovada band';
      steps.push('Kamera ishlatayotgan ilovalarni (video qo‘ng‘iroq, kamera) yoping, so‘ng «Kamerani qayta yoqish».');
    } else if (name === 'NO_API' || name === 'NotSupportedError') {
      title = 'Bu brauzer kamerani qo‘llamaydi';
      steps.push(P.ios ? 'Safari’ning yangi versiyasidan foydalaning.' : 'Chrome’ning yangi versiyasidan foydalaning.');
    } else {
      title = 'Kamerani ishga tushirib bo‘lmadi';
      steps.push('«Kamerani qayta yoqish» bosing. Bo‘lmasa — tashqi skaner yoki qo‘lda kiritish.');
    }
    steps.push('Kamerasiz ham ishlash mumkin: tashqi skaner yoki pastdagi maydonga raqamni yozing.');
    return { title: title, steps: steps, code: name || 'UNKNOWN' };
  }

  // ---------------------------------------------------------------- kamera
  var cam = { stream: null, video: null, raf: null, detector: null, onCode: null, last: { v: null, t: 0 }, busy: false, lastTick: 0, box: null, status: null };
  function emit(v, source) {
    v = normalize(v); if (!v) return;
    var now = Date.now();
    if (v === cam.last.v && now - cam.last.t < 1500) { cam.last.t = now; return; }   // bir qog'oz kadrdan chiqmaguncha qayta sanalmaydi
    cam.last = { v: v, t: now };
    if (cam.onCode) cam.onCode(v, source);
  }
  function tick(ts) {
    cam.raf = requestAnimationFrame(tick);
    var video = cam.video;
    if (cam.busy || !video || video.readyState < 2 || ts - cam.lastTick < 110) return;
    cam.lastTick = ts;
    if (cam.detector) {
      cam.busy = true;
      cam.detector.detect(video).then(function (r) { cam.busy = false; if (r && r[0] && r[0].rawValue) emit(r[0].rawValue, 'CAMERA'); },
                                       function () { cam.busy = false; cam.detector = null; });
      return;
    }
    var w = video.videoWidth, hh = video.videoHeight; if (!w || !window.jsQR) return;
    var c = cam.canvas || (cam.canvas = document.createElement('canvas')), ctx = cam.ctx || (cam.ctx = c.getContext('2d', { willReadFrequently: true }));
    var sc = Math.min(1, 720 / Math.max(w, hh)); c.width = Math.round(w * sc); c.height = Math.round(hh * sc);
    ctx.drawImage(video, 0, 0, c.width, c.height);
    var img = ctx.getImageData(0, 0, c.width, c.height);
    var q = window.jsQR(img.data, img.width, img.height, { inversionAttempts: 'attemptBoth' });
    if (q && q.data) emit(q.data, 'CAMERA');
  }
  function stopCamera() {
    if (cam.raf) cancelAnimationFrame(cam.raf); cam.raf = null;
    if (cam.stream) cam.stream.getTracks().forEach(function (t) { t.stop(); }); cam.stream = null;
  }
  function showProblem(err) {
    var g = guidance(err);
    if (!cam.box) return;
    cam.box.replaceChildren(h('div', { class: 'camhelp', role: 'alert', 'data-code': g.code }, [
      h('b', { text: '📷 ' + g.title }),
      h('ol', {}, g.steps.map(function (s) { return h('li', { text: s }); })),
      h('div', { class: 'row' }, [
        h('button', { class: 'primary', type: 'button', onclick: function () { startCamera(true); }, text: 'Kamerani qayta yoqish' }),
        h('button', { type: 'button', onclick: function () { stopCamera(); cam.box.replaceChildren(h('p', { class: 'muted small', text: 'Kamera o‘chirilgan — tashqi skaner yoki qo‘lda kiritish.' }), h('button', { type: 'button', onclick: function () { startCamera(true); }, text: 'Kamerani yoqish' })); }, text: 'Kamerasiz ishlash' })
      ])
    ]));
    if (cam.status) cam.status.textContent = 'Kamera: ' + g.code;
  }
  function startCamera(userAction) {
    stopCamera();
    if (!cam.box) return;
    if (!P.secure) return showProblem({ name: 'SecurityError' });
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return showProblem({ name: 'NO_API' });
    var video = cam.video = h('video', { playsinline: true, 'webkit-playsinline': true, muted: true, autoplay: true });
    video.muted = true;
    cam.box.replaceChildren(h('div', { class: 'scan' }, [video, h('div', { class: 'frame' }), h('div', { class: 'hint', text: 'QR kodni ramkaga keltiring' })]));
    if ('BarcodeDetector' in window) { try { cam.detector = new window.BarcodeDetector({ formats: ['qr_code'] }); } catch (e) { cam.detector = null; } }
    var want = { video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false };
    navigator.mediaDevices.getUserMedia(want)
      .catch(function (e) { if (e && e.name === 'OverconstrainedError') return navigator.mediaDevices.getUserMedia({ video: true, audio: false }); throw e; })
      .then(function (s) { cam.stream = s; video.srcObject = s; return video.play().catch(function (e) {
        // iOS: avtomatik ijro bloklansa — bitta bosish kerak
        cam.box.appendChild(h('button', { class: 'primary big', type: 'button', onclick: function () { video.play(); this.remove(); }, text: 'Kamerani boshlash' }));
      }); })
      .then(function () { if (cam.status) cam.status.textContent = 'Kamera: ishlayapti' + (cam.detector ? ' (tez)' : ''); cam.raf = requestAnimationFrame(tick); })
      .catch(showProblem);
  }

  // ---------------------------------------------------------------- tashqi skaner (klaviatura emulyatsiyasi)
  var wedge = { keys: '', codes: '', last: 0 };
  function onKey(e) {
    if (!cam.onCode || e.ctrlKey || e.metaKey || e.altKey) return;
    var tgt = e.target, tag = tgt && tgt.tagName;
    // matn maydonida yozilayotgan bo'lsa — maydonning o'z formasi (Enter) ishlaydi
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (tgt && tgt.isContentEditable)) { wedge.keys = wedge.codes = ''; return; }
    var now = performance.now();
    if (now - wedge.last > 80) wedge.keys = wedge.codes = '';      // inson yozishi sekin; skaner < 50 ms
    wedge.last = now;
    if (e.key === 'Enter' || e.key === 'Tab') {
      // ikki talqin: e.key (US tartib) va jismoniy tugma kodi (kirill va boshqa tartiblar). Skanda US bo'lmagan belgi bo'lsa — kod talqini
      var v = /[^\x20-\x7e]/.test(wedge.keys) ? wedge.codes : wedge.keys;
      wedge.keys = wedge.codes = '';
      if (v.length >= 5) { e.preventDefault(); emit(v, 'SCANNER'); }
      return;
    }
    if (e.key && e.key.length === 1) { wedge.keys += e.key; wedge.codes += codeChar(e) || e.key; }
  }
  document.addEventListener('keydown', onKey, true);

  // Skaner US tugma kodlarini yuboradi; telefon kirill tartibida bo'lsa ham e.code o'zgarmaydi (KeyH → h, Slash → /)
  var PUNCT = { Period: '.>', Comma: ',<', Slash: '/?', Semicolon: ';:', Quote: '\'"', Minus: '-_', Equal: '=+', BracketLeft: '[{', BracketRight: ']}',
                Backslash: '\\|', Backquote: '`~', Space: '  ', NumpadDecimal: '..', NumpadDivide: '//', NumpadSubtract: '--', NumpadAdd: '++', NumpadMultiply: '**' };
  function codeChar(e) {
    var c = e.code || '', sh = e.shiftKey ? 1 : 0, m;
    if ((m = /^Key([A-Z])$/.exec(c))) return sh ? m[1] : m[1].toLowerCase();
    if ((m = /^Digit([0-9])$/.exec(c))) return sh ? ')!@#$%^&*('.charAt(+m[1]) : m[1];
    if ((m = /^Numpad([0-9])$/.exec(c))) return m[1];
    if (PUNCT[c]) return PUNCT[c].charAt(sh);
    return null;
  }

  /**
   * mount(container, onCode(value, source), opts)
   *  - container: kamera bloki joylashadigan element
   *  - opts.status: holat matni uchun element (ixtiyoriy)
   */
  function mount(container, onCode, opts) {
    opts = opts || {};
    cam.onCode = onCode; cam.box = container; cam.status = opts.status || null; cam.last = { v: null, t: 0 };
    if (opts.camera === false) { container.replaceChildren(h('button', { type: 'button', onclick: function () { startCamera(true); }, text: 'Kamerani yoqish' })); return; }
    startCamera(false);
  }
  function unmount() { stopCamera(); cam.onCode = null; cam.box = null; }
  function pause() { var cb = cam.onCode; cam.onCode = null; return function () { cam.onCode = cb; }; }

  window.DuselScanner = { mount: mount, unmount: unmount, pause: pause, reset: function () { cam.last = { v: null, t: 0 }; },
    normalize: normalize, guidance: guidance, platform: P, emit: emit, _state: cam };
})();
