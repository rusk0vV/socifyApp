/* Socify shared helpers — no dependencies. */

/* ===== Number formatting (mirrors the Python format_followers filter) ===== */
const fmt = n => n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'K' : String(Math.round(n));

/* ===== Sidebar (mobile off-canvas) ===== */
(() => {
  const sb = document.getElementById('sidebar');
  const btn = document.getElementById('navToggle');
  const scrim = document.getElementById('scrim');
  if (!sb || !btn) return;
  const close = () => { sb.classList.remove('open'); scrim && scrim.classList.remove('show'); btn.setAttribute('aria-expanded', 'false'); };
  btn.addEventListener('click', () => {
    const open = sb.classList.toggle('open');
    scrim && scrim.classList.toggle('show', open);
    btn.setAttribute('aria-expanded', String(open));
  });
  scrim && scrim.addEventListener('click', close);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
})();

/* ===== Topbar shadow after scroll ===== */
(() => {
  const tb = document.querySelector('.topbar');
  if (!tb) return;
  const on = () => tb.classList.toggle('scrolled', window.scrollY > 8);
  on(); window.addEventListener('scroll', on, { passive: true });
})();

/* ===== Count-up: <div data-countup="12400" data-suffix="%"> ===== */
(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('[data-countup]').forEach(el => {
    const target = parseFloat(el.dataset.countup);
    if (!isFinite(target) || reduce) return;
    const suffix = el.dataset.suffix || '';
    const decimals = Number.isInteger(target) ? 0 : 1;
    const render = v => (suffix ? v.toFixed(decimals) : fmt(v)) + suffix;
    const start = performance.now(), dur = 800;
    const tick = now => {
      const t = Math.min(1, (now - start) / dur), eased = 1 - Math.pow(1 - t, 3);
      el.textContent = render(target * eased);
      if (t < 1) requestAnimationFrame(tick); else el.textContent = render(target);
    };
    requestAnimationFrame(tick);
  });
})();

/* ===== Greeting: <span data-greeting> ===== */
document.querySelectorAll('[data-greeting]').forEach(el => {
  const h = new Date().getHours();
  el.textContent = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
});

/* ===== Toasts: toast('Saved', 'success' | 'error' | 'info') ===== */
function toast(msg, type = 'info') {
  const host = document.getElementById('toasts'); if (!host) return;
  const el = document.createElement('div');
  el.className = 'toast-s ' + type; el.textContent = msg; el.setAttribute('role', 'status');
  host.appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 250); }, 4000);
}

/* ===== Bootstrap tooltips ===== */
document.addEventListener('DOMContentLoaded', () => {
  if (window.bootstrap) document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));
});

/* ===== Copy to clipboard: <button data-copy="text"> ===== */
document.addEventListener('click', e => {
  const b = e.target.closest('[data-copy]'); if (!b) return;
  navigator.clipboard.writeText(b.dataset.copy).then(() => toast('Copied to clipboard', 'success'));
});

/* ===== Top progress bar while navigating (slow pages: Instagram/YouTube fetches) ===== */
(() => {
  const bar = document.getElementById('navbar-progress'); if (!bar) return;
  document.addEventListener('click', e => {
    const a = e.target.closest('a[href]');
    if (!a || a.target === '_blank' || e.ctrlKey || e.metaKey || e.shiftKey) return;
    const url = new URL(a.href, location.href);
    if (url.origin === location.origin && url.pathname !== location.pathname) bar.classList.add('on');
  });
  window.addEventListener('pageshow', () => bar.classList.remove('on'));
})();

/* ===== Submit buttons: show spinner + disable on submit (prevents double posts) ===== */
document.addEventListener('submit', e => {
  const btn = e.target.querySelector('button[type="submit"].btn-s');
  if (!btn || e.defaultPrevented) return;
  btn.classList.add('loading');
  btn.dataset.label = btn.innerHTML;
  btn.innerHTML = '<span class="spinner"></span> Please wait…';
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('button.loading').forEach(b => { b.classList.remove('loading'); if (b.dataset.label) b.innerHTML = b.dataset.label; });
});

/* ===== Chart.js shared theme (only if Chart is loaded) ===== */
function themeCharts() {
  if (!window.Chart) return;
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.color = '#9AA3B8';
  Chart.defaults.borderColor = 'rgba(255,255,255,.06)';
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.plugins.tooltip.backgroundColor = '#1F2433';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(255,255,255,.14)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.elements.bar.borderRadius = 6;
  Chart.defaults.maintainAspectRatio = false;
}

