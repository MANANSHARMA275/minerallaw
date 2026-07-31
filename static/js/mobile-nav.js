// ============================================================
// FILE: static/js/mobile-nav.js
// PURPOSE: Hamburger toggle for the collapsible mobile nav panel (Chunk F2)
// ============================================================
(function () {
    // Must match the `lg:` breakpoint used on the nav's Tailwind classes in
    // base.html — this is what decides whether the desktop row or the
    // hamburger/mobile panel is visible.
    var LG_BREAKPOINT = 1024;

    var btn = document.getElementById('mobile-menu-btn');
    var menu = document.getElementById('mobile-menu');
    if (!btn || !menu) return;

    function closeMenu() {
        menu.classList.add('hidden');
        btn.setAttribute('aria-expanded', 'false');
    }

    function openMenu() {
        menu.classList.remove('hidden');
        btn.setAttribute('aria-expanded', 'true');
    }

    btn.addEventListener('click', function () {
        var isOpen = btn.getAttribute('aria-expanded') === 'true';
        if (isOpen) {
            closeMenu();
        } else {
            openMenu();
        }
    });

    menu.querySelectorAll('a').forEach(function (link) {
        link.addEventListener('click', closeMenu);
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeMenu();
    });

    // Phone rotated to landscape, or a desktop window widened past lg while
    // the panel was open — the desktop row becomes visible again, so the
    // mobile panel must not linger open behind/above it.
    window.addEventListener('resize', function () {
        if (window.innerWidth >= LG_BREAKPOINT) closeMenu();
    }, { passive: true });
}());
