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
  });
}());
