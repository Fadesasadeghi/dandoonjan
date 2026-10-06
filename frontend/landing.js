"use strict";
// Decorative asset lifecycle only. Case, upload, processing and report handlers
// remain in app.js. A failed image exposes a neutral inline status message.
const landingTooth = document.getElementById("landing-tooth");
const showLandingFallback = () => landingTooth.closest("figure").classList.add("art-unavailable");
landingTooth.addEventListener("error", showLandingFallback);
if (landingTooth.complete && !landingTooth.naturalWidth) showLandingFallback();

// Existing rings only: localized light and anchored depth activation.
(() => {
  const home = document.getElementById('view-home');
  const eligible = matchMedia('(min-width: 1051px) and (hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)');
  const rings = [...home.querySelectorAll('.landing-orbits span')].map((el, i) => ({
    el, scale: [.016, .020, .012, .018][i], drift: [[3, -4], [-4, -3], [4, 3], [-3, 5]][i], level: 0, target: 0, lx: 50, ly: 50, tx: 50, ty: 50, specularAngle: 0, specularTarget: 0
  }));
  let geometry = null, frame = 0, lastTime = 0;
  const clear = r => {
    ['--ring-light', '--ring-light-x', '--ring-light-y', '--ring-specular-x', '--ring-specular-y', 'scale', 'translate'].forEach(name => r.el.style.removeProperty(name));
  };
  const reset = () => {
    cancelAnimationFrame(frame);
    frame = lastTime = 0;
    geometry = null;
    rings.forEach(r => { r.level = r.target = 0; clear(r); });
  };
  const tick = time => {
    if (!eligible.matches || document.hidden || !home.classList.contains('active')) { reset(); return; }
    const blend = 1 - Math.exp(-Math.min(lastTime ? time - lastTime : 16, 64) / 160);
    lastTime = time;
    let moving = false;
    rings.forEach(r => {
      r.level += (r.target - r.level) * blend;
      r.lx += (r.tx - r.lx) * blend;
      r.ly += (r.ty - r.ly) * blend;
      // Shortest angular path keeps the reflection on the ring across 0/360°.
      const arc = Math.atan2(Math.sin(r.specularTarget - r.specularAngle), Math.cos(r.specularTarget - r.specularAngle));
      r.specularAngle += arc * blend;
      if (Math.abs(r.target - r.level) < .001) r.level = r.target;
      else moving = true;
      if (r.level === 0) clear(r);
      else {
        if (Math.hypot(r.tx - r.lx, r.ty - r.ly) > .1) moving = true;
        if (Math.abs(arc) > .002) moving = true;
        r.el.style.setProperty('--ring-specular-x', `${(50 + Math.cos(r.specularAngle) * 50).toFixed(2)}%`);
        r.el.style.setProperty('--ring-specular-y', `${(50 + Math.sin(r.specularAngle) * 50).toFixed(2)}%`);
        r.el.style.setProperty('--ring-light', (r.level * .65).toFixed(4));
        r.el.style.setProperty('--ring-light-x', `${r.lx.toFixed(2)}%`);
        r.el.style.setProperty('--ring-light-y', `${r.ly.toFixed(2)}%`);
        r.el.style.translate = `${(r.level * r.drift[0]).toFixed(3)}px ${(r.level * r.drift[1]).toFixed(3)}px`;
        r.el.style.scale = (1 + r.level * r.scale).toFixed(5);
      }
    });
    frame = moving ? requestAnimationFrame(tick) : 0;
    if (!moving) lastTime = 0;
  };
  const schedule = () => { if (!frame) frame = requestAnimationFrame(tick); };
  const neutral = () => { rings.forEach(r => { r.target = 0; }); schedule(); };
  window.addEventListener('pointermove', event => {
    if (!eligible.matches || event.pointerType !== 'mouse' || !home.classList.contains('active')) return;
    // Read once after invalidation, never in the animation loop. Recover resting
    // centers and dimensions so activation cannot feed back into proximity.
    if (!geometry) geometry = rings.map(r => {
      const b = r.el.getBoundingClientRect();
      return {cx: b.x + b.width / 2 - r.level * r.drift[0], cy: b.y + b.height / 2 - r.level * r.drift[1],
        rx: r.el.offsetWidth / 2, ry: r.el.offsetHeight / 2};
    });
    rings.forEach((r, i) => {
      const g = geometry[i], dx = event.clientX - g.cx, dy = event.clientY - g.cy;
      const distance = Math.hypot(dx, dy);
      const radial = g.rx && g.ry ? Math.hypot(dx / g.rx, dy / g.ry) : 0;
      const edgeDistance = radial ? Math.abs(distance - distance / radial) : Infinity;
      const proximity = Math.max(0, 1 - edgeDistance / 130);
      const strength = proximity * proximity * (3 - 2 * proximity);
      r.target = strength;
      if (radial > .001) r.specularTarget = Math.atan2(dy / g.ry, dx / g.rx);
      r.tx = Math.max(0, Math.min(100, 50 + dx / (g.rx || 1) * 50));
      r.ty = Math.max(0, Math.min(100, 50 + dy / (g.ry || 1) * 50));
    });
    schedule();
  }, { passive: true });
  document.documentElement.addEventListener('pointerleave', neutral);
  window.addEventListener('blur', neutral);
  eligible.addEventListener('change', reset);
  window.addEventListener('resize', reset, { passive: true });
  window.addEventListener('scroll', () => { geometry = null; neutral(); }, { passive: true });
  document.addEventListener('visibilitychange', reset);
})();
