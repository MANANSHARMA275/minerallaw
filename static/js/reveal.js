// Scroll-reveal via IntersectionObserver — once-only fade+rise for off-screen sections.
// No-JS safe: reveal-pending is only added after JS confirms the element is off-screen.
// Reduced-motion safe: CSS reduce block forces full visibility regardless of class state.
(function () {
  'use strict';
  if (!window.IntersectionObserver) return;

  document.addEventListener('DOMContentLoaded', function () {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.remove('reveal-pending');
          entry.target.classList.add('is-revealed');
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -40px 0px', threshold: 0.1 });

    document.querySelectorAll('[data-reveal]').forEach(function (el) {
      var rect = el.getBoundingClientRect();
      if (rect.top >= window.innerHeight) {
        el.classList.add('reveal-pending');
      }
      observer.observe(el);
    });

    // Staggered reveal: direct children of [data-reveal-stagger] cascade in
    // with a short delay between each, once the container enters the
    // viewport. Same no-JS-safe / reduced-motion-safe guarantee as above —
    // reveal-pending is only ever added by this script, never server-rendered.
    var STAGGER_MS = 90;
    var staggerObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          Array.prototype.forEach.call(entry.target.children, function (child, i) {
            setTimeout(function () {
              child.classList.remove('reveal-pending');
              child.classList.add('is-revealed');
            }, i * STAGGER_MS);
          });
          staggerObserver.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -40px 0px', threshold: 0.1 });

    document.querySelectorAll('[data-reveal-stagger]').forEach(function (container) {
      var rect = container.getBoundingClientRect();
      if (rect.top >= window.innerHeight) {
        Array.prototype.forEach.call(container.children, function (child) {
          child.classList.add('reveal-pending');
        });
      }
      staggerObserver.observe(container);
    });
  });
}());
