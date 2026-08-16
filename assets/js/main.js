(() => {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isTouch = window.matchMedia('(hover: none), (pointer: coarse)').matches;

  /* ---------- obfuscated email (defeats basic scrapers; the raw
     address never appears in page source, only assembled here) ---------- */
  document.querySelectorAll('.js-email').forEach((el) => {
    const link = document.createElement('a');
    const email = `${el.dataset.u}@${el.dataset.d}`;
    link.href = `mailto:${email}`;
    link.textContent = email;
    el.replaceWith(link);
  });

  /* ---------- obfuscated phone (same idea as the email above) ---------- */
  document.querySelectorAll('.js-phone').forEach((el) => {
    const link = document.createElement('a');
    const phone = `${el.dataset.cc} ${el.dataset.n}`;
    link.href = `tel:${el.dataset.cc}${el.dataset.n}`;
    link.textContent = phone;
    el.replaceWith(link);
  });

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

  /* ---------- robust same-page anchor scrolling ----------
     Fonts load non-blocking (media="print" swap) for performance, so a
     click right after page load can compute a scroll target against
     fallback-font text metrics, then land short/long once the real font
     swaps in and text reflows mid-scroll. Waiting for document.fonts.ready
     before scrolling avoids that without reintroducing render-blocking
     fonts (only the scroll is delayed, not the initial paint). */
  document.querySelectorAll('a[href*="#"]').forEach((link) => {
    let url;
    try {
      url = new URL(link.getAttribute('href'), location.href);
    } catch (err) {
      return;
    }
    if (url.pathname !== location.pathname || !url.hash) return;
    link.addEventListener('click', (e) => {
      const target = document.querySelector(url.hash);
      if (!target) return;
      e.preventDefault();
      const go = () => target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
      const ready = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
      ready.then(go);
      history.pushState(null, '', url.hash);
    });
  });

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

    // mouseleave doesn't fire when a card scrolls out from under a stationary
    // pointer, so the dot can get stuck active — clear it on scroll.
    window.addEventListener('scroll', () => cursor.classList.remove('is-active'), { passive: true });
  }

  /* ---------- hero mouse bubble trail ---------- */
  const hero = document.querySelector('.hero');
  if (hero && !isTouch && !reduceMotion) {
    const bubbleColors = [
      'rgba(58,169,196,0.45)',
      'rgba(255,107,78,0.425)',
      'rgba(198,183,236,0.46)',
      'rgba(127,212,230,0.46)',
    ];
    let lastSpawn = 0;
    const spawnInterval = 55;

    hero.addEventListener('mousemove', (e) => {
      const now = performance.now();
      if (now - lastSpawn < spawnInterval) return;
      lastSpawn = now;

      const rect = hero.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const size = 36 + Math.random() * 48;
      const color = bubbleColors[Math.floor(Math.random() * bubbleColors.length)];

      const bubble = document.createElement('span');
      bubble.className = 'mouse-bubble';
      bubble.style.left = `${x}px`;
      bubble.style.top = `${y}px`;
      bubble.style.width = `${size}px`;
      bubble.style.height = `${size}px`;
      bubble.style.background = `radial-gradient(circle at 30% 30%, rgba(255,255,255,0.5), ${color} 72%, transparent 90%)`;
      hero.appendChild(bubble);

      bubble.addEventListener('animationend', () => bubble.remove());
    });
  }

  /* ---------- contact form (Formspree) ---------- */
  const form = document.querySelector('#contact-form');
  if (form) {
    const status = form.querySelector('.form-status');
    const msg = (key, fallback) => form.dataset[key] || fallback;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      const data = new FormData(form);

      if (!form.action || form.action.includes('YOUR_FORM_ID')) {
        status.textContent = msg('msgNotWired', 'Form isn’t wired up yet — add your Formspree endpoint in contact form action.');
        status.classList.add('visible');
        return;
      }

      // Second honeypot, checked client-side under a name that doesn't
      // signal "trap" — a bot filling every field in gets a fake success
      // instead of a rejection that would tip it off.
      const decoy = form.querySelector('.hp-decoy');
      if (decoy && decoy.value) {
        status.textContent = msg('msgSuccess', 'Thanks — got it. I’ll get back to you within a day or two.');
        status.classList.add('visible');
        form.reset();
        return;
      }

      if (window.grecaptcha && form.querySelector('.g-recaptcha') && !grecaptcha.getResponse()) {
        status.textContent = msg('msgRecaptcha', "Please confirm you're not a robot before sending.");
        status.classList.add('visible');
        return;
      }

      submitBtn.disabled = true;
      const originalLabel = submitBtn.textContent;
      submitBtn.textContent = msg('msgSending', 'Sending…');

      try {
        const res = await fetch(form.action, {
          method: 'POST',
          body: data,
          headers: { Accept: 'application/json' },
        });
        if (res.ok) {
          status.textContent = msg('msgSuccess', 'Thanks — got it. I’ll get back to you within a day or two.');
          form.reset();
        } else {
          status.textContent = msg('msgError', 'Something went wrong sending that. Try the Calendly link instead?');
        }
      } catch (err) {
        status.textContent = msg('msgNetwork', 'Network hiccup — mind trying again, or use the Calendly link?');
      } finally {
        status.classList.add('visible');
        submitBtn.disabled = false;
        submitBtn.textContent = originalLabel;
        if (window.grecaptcha && form.querySelector('.g-recaptcha')) grecaptcha.reset();
      }
    });
  }
})();
