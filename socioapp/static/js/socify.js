/* Socify shared helpers — no dependencies. */

/* ===== Number formatting (mirrors the Python format_followers filter) ===== */
const fmt = n => n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'K' : String(Math.round(n));

/* ===== Interactive Watery / Wobbly Background (cursor-following fluid blobs + water ripples) ===== */
(() => {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const stage = document.createElement('div');
  stage.className = 'water-stage';
  stage.setAttribute('aria-hidden', 'true');
  stage.innerHTML =
    '<div class="water-blob b1"></div>' +
    '<div class="water-blob b2"></div>' +
    '<div class="water-blob b3"></div>' +
    '<canvas class="water-canvas"></canvas>';
  document.body.prepend(stage);

  const blobs = stage.querySelectorAll('.water-blob');
  const canvas = stage.querySelector('.water-canvas');
  const ctx = canvas.getContext('2d');

  let w = window.innerWidth, h = window.innerHeight;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const resize = () => {
    w = window.innerWidth; h = window.innerHeight;
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();
  window.addEventListener('resize', resize, { passive: true });

  // Target cursor position + three trailing fluid followers with different spring speeds
  let tx = w * 0.55, ty = h * 0.35;
  const pts = [
    { x: tx, y: ty, vx: 0, vy: 0, spring: 0.055, damp: 0.80, ox: 0,    oy: 0 },
    { x: w * 0.3, y: h * 0.6, vx: 0, vy: 0, spring: 0.032, damp: 0.84, ox: -90,  oy: 60 },
    { x: w * 0.7, y: h * 0.7, vx: 0, vy: 0, spring: 0.022, damp: 0.86, ox: 100,  oy: -70 }
  ];

  // Expanding water ripples spawned as the cursor glides across the page
  const ripples = [];
  let lastRipple = 0, lastX = tx, lastY = ty;

  window.addEventListener('pointermove', e => {
    tx = e.clientX; ty = e.clientY;
    const now = performance.now();
    const dist = Math.hypot(tx - lastX, ty - lastY);
    if (dist > 28 && now - lastRipple > 55) {
      lastRipple = now; lastX = tx; lastY = ty;
      ripples.push({
        x: tx, y: ty,
        r: 8,
        maxR: 110 + Math.min(dist * 1.4, 90),
        alpha: 0.28,
        hue: (now * 0.05) % 60 // subtle shift between indigo (235) and cyan/violet
      });
      if (ripples.length > 18) ripples.shift();
    }
  }, { passive: true });

  window.addEventListener('pointerdown', e => {
    ripples.push({ x: e.clientX, y: e.clientY, r: 6, maxR: 180, alpha: 0.40, hue: 15 });
  }, { passive: true });

  let t = 0;
  const loop = () => {
    t += 0.018;

    // 1. Update wobbly morphing fluid blobs with spring physics + velocity stretch
    pts.forEach((p, i) => {
      const targetX = tx + p.ox + Math.cos(t + i * 2.1) * 45;
      const targetY = ty + p.oy + Math.sin(t * 0.9 + i * 1.7) * 45;
      p.vx = (p.vx + (targetX - p.x) * p.spring) * p.damp;
      p.vy = (p.vy + (targetY - p.y) * p.spring) * p.damp;
      p.x += p.vx; p.y += p.vy;

      const speed = Math.min(Math.hypot(p.vx, p.vy), 28);
      const angle = Math.atan2(p.vy, p.vx) * (180 / Math.PI);
      const sx = 1 + speed * 0.012;
      const sy = 1 - speed * 0.006;
      blobs[i].style.transform =
        `translate3d(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px, 0) rotate(${angle.toFixed(1)}deg) scale(${sx.toFixed(3)}, ${sy.toFixed(3)})`;
    });

    // 2. Draw subtle wobbly water ripples on canvas
    ctx.clearRect(0, 0, w, h);
    for (let i = ripples.length - 1; i >= 0; i--) {
      const rp = ripples[i];
      rp.r += (rp.maxR - rp.r) * 0.055 + 0.9;
      rp.alpha *= 0.965;
      if (rp.alpha < 0.01 || rp.r >= rp.maxR) {
        ripples.splice(i, 1);
        continue;
      }

      // Draw a slightly organic wobbly ring
      ctx.save();
      ctx.beginPath();
      const steps = 32;
      for (let s = 0; s <= steps; s++) {
        const a = (s / steps) * Math.PI * 2;
        const wobble = Math.sin(a * 4 + t * 3 + i) * (rp.r * 0.045) + Math.cos(a * 3 - t * 2) * (rp.r * 0.03);
        const rx = rp.x + Math.cos(a) * (rp.r + wobble);
        const ry = rp.y + Math.sin(a) * (rp.r + wobble);
        if (s === 0) ctx.moveTo(rx, ry); else ctx.lineTo(rx, ry);
      }
      ctx.closePath();
      ctx.strokeStyle = `hsla(${230 + rp.hue}, 78%, 58%, ${rp.alpha.toFixed(3)})`;
      ctx.lineWidth = 1.6;
      ctx.stroke();

      // Inner caustic echo ring
      if (rp.r > 24) {
        ctx.beginPath();
        ctx.arc(rp.x, rp.y, rp.r * 0.68, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(${260 + rp.hue}, 75%, 62%, ${(rp.alpha * 0.45).toFixed(3)})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      ctx.restore();
    }

    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
})();

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

/* ===== Chart.js shared theme (Light mode) ===== */
function themeCharts() {
  if (!window.Chart) return;
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.color = '#4B5568';
  Chart.defaults.borderColor = 'rgba(79,70,229,.10)';
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.plugins.tooltip.backgroundColor = '#0F172A';
  Chart.defaults.plugins.tooltip.titleColor = '#FFFFFF';
  Chart.defaults.plugins.tooltip.bodyColor = '#E2E8F0';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(255,255,255,.12)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.elements.bar.borderRadius = 6;
  Chart.defaults.maintainAspectRatio = false;
}
