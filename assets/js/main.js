(() => {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isTouch = window.matchMedia('(hover: none), (pointer: coarse)').matches;

  /* ---------- header scroll state ---------- */
  const header = document.querySelector('.site-header');
  if (header) {
    const onScroll = () => header.classList.toggle('is-scrolled', window.scrollY > 12);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ---------- mobile nav toggle ---------- */
  const navToggle = document.querySelector('.nav-toggle');
  const navLinks = document.querySelector('.nav-links');
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      const open = navLinks.classList.toggle('is-open');
      navToggle.setAttribute('aria-expanded', String(open));
      document.body.style.overflow = open ? 'hidden' : '';
    });
    navLinks.querySelectorAll('a').forEach((a) => {
      a.addEventListener('click', () => {
        navLinks.classList.remove('is-open');
        navToggle.setAttribute('aria-expanded', 'false');
        document.body.style.overflow = '';
      });
    });
  }

  /* ---------- scroll reveal ---------- */
  const revealEls = document.querySelectorAll('[data-reveal]');
  if (revealEls.length && 'IntersectionObserver' in window && !reduceMotion) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: '0px 0px -8% 0px' }
    );
    revealEls.forEach((el, i) => {
      el.style.transitionDelay = `${Math.min(i % 4, 3) * 90}ms`;
      io.observe(el);
    });
  } else {
    revealEls.forEach((el) => el.classList.add('is-visible'));
  }

  /* ---------- parallax (hero blobs + case cards) ---------- */
  if (!reduceMotion && !isTouch) {
    const parallaxEls = document.querySelectorAll('[data-parallax]');
    if (parallaxEls.length) {
      let ticking = false;
      const update = () => {
        const y = window.scrollY;
        parallaxEls.forEach((el) => {
          const speed = parseFloat(el.dataset.parallax) || 0.15;
          el.style.transform = `translate3d(0, ${y * speed}px, 0)`;
        });
        ticking = false;
      };
      window.addEventListener(
        'scroll',
        () => {
          if (!ticking) {
            requestAnimationFrame(update);
            ticking = true;
          }
        },
        { passive: true }
      );
      update();
    }
  }

  /* ---------- custom cursor on work cards ---------- */
  if (!isTouch && !reduceMotion) {
    const cursor = document.createElement('div');
    cursor.className = 'cursor-dot';
    cursor.textContent = 'View';
    document.body.appendChild(cursor);

    let cx = 0, cy = 0;
    window.addEventListener('mousemove', (e) => {
      cx = e.clientX;
      cy = e.clientY;
      cursor.style.left = `${cx}px`;
      cursor.style.top = `${cy}px`;
    });

    document.querySelectorAll('.work-card').forEach((card) => {
      card.addEventListener('mouseenter', () => cursor.classList.add('is-active'));
      card.addEventListener('mouseleave', () => cursor.classList.remove('is-active'));
    });
  }

  /* ---------- hero mouse bubble trail ---------- */
  const hero = document.querySelector('.hero');
  if (hero && !isTouch && !reduceMotion) {
    const bubbleColors = [
      'rgba(58,169,196,0.45)',
      'rgba(255,107,78,0.4)',
      'rgba(198,183,236,0.5)',
      'rgba(127,212,230,0.5)',
    ];
    let lastSpawn = 0;
    const spawnInterval = 60;

    hero.addEventListener('mousemove', (e) => {
      const now = performance.now();
      if (now - lastSpawn < spawnInterval) return;
      lastSpawn = now;

      const rect = hero.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const size = 28 + Math.random() * 40;
      const color = bubbleColors[Math.floor(Math.random() * bubbleColors.length)];

      const bubble = document.createElement('span');
      bubble.className = 'mouse-bubble';
      bubble.style.left = `${x}px`;
      bubble.style.top = `${y}px`;
      bubble.style.width = `${size}px`;
      bubble.style.height = `${size}px`;
      bubble.style.background = `radial-gradient(circle at 30% 30%, rgba(255,255,255,0.85), ${color} 65%, transparent 78%)`;
      hero.appendChild(bubble);

      bubble.addEventListener('animationend', () => bubble.remove());
    });
  }

  /* ---------- contact form (Formspree) ---------- */
  const form = document.querySelector('#contact-form');
  if (form) {
    const status = form.querySelector('.form-status');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      const data = new FormData(form);

      if (!form.action || form.action.includes('YOUR_FORM_ID')) {
        status.textContent = 'Form isn’t wired up yet — add your Formspree endpoint in contact form action.';
        status.classList.add('visible');
        return;
      }

      submitBtn.disabled = true;
      const originalLabel = submitBtn.textContent;
      submitBtn.textContent = 'Sending…';

      try {
        const res = await fetch(form.action, {
          method: 'POST',
          body: data,
          headers: { Accept: 'application/json' },
        });
        if (res.ok) {
          status.textContent = 'Thanks — got it. I’ll get back to you within a day or two.';
          form.reset();
        } else {
          status.textContent = 'Something went wrong sending that. Try the Calendly link instead?';
        }
      } catch (err) {
        status.textContent = 'Network hiccup — mind trying again, or use the Calendly link?';
      } finally {
        status.classList.add('visible');
        submitBtn.disabled = false;
        submitBtn.textContent = originalLabel;
      }
    });
  }
})();
