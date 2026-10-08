/* Safe no-browser checks: node verification/test_landing_middle_refinements.js
 * Reads source only. No screenshots, server, evidence, or external dependencies.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/landing.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'frontend/landing.css'), 'utf8');
function fixture({reduced = false, observerAvailable = true, code = source} = {}) {
  function target(x, y, width, height) {
    const values = {}, classes = new Set(), listeners = {};
    return {
      style: {values, setProperty: (key, value) => { values[key] = value; }, removeProperty: key => { delete values[key]; }},
      classList: {add: (...names) => names.forEach(n => classes.add(n)), remove: (...names) => names.forEach(n => classes.delete(n)), contains: n => classes.has(n)},
      classes, offsetWidth: width, offsetHeight: height,
      getBoundingClientRect: () => ({x, y, width, height, left: x, top: y, right: x + width, bottom: y + height}),
      addEventListener: (name, fn) => { (listeners[name] ||= []).push(fn); },
      emit: (name, event) => (listeners[name] || []).forEach(fn => fn(event)),
    };
  }
  const events = {}, frames = new Map(), observers = [], media = [];
  let time = 0, nextFrame = 0;
  const rings = Array.from({length: 4}, () => target(10, 10, 300, 300));
  const artwork = target(10, 10, 300, 300), tooth = target(10, 10, 300, 300);
  Object.assign(tooth, {complete: true, naturalWidth: 100, closest: () => artwork});
  const card = target(700, 900, 600, 200), story = target(700, 1200, 600, 600);
  const steps = Array.from({length: 4}, (_, i) => target(100, 1200 + i * 80, 400, 50));
  const home = target(0, 0, 1440, 2000);
  home.classList.add('active');
  home.querySelector = s => s.includes('product') ? card : story;
  home.querySelectorAll = s => s.includes('orbits') ? rings : steps;
  class Observer {
    constructor(callback, options) { this.callback = callback; this.options = options; this.observed = new Set(); this.disconnected = false; observers.push(this); }
    observe(el) { this.observed.add(el); }
    unobserve(el) { this.observed.delete(el); }
    disconnect() { this.disconnected = true; this.observed.clear(); }
    intersect(el, isIntersecting = true) { this.callback([{target: el, isIntersecting}]); }
  }
  const context = {
    Math, Set,
    matchMedia(query) {
      const m = {query, matches: !reduced, listener: () => {}, addEventListener: (_, fn) => { m.listener = fn; }};
      media.push(m); return m;
    },
    requestAnimationFrame: fn => { frames.set(++nextFrame, fn); return nextFrame; },
    cancelAnimationFrame: id => frames.delete(id),
    window: {addEventListener: (name, fn) => { events[name] = fn; }},
    document: {
      hidden: false, getElementById: id => id === 'view-home' ? home : tooth,
      documentElement: {addEventListener: (name, fn) => { events[name] = fn; }},
      addEventListener: (name, fn) => { events[name] = fn; },
    },
  };
  if (observerAvailable) context.IntersectionObserver = Observer;
  vm.runInNewContext(code, context);
  function tick() { const queued = [...frames.values()]; frames.clear(); time += 16; queued.forEach(fn => fn(time)); }
  function settle() { for (let i = 0; frames.size && i < 350; i++) tick(); assert.equal(frames.size, 0, 'shared scheduler must settle'); }
  function move(x, y) { events.pointermove({pointerType: 'mouse', clientX: x, clientY: y}); }
  return {card, story, steps, rings, artwork, tooth, home, events, frames, observers, media, tick, settle, move};
}

// Entry is one-time, even if the observer delivers redundant intersections.
{
  const f = fixture(), observer = f.observers[0];
  assert.equal(observer.options.threshold, .08);
  assert(f.card.classes.has('middle-entry-pending'));
  assert(f.story.classes.has('middle-entry-pending'));
  assert.equal(f.frames.size, 0, 'observer adds no animation loop');
  observer.intersect(f.card, false);
  assert(f.card.classes.has('middle-entry-pending'));
  observer.intersect(f.card);
  assert(!observer.observed.has(f.card));
  assert(f.card.classes.has('middle-entry-revealed'));
  f.card.emit('animationend', {target: f.card, animationName: 'middle-entry'});
  assert(!f.card.classes.has('middle-entry-revealed'));
  observer.intersect(f.card);
  assert(!f.card.classes.has('middle-entry-revealed'), 'scrolling cannot repeat reveal');
  observer.intersect(f.story);
  assert(observer.disconnected);
  assert(f.story.classes.has('middle-entry-revealed'));
  f.story.emit('animationend', {target: f.story, animationName: 'middle-entry'});
  assert.equal(f.story.classes.size, 0, 'original resting styles restored');
}
// Reduced motion, unavailable observer, and preference changes leave content visible.
for (const options of [{reduced: true}, {observerAvailable: false}]) {
  const f = fixture(options);
  assert.equal(f.observers.length, 0);
  assert.equal(f.card.classes.size + f.story.classes.size, 0);
}
{
  const f = fixture();
  f.observers[0].intersect(f.card);
  f.media[1].matches = false; f.media[1].listener();
  assert(f.observers[0].disconnected);
  assert.equal(f.card.classes.size + f.story.classes.size, 0);
  f.media[1].matches = true; f.media[1].listener();
  assert.equal(f.card.classes.size + f.story.classes.size, 0, 'no restart after preference change');
}
// Only nearest step text responds; existing neighboring icon proximity is preserved.
{
  const f = fixture();
  f.move(350, 1305); f.tick();
  const early = Number(f.steps[1].style.values['--step-text-light']);
  assert(early > 0 && early < 1);
  f.settle();
  assert.equal(f.steps[1].style.values['--step-text-light'], '1.0000');
  for (const i of [0, 2, 3]) assert(!f.steps[i].style.values['--step-text-light']);
  f.move(350, 1285); f.settle();
  assert(Number(f.steps[0].style.values['--local-light']) > 0, 'existing icon proximity remains');
  assert(!f.steps[0].style.values['--step-text-light'], 'neighboring text stays at rest');
  f.move(350, 1385); f.settle();
  assert(!f.steps[1].style.values['--step-text-light']);
  assert.equal(f.steps[2].style.values['--step-text-light'], '1.0000');
  assert.equal(f.frames.size, 0);
  f.events.pointerleave(); f.tick();
  assert(Number(f.steps[2].style.values['--step-text-light']) > 0, 'smooth fade');
  f.settle();
  assert(f.steps.every(el => !el.style.values['--step-text-light']));
  f.move(350, 1305); f.settle();
  f.media[0].matches = false; f.media[0].listener();
  assert(f.steps.every(el => !el.style.values['--step-text-light']));
  assert(f.steps.every(el => !el.style.scale && !el.style.translate));
}
// CSS changes involve only color, relative composition offset, opacity and translate.
const additions = css.slice(css.indexOf('/* Approved middle refinements:'));
assert(additions.includes('.landing-story { top: -22px; }'));
assert(additions.includes('opacity: .9; translate: 0 10px'));
assert(additions.includes('520ms cubic-bezier(.22, 1, .36, 1) both'));
assert(additions.includes('animation-delay: 80ms'));
assert(additions.includes('prefers-reduced-motion: no-preference'));
assert(additions.includes('* 18%') && additions.includes('* 8%'));
assert(!/[;{]\s*(?:scale|rotate|rotation|blur|filter|font\S*|line-height|letter-spacing|width|height|padding|margin|background|text-shadow)\s*:/.test(additions));
console.log('PASS: one-time entry and cleanup; reduced-motion and observer fallback; nearest-step text, smooth fade and reset; unchanged typography metrics and layout footprint by CSS inspection.');
