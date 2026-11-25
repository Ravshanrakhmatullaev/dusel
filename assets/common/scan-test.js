/* Skaner sinovi: kamera ruxsati, dekoder, tashqi skaner va kirill tartibini tekshiradi. Server bilan aloqa YO'Q. */
(function () {
  'use strict';
  var P = window.DuselScanner.platform, log = document.getElementById('log'), out = document.getElementById('out'), rows = [];
  function kv(k, v) { var d = document.getElementById('env'); var a = document.createElement('dt'), b = document.createElement('dd'); a.textContent = k; b.textContent = v; d.appendChild(a); d.appendChild(b); }
  kv('Brauzer', navigator.userAgent);
  kv('HTTPS (xavfsiz kontekst)', P.secure ? 'ha' : 'YO\'Q — kamera ishlamaydi');
  kv('Platforma', P.ios ? 'iPhone/iPad' : P.android ? 'Android' : 'boshqa');
  kv('Ilova ichidagi brauzer', P.inApp ? 'HA — Safari/Chrome’da oching' : 'yo\'q');
  kv('Tez dekoder (BarcodeDetector)', 'BarcodeDetector' in window ? 'bor' : 'yo\'q (jsQR ishlatiladi)');
  kv('Kamera API', navigator.mediaDevices && navigator.mediaDevices.getUserMedia ? 'bor' : 'YO\'Q');
  if (navigator.permissions && navigator.permissions.query) {
    navigator.permissions.query({ name: 'camera' }).then(function (r) { kv('Kamera ruxsati', r.state); }, function () { kv('Kamera ruxsati', 'aniqlab bo\'lmadi'); });
  }
  // server bilan bir xil qoidalar (checkin._parse) — faqat ko'rsatish uchun
  function classify(s) {
    if (/^DUSELR1:[A-Za-z0-9_-]{24}$/.test(s)) return ['info', 'ALMASHTIRISH BILETI (format to\'g\'ri)'];
    var m = /^([0-9]{5})$/.exec(s) || /^https?:\/\/(?:dusel\.pages\.dev\/(?:ticket(?:\.html)?|index\.html)?|ravshanrakhmatullaev\.github\.io\/dusel\/(?:index\.html)?)\?code=([0-9]{5})$/i.exec(s);
    if (m) { var n = +(m[1] || m[2]); return n >= 1 && n <= 11222 ? ['ok', 'KONSERT BILETI № ' + (m[1] || m[2])] : ['bad', 'Diapazondan tashqari raqam']; }
    if (/^https?:\/\/dusel\.pages\.dev\/(gold|silver|gal|coupon)(\.html)?([/?#]|$)/i.test(s)) return ['bad', 'KUPON/VAUCHER — konsert bileti emas'];
    return ['bad', 'Noma\'lum QR'];
  }
  var t0 = performance.now();
  function got(v, src) {
    var c = classify(v), ms = Math.round(performance.now() - t0); t0 = performance.now();
    out.innerHTML = ''; var d = document.createElement('div'); d.className = 'result ' + c[0];
    var b = document.createElement('div'); b.className = 'big'; b.textContent = c[1]; d.appendChild(b);
    var p = document.createElement('p'); p.className = 'small'; p.textContent = 'Manba: ' + src + ' · ' + v; d.appendChild(p); out.appendChild(d);
    var li = document.createElement('li'); li.textContent = new Date().toLocaleTimeString() + ' · ' + src + ' · ' + c[1]; log.prepend(li);
    rows.push([new Date().toISOString(), src, c[1], v].join(' | '));
    if (navigator.vibrate) navigator.vibrate(c[0] === 'ok' ? 60 : [150, 60, 150]);
  }
  window.DuselScanner.mount(document.getElementById('cam'), got, { status: document.getElementById('camstatus') });
  document.getElementById('f').addEventListener('submit', function (e) {
    e.preventDefault(); var i = document.getElementById('manual'); var v = window.DuselScanner.normalize(i.value); if (v) got(v, /^\d+$/.test(v) ? 'MANUAL' : 'SCANNER→maydon'); i.value = '';
  });
  document.getElementById('copy').addEventListener('click', function () {
    var txt = 'DUSEL skaner sinovi\n' + navigator.userAgent + '\n' + rows.join('\n');
    if (navigator.clipboard) navigator.clipboard.writeText(txt).then(function () { alert('Nusxalandi'); }, function () { prompt('Nusxalang:', txt); }); else prompt('Nusxalang:', txt);
  });
  window.DUSEL_SCANTEST = { rows: rows };
})();
