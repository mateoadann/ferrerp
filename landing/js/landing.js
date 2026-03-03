/* FerrERP - Landing Page JavaScript */

document.addEventListener('DOMContentLoaded', () => {
    initNavScroll();
    initMobileMenu();
    initScrollAnimations();
    initSmoothScroll();
});

/* Efecto de scroll en la navbar */
function initNavScroll() {
    const nav = document.querySelector('.landing-nav');
    if (!nav) return;

    function updateNav() {
        if (window.scrollY > 40) {
            nav.classList.add('scrolled');
        } else {
            nav.classList.remove('scrolled');
        }
    }

    window.addEventListener('scroll', updateNav, { passive: true });
    updateNav();
}

/* Menu mobile */
function initMobileMenu() {
    const toggle = document.querySelector('.nav-hamburger');
    const menu = document.querySelector('.mobile-menu');
    if (!toggle || !menu) return;

    toggle.addEventListener('click', () => {
        const isOpen = menu.classList.toggle('open');
        toggle.querySelector('.material-symbols-rounded').textContent =
            isOpen ? 'close' : 'menu';
    });

    /* Cerrar al hacer click en un link */
    menu.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', () => {
            menu.classList.remove('open');
            toggle.querySelector('.material-symbols-rounded').textContent = 'menu';
        });
    });
}

/* Animaciones al hacer scroll (Intersection Observer) */
function initScrollAnimations() {
    const elements = document.querySelectorAll('.fade-up');
    if (!elements.length) return;

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    );

    elements.forEach((el) => observer.observe(el));
}

/* Smooth scroll para links internos */
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach((link) => {
        link.addEventListener('click', (e) => {
            const targetId = link.getAttribute('href');
            if (targetId === '#') return;

            const target = document.querySelector(targetId);
            if (!target) return;

            e.preventDefault();
            const offset = 80; /* Altura del nav */
            const top = target.getBoundingClientRect().top + window.scrollY - offset;
            window.scrollTo({ top, behavior: 'smooth' });
        });
    });
}
