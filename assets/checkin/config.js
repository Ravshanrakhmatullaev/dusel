// DUSEL check-in — muhit sozlamasi. Bu yerda faqat OMMAVIY (publishable/anon) kalit bo'ladi; maxfiy kalitlar hech qachon frontendga qo'yilmaydi.
// Har bir sayt manzili aynan bitta bazaga bog'lanadi; ilova serverdagi 'environment' sozlamasi shu yerda kutilgan bilan mos kelmasa — ishlamaydi.
//   dusel.pages.dev                 → PRODUCTION (tasdiqdan keyin)            — /checkin + /inventory
//   inventory-live.dusel.pages.dev  → PRODUCTION, FAQAT /inventory (ixtiyoriy) — kirish ilovasi bu manzilda o'chirilgan
//   boshqa *.dusel.pages.dev        → STAGING (sinov branch)
window.DUSEL_CHECKIN_CONFIG = (function () {
  var h = location.hostname;
  var ENVS = {
    PRODUCTION: null,        // { url: 'https://<prod-ref>.supabase.co', key: '<publishable key>' } — P4/P5 tasdig'idan keyin
    STAGING: null            // { url: 'https://<branch-ref>.supabase.co', key: '<publishable key>' } — staging branch yaratilgach
  };
  function pick(env, extra) { return ENVS[env] ? Object.assign({ env: env, expectServerEnv: env }, ENVS[env], extra || {}) : Object.assign({ env: env, disabled: true }, extra || {}); }
  if (h === 'dusel.pages.dev') return pick('PRODUCTION');
  if (h === 'inventory-live.dusel.pages.dev') return pick('PRODUCTION', { apps: ['inventory'] });
  if (/\.dusel\.pages\.dev$/.test(h)) return pick('STAGING');
  if (h === '127.0.0.1' || h === 'localhost') return { env: 'LOCAL-TEST', expectServerEnv: 'STAGING', url: location.origin, key: 'local-test-anon-key' };
  return { env: 'UNKNOWN', disabled: true };
})();
