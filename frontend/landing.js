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
  const artwork = landingTooth.closest('.landing-artwork');
  const sheen = {level: 0, target: 0, x: 50, y: 50, tx: 50, ty: 50, angle: 0, targetAngle: 0};
  // Middle surfaces share the existing scheduler; no geometry is animated.
  const surfaces = [home.querySelector('.landing-product-context'),
    ...home.querySelectorAll('.landing-process li'), home.querySelector('.landing-story')]
    .map((el, i) => ({el, kind: i === 0 ? 'card' : i === 5 ? 'edge' : 'step',
      level: 0, target: 0, x: 50, y: 50, tx: 50, ty: 50, angle: 0, ta: 0, textLevel: 0, textTarget: 0}));
  const faqLights = [...home.querySelectorAll('.landing-faq details')].map(el =>
    ({el, level: 0, target: 0, x: 50, y: 50, tx: 50, ty: 50}));
  const clearFaq = s => ['--faq-light', '--faq-x', '--faq-y'].forEach(name => s.el.style.removeProperty(name));
  let surfaceBounds = null;
  const clearSurface = s => ['--local-light', '--local-x', '--local-y', '--local-angle', '--local-edge-x', '--local-edge-y', '--step-text-light']
    .forEach(name => s.el.style.removeProperty(name));
  let toothBounds = null;
  const clearSheen = () => ['--tooth-sheen', '--tooth-sheen-x', '--tooth-sheen-y', '--tooth-light-angle'].forEach(name => artwork.style.removeProperty(name));
  let geometry = null, frame = 0, lastTime = 0;
  const clear = r => {
    ['--ring-light', '--ring-light-x', '--ring-light-y', '--ring-specular-x', '--ring-specular-y', 'scale', 'translate'].forEach(name => r.el.style.removeProperty(name));
  };
  const reset = () => {
    cancelAnimationFrame(frame);
    frame = lastTime = 0;
    geometry = null;
    toothBounds = null;
    surfaceBounds = null;
    faqLights.forEach(s => { s.level = s.target = 0; clearFaq(s); });
    surfaces.forEach(s => { s.level = s.target = s.textLevel = s.textTarget = 0; clearSurface(s); });
    sheen.level = sheen.target = 0;
    clearSheen();
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
    // Additive lighting only; the tooth's geometry and ring formulas are untouched.
    sheen.level += (sheen.target - sheen.level) * blend;
    sheen.x += (sheen.tx - sheen.x) * blend;
    sheen.y += (sheen.ty - sheen.y) * blend;
    const lightArc = Math.atan2(Math.sin(sheen.targetAngle - sheen.angle), Math.cos(sheen.targetAngle - sheen.angle));
    sheen.angle += lightArc * blend;
    if (Math.abs(sheen.target - sheen.level) < .001) sheen.level = sheen.target;
    else moving = true;
    if (sheen.level === 0) clearSheen();
    else {
      if (Math.abs(lightArc) > .002) moving = true;
      if (Math.hypot(sheen.tx - sheen.x, sheen.ty - sheen.y) > .1) moving = true;
      artwork.style.setProperty('--tooth-light-angle', `${(sheen.angle * 180 / Math.PI - 90).toFixed(3)}deg`);
      artwork.style.setProperty('--tooth-sheen', (sheen.level * .45).toFixed(4));
      artwork.style.setProperty('--tooth-sheen-x', `${sheen.x.toFixed(2)}%`);
      artwork.style.setProperty('--tooth-sheen-y', `${sheen.y.toFixed(2)}%`);
    }
    surfaces.forEach(s => {
      if (s.kind === 'step') {
        s.textLevel += (s.textTarget - s.textLevel) * blend;
        if (Math.abs(s.textTarget - s.textLevel) < .001) s.textLevel = s.textTarget;
        else moving = true;
        if (s.textLevel === 0) s.el.style.removeProperty('--step-text-light');
        else s.el.style.setProperty('--step-text-light', s.textLevel.toFixed(4));
      }
      s.level += (s.target - s.level) * blend;
      s.x += (s.tx - s.x) * blend;
      s.y += (s.ty - s.y) * blend;
      const arc = Math.atan2(Math.sin(s.ta - s.angle), Math.cos(s.ta - s.angle));
      s.angle += arc * blend;
      if (Math.abs(s.target - s.level) < .001) s.level = s.target;
      else moving = true;
      if (s.level === 0) clearSurface(s);
      else {
        if (Math.hypot(s.tx - s.x, s.ty - s.y) > .1 || Math.abs(arc) > .002) moving = true;
        s.el.style.setProperty('--local-light', s.level.toFixed(4));
        s.el.style.setProperty('--local-x', `${s.x.toFixed(2)}%`);
        s.el.style.setProperty('--local-y', `${s.y.toFixed(2)}%`);
        s.el.style.setProperty('--local-angle', `${(s.angle * 180 / Math.PI + 90).toFixed(3)}deg`);
        if (s.kind === 'edge') {
          // Same pointer-facing projection as the approved Hero C+ reflection.
          s.el.style.setProperty('--local-edge-x', `${(50 + Math.cos(s.angle) * 50).toFixed(2)}%`);
          s.el.style.setProperty('--local-edge-y', `${(50 + Math.sin(s.angle) * 50).toFixed(2)}%`);
        }
      }
    });
    faqLights.forEach(s => {
      s.level += (s.target - s.level) * blend;
      s.x += (s.tx - s.x) * blend;
      s.y += (s.ty - s.y) * blend;
      if (Math.abs(s.target - s.level) < .001) s.level = s.target;
      else moving = true;
      if (s.level === 0) clearFaq(s);
      else {
        if (Math.hypot(s.tx - s.x, s.ty - s.y) > .1) moving = true;
        s.el.style.setProperty('--faq-light', s.level.toFixed(4));
        s.el.style.setProperty('--faq-x', `${s.x.toFixed(2)}%`);
        s.el.style.setProperty('--faq-y', `${s.y.toFixed(2)}%`);
      }
    });
    frame = moving ? requestAnimationFrame(tick) : 0;
    if (!moving) lastTime = 0;
  };
  const schedule = () => { if (!frame) frame = requestAnimationFrame(tick); };
  const neutral = () => { faqLights.forEach(s => { s.target = 0; }); surfaces.forEach(s => { s.target = s.textTarget = 0; }); sheen.target = 0; rings.forEach(r => { r.target = 0; }); schedule(); };
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
    if (!toothBounds) toothBounds = landingTooth.getBoundingClientRect();
    const b = toothBounds;
    const dx = event.clientX - (b.x + b.width / 2), dy = event.clientY - (b.y + b.height / 2);
    const radial = b.width && b.height ? Math.hypot(dx / (b.width / 2), dy / (b.height / 2)) : Infinity;
    const gap = Math.max(0, (radial - 1) * Math.min(b.width, b.height) / 2);
    const proximity = Math.max(0, 1 - gap / 90);
    sheen.target = proximity * proximity * (3 - 2 * proximity);
    if (Math.hypot(dx, dy) > 1) sheen.targetAngle = Math.atan2(dy / (b.height || 1), dx / (b.width || 1));
    sheen.tx = Math.max(0, Math.min(100, 50 + dx / (b.width || 1) * 100));
    sheen.ty = Math.max(0, Math.min(100, 50 + dy / (b.height || 1) * 100));
    if (!surfaceBounds) surfaceBounds = surfaces.map(s => {
      const b = s.el.getBoundingClientRect();
      // Existing outline: right:-85px (RTL inline-start), top:-25px,
      // 470x370 border box, 1px border, rotated -18deg about its center.
      return s.kind === 'edge' ? {cx: b.right + 85 - 235, cy: b.top - 25 + 185, rx: 235, ry: 185} : b;
    });
    let nearestStep = null, nearestDistance = Infinity;
    surfaces.forEach((s, i) => {
      const b = surfaceBounds[i];
      let gap;
      if (s.kind === 'edge') {
        const dx = event.clientX - b.cx, dy = event.clientY - b.cy;
        const a = 18 * Math.PI / 180;
        const x = dx * Math.cos(a) - dy * Math.sin(a), y = dx * Math.sin(a) + dy * Math.cos(a);
        const radial = Math.hypot(x / b.rx, y / b.ry);
        gap = radial ? Math.abs(Math.hypot(x, y) * (1 - 1 / radial)) : Infinity;
        s.ta = Math.atan2(y / b.ry, x / b.rx);
      } else {
        gap = Math.hypot(Math.max(b.left - event.clientX, 0, event.clientX - b.right),
          Math.max(b.top - event.clientY, 0, event.clientY - b.bottom));
        s.tx = Math.max(0, Math.min(100, (event.clientX - b.left) / b.width * 100));
        s.ty = Math.max(0, Math.min(100, (event.clientY - b.top) / b.height * 100));
      }
      const proximity = Math.max(0, 1 - gap / (s.kind === 'step' ? 38 : s.kind === 'edge' ? 130 : 70));
      s.target = proximity * proximity * (3 - 2 * proximity);
      if (s.kind === 'step' && s.target > 0) {
        const distance = Math.hypot(event.clientX - (b.left + b.width / 2),
          event.clientY - (b.top + b.height / 2));
        if (distance < nearestDistance) { nearestStep = s; nearestDistance = distance; }
      }
    });
    surfaces.forEach(s => { if (s.kind === 'step') s.textTarget = s === nearestStep ? s.target : 0; });
    // Measure FAQ rows on pointer input: accordion/reveal geometry may be changing.
    // Select just the nearest row within 28px; never light both neighboring rows.
    let nearestFaq = null, faqDistance = Infinity;
    faqLights.forEach(s => {
      const b = s.el.getBoundingClientRect();
      const gap = Math.hypot(Math.max(b.left - event.clientX, 0, event.clientX - b.right),
        Math.max(b.top - event.clientY, 0, event.clientY - b.bottom));
      s.target = 0;
      if (gap < 28 && gap < faqDistance) {
        nearestFaq = s; faqDistance = gap;
        s.tx = Math.max(0, Math.min(100, (event.clientX - b.left) / (b.width || 1) * 100));
        s.ty = Math.max(0, Math.min(100, (event.clientY - b.top) / (b.height || 1) * 100));
      }
    });
    if (nearestFaq) {
      const proximity = 1 - faqDistance / 28;
      nearestFaq.target = proximity * proximity * (3 - 2 * proximity);
    }
    schedule();
  }, { passive: true });
  document.documentElement.addEventListener('pointerleave', neutral);
  window.addEventListener('blur', neutral);
  eligible.addEventListener('change', reset);
  window.addEventListener('resize', reset, { passive: true });
  window.addEventListener('scroll', () => { geometry = null; toothBounds = null; surfaceBounds = null; neutral(); }, { passive: true });
  document.addEventListener('visibilitychange', reset);
  home.addEventListener('animationend', event => {
    if (event.animationName === 'middle-entry') surfaceBounds = null;
  });
})();

