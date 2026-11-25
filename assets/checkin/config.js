// DUSEL check-in — muhit sozlamasi. Bu yerda faqat OMMAVIY (publishable/anon) kalit bo'ladi; maxfiy kalitlar hech qachon frontendga qo'yilmaydi.
// Production (dusel.pages.dev) uchun sozlama TASDIQDAN KEYIN qo'shiladi — ungacha /checkin production'da ishlamaydi.
window.DUSEL_CHECKIN_CONFIG = (function () {
  var h = location.hostname;
  var ENVS = {
    PRODUCTION: null,
    STAGING: null            // { url: 'https://<ref>.supabase.co', key: '<publishable key>' } — staging loyihasi yaratilgach
  };
  if (h === 'dusel.pages.dev') return ENVS.PRODUCTION ? Object.assign({ env: 'PRODUCTION' }, ENVS.PRODUCTION) : { env: 'PRODUCTION', disabled: true };
  if (/\.dusel\.pages\.dev$/.test(h)) return ENVS.STAGING ? Object.assign({ env: 'STAGING' }, ENVS.STAGING) : { env: 'STAGING', disabled: true };
  if (h === '127.0.0.1' || h === 'localhost') return { env: 'LOCAL-TEST', url: location.origin, key: 'local-test-anon-key' };
  return { env: 'UNKNOWN', disabled: true };
})();
