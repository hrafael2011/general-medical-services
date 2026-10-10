// Verificación visual Task 2.4 — no toca producción, solo lee el frontend servido.
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
// playwright vive en frontend/node_modules (no hay dependencia en la raíz)
const { chromium } = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright'));

const BASE = 'https://general-medical-services.vercel.app';

const browser = await chromium.launch();

// ── 1. Escritorio: medir tarjeta y centrado ──────────────────────────────
const desktop = await browser.newPage({ viewport: { width: 1280, height: 800 } });
await desktop.goto(`${BASE}/forgot-password`, { waitUntil: 'networkidle' });

const desktopMetrics = await desktop.evaluate(() => {
  const card = document.querySelector('.auth-panel--narrow');
  const input = document.querySelector('input');
  const rect = (el) =>
    el
      ? { width: Math.round(el.getBoundingClientRect().width), left: Math.round(el.getBoundingClientRect().left) }
      : null;
  const c = rect(card);
  const deadClasses = ['login-page', 'login-card', 'form-group', 'form-label', 'form-input', 'form-hint'].filter(
    (cls) => !!document.querySelector('.' + cls)
  );
  return {
    viewportW: window.innerWidth,
    card: c,
    centered: c ? { leftGap: c.left, rightGap: window.innerWidth - (c.left + c.width) } : null,
    input: rect(input),
    deadClasses,
  };
});
console.log('=== DESKTOP 1280px — /forgot-password ===');
console.log(JSON.stringify(desktopMetrics, null, 2));

// ── 2. Móvil 400px: sin scroll horizontal ───────────────────────────────
const mobile = await browser.newPage({ viewport: { width: 400, height: 800 } });
await mobile.goto(`${BASE}/forgot-password`, { waitUntil: 'networkidle' });
const mobileMetrics = await mobile.evaluate(() => ({
  viewportW: window.innerWidth,
  scrollWidth: document.documentElement.scrollWidth,
  clientWidth: document.documentElement.clientWidth,
  hScroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
}));
console.log('=== MOBILE 400px — /forgot-password ===');
console.log(JSON.stringify(mobileMetrics, null, 2));

// ── 3. /set-password?token=basura ───────────────────────────────────────
const sp = await browser.newPage({ viewport: { width: 1280, height: 800 } });
await sp.goto(`${BASE}/set-password?token=basura`, { waitUntil: 'networkidle' });
await sp.waitForTimeout(1500);
const spBody = await sp.evaluate(() => document.body.innerText);
console.log('=== /set-password?token=basura — texto visible ===');
console.log(spBody.trim().slice(0, 600));

await browser.close();