// One-time middle entry. The process and statement share their existing wrapper,
// so they reveal together without doubled movement or alignment changes.
(() => {
  const home = document.getElementById('view-home');
  const targets = [home.querySelector('.landing-product-context'), home.querySelector('.landing-story')];
  const motion = matchMedia('(min-width: 1051px) and (prefers-reduced-motion: no-preference)');
  if (!motion.matches || typeof IntersectionObserver === 'undefined') return;
  const seen = new Set();
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting || seen.has(entry.target)) return;
      seen.add(entry.target);
      entry.target.classList.remove('middle-entry-pending');
      entry.target.classList.add('middle-entry-revealed');
      observer.unobserve(entry.target);
    });
    if (seen.size === targets.length) observer.disconnect();
  }, { threshold: .08 });
  targets.forEach(el => {
    el.classList.add('middle-entry-pending');
    el.addEventListener('animationend', event => {
      if (event.target === el && event.animationName === 'middle-entry') {
        // Restore the original resting opacity/translate and stacking behavior.
        el.classList.remove('middle-entry-revealed');
      }
    });
    observer.observe(el);
  });
  motion.addEventListener('change', () => {
    if (motion.matches) return;
    observer.disconnect();
    targets.forEach(el => {
      seen.add(el);
      el.classList.remove('middle-entry-pending', 'middle-entry-revealed');
    });
  });
})();

// Native summary activation (including keyboard) with reversible answer animation.
(() => {
  const motion = matchMedia('(prefers-reduced-motion: no-preference)');
  document.querySelectorAll('.landing-faq details').forEach(row => {
    const summary = row.querySelector('summary'), answer = row.querySelector('p');
    if (!answer || typeof answer.animate !== 'function') return; // Native fallback.
    let animation = null, desired = row.open;
    const finish = () => {
      if (animation) { animation.onfinish = null; animation.cancel(); animation = null; }
      row.open = desired;
      row.removeAttribute('data-faq-open');
      answer.style.removeProperty('overflow');
    };
    summary.addEventListener('click', event => {
      event.preventDefault();
      desired = !desired;
      const fromHeight = row.open ? answer.getBoundingClientRect().height : 0;
      const currentStyle = row.open ? getComputedStyle(answer) : null;
      const fromOpacity = currentStyle ? currentStyle.opacity : '0';
      const spacing = ['paddingTop', 'paddingBottom', 'marginTop', 'marginBottom'];
      const fromSpacing = Object.fromEntries(spacing.map(name => [name, currentStyle ? currentStyle[name] : '0px']));
      if (animation) { animation.onfinish = null; animation.cancel(); }
      row.open = true; // Keep native content rendered throughout closing.
      row.setAttribute('data-faq-open', String(desired));
      summary.setAttribute('aria-expanded', String(desired));
      if (!motion.matches) { finish(); return; }
      const toHeight = desired ? answer.getBoundingClientRect().height : 0;
      const restingStyle = getComputedStyle(answer);
      const toSpacing = Object.fromEntries(spacing.map(name => [name, desired ? restingStyle[name] : '0px']));
      answer.style.overflow = 'hidden';
      animation = answer.animate([
        {...fromSpacing, height: `${fromHeight}px`, opacity: fromOpacity, boxSizing: 'border-box', minHeight: '0'},
        {...toSpacing, height: `${toHeight}px`, opacity: desired ? '1' : '0', boxSizing: 'border-box', minHeight: '0'}
      ], {duration: 320, easing: 'cubic-bezier(.22, 1, .36, 1)', fill: 'both'});
      animation.onfinish = finish;
    });
    row.addEventListener('toggle', () => {
      if (!animation) { desired = row.open; summary.setAttribute('aria-expanded', String(row.open)); }
    });
    motion.addEventListener('change', () => { if (!motion.matches) finish(); });
  });
})();

// FAQ entry uses the approved middle reveal language, once per page lifecycle.
(() => {
  const faq = document.getElementById('landing-faq');
  const motion = matchMedia('(prefers-reduced-motion: no-preference)');
  if (!faq || !motion.matches || typeof IntersectionObserver === 'undefined') return;
  const targets = [faq.querySelector('.landing-faq-intro'), ...faq.querySelectorAll('details')];
  let seen = false;
  const clear = () => targets.forEach(el => el.classList.remove('faq-entry-pending', 'faq-entry-revealed'));
  const observer = new IntersectionObserver(entries => {
    if (seen || !entries.some(entry => entry.isIntersecting)) return;
    seen = true;
    targets.forEach(el => {
      el.classList.remove('faq-entry-pending');
      el.classList.add('faq-entry-revealed');
    });
    observer.disconnect();
  }, {threshold: .08});
  targets.forEach(el => {
    el.classList.add('faq-entry-pending');
    el.addEventListener('animationend', event => {
      if (event.target === el && event.animationName === 'faq-entry') el.classList.remove('faq-entry-revealed');
    });
  });
  observer.observe(faq);
  motion.addEventListener('change', () => {
    if (!motion.matches) { seen = true; observer.disconnect(); clear(); }
  });
})();
