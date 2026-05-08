/* ═══════════════════════════════════════════════════════════════════════════
   OpenOSINT Docs — docs.js
   Handles: terminal typewriter · copy buttons · active-nav tracking ·
            scroll reveal · search filter · smooth scroll offset
   ═══════════════════════════════════════════════════════════════════════════ */

'use strict';

/* ─── Terminal Typewriter ────────────────────────────────────────────────── */

const DEMO = [
  // Each entry: { html, delay (ms before appearing), typewrite (char-by-char?) }
  { html: '<span class="t-prompt">openosint ❯ </span><span class="t-cmd" id="tw-cmd"></span>', delay: 600, typewrite: 'investigate john.doe@example.com' },
  { html: '', delay: 300 },
  { html: '<span class="t-status">  ⟡ Analyzing target: email address</span>', delay: 100 },
  { html: '', delay: 400 },
  { html: '<span class="t-arrow">  › </span><span class="t-tool">check_email</span><span class="t-dim">  email </span><span class="t-val">john.doe@example.com</span>', delay: 150 },
  { html: '<span class="t-ok">    ✓ </span><span class="t-dim">valid=</span><span class="t-val">True</span>  <span class="t-dim">provider=</span><span class="t-val">Google</span>  <span class="t-dim">mx=gmail-smtp-in.l.google.com</span>', delay: 700 },
  { html: '', delay: 200 },
  { html: '<span class="t-arrow">  › </span><span class="t-tool">check_breach</span><span class="t-dim">  email </span><span class="t-val">john.doe@example.com</span>', delay: 150 },
  { html: '<span class="t-warn">    ⚠ </span><span class="t-dim">2 breaches: </span><span class="t-val">LinkedIn (2021)</span><span class="t-dim"> · </span><span class="t-val">Adobe (2013)</span>', delay: 900 },
  { html: '', delay: 200 },
  { html: '<span class="t-arrow">  › </span><span class="t-tool">check_username</span><span class="t-dim">  username </span><span class="t-val">johndoe</span>', delay: 150 },
  { html: '<span class="t-ok">    ✓ </span><span class="t-dim">6 platforms: </span><span class="t-val">GitHub · Reddit · Twitter/X · Instagram · GitLab · Dev.to</span>', delay: 1500 },
  { html: '', delay: 200 },
  { html: '<span class="t-arrow">  › </span><span class="t-tool">generate_dorks</span><span class="t-dim">  target </span><span class="t-val">john.doe@example.com</span><span class="t-dim">  type=email</span>', delay: 150 },
  { html: '<span class="t-ok">    ✓ </span><span class="t-dim">7 dork queries generated</span>', delay: 400 },
  { html: '', delay: 600 },
  { html: '<span class="t-divider">  ──────────────  REPORT  ──────────────</span>', delay: 100 },
  { html: '<span class="t-dim">  Target    </span><span class="t-val">john.doe@example.com</span>', delay: 120 },
  { html: '<span class="t-dim">  Accounts  </span><span class="t-ok">6 confirmed profiles</span>', delay: 120 },
  { html: '<span class="t-dim">  Breaches  </span><span class="t-warn">⚠ HIGH — 2 exposures</span>', delay: 120 },
  { html: '<span class="t-dim">  Dorks     </span><span class="t-dim">7 search queries ready</span>', delay: 120 },
  { html: '<span class="t-divider">  ────────────────────────────────────</span>', delay: 100 },
  { html: '', delay: 3000 }, // pause before loop
];

class TerminalAnimation {
  constructor() {
    this.output = document.getElementById('terminal-output');
    this.cursor = document.getElementById('terminal-cursor');
    if (!this.output) return;
    this._running = true;
    this._run();
  }

  stop() { this._running = false; }

  async _run() {
    while (this._running) {
      this.output.innerHTML = '';
      for (const frame of DEMO) {
        if (!this._running) return;
        await this._wait(frame.delay);
        if (!this._running) return;

        if (frame.typewrite) {
          // Render the frame HTML first (sets up the span structure)
          const line = document.createElement('div');
          line.innerHTML = frame.html;
          this.output.appendChild(line);
          const target = line.querySelector('#tw-cmd');
          if (target) await this._typewrite(target, frame.typewrite);
          line.removeAttribute('id');
          if (target) target.removeAttribute('id');
        } else if (frame.html !== '') {
          const line = document.createElement('div');
          line.innerHTML = frame.html;
          this.output.appendChild(line);
        } else {
          this.output.appendChild(document.createElement('div'));
        }

        // Auto-scroll
        this.output.scrollTop = this.output.scrollHeight;
      }
    }
  }

  async _typewrite(el, text, speed = 45) {
    for (const char of text) {
      if (!this._running) return;
      el.textContent += char;
      await this._wait(speed + Math.random() * 30);
    }
  }

  _wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/* ─── Copy Buttons ───────────────────────────────────────────────────────── */

function initCopyButtons() {
  document.querySelectorAll('[data-copy-target]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const pre = btn.closest('.code-wrap')?.querySelector('pre');
      if (!pre) return;
      const text = pre.textContent.trim();
      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.textContent = 'Copy';
          btn.classList.remove('copied');
        }, 2000);
      } catch {
        btn.textContent = 'Error';
        setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
      }
    });
  });
}

/* ─── Active Nav Tracking ────────────────────────────────────────────────── */

function initActiveNav() {
  const sections = document.querySelectorAll('section[id], div[id^="providers-"]');
  const links = document.querySelectorAll('.nav-item[data-section]');
  if (!sections.length || !links.length) return;

  const setActive = (id) => {
    links.forEach(l => l.classList.remove('active'));
    const match = document.querySelector(`.nav-item[data-section="${id}"]`);
    if (match) {
      match.classList.add('active');
      // Scroll nav item into view within sidebar if needed
      const nav = document.getElementById('sidebar-nav');
      if (nav) {
        const itemTop = match.offsetTop;
        const navScroll = nav.scrollTop;
        const navH = nav.clientHeight;
        if (itemTop < navScroll || itemTop > navScroll + navH - 40) {
          nav.scrollTo({ top: itemTop - navH / 2, behavior: 'smooth' });
        }
      }
    }
  };

  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) setActive(e.target.id);
    });
  }, { rootMargin: '-15% 0% -70% 0%', threshold: 0 });

  sections.forEach(s => observer.observe(s));
}

/* ─── Scroll Reveal ──────────────────────────────────────────────────────── */

function initScrollReveal() {
  const sections = document.querySelectorAll('.reveal-section');
  if (!sections.length) return;

  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('revealed');
        observer.unobserve(e.target);
      }
    });
  }, { rootMargin: '0px 0px -10% 0px', threshold: 0.05 });

  sections.forEach(s => observer.observe(s));
}

/* ─── Smooth Scroll (offset for sidebar / mobile header) ────────────────── */

function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', e => {
      const href = anchor.getAttribute('href');
      if (href === '#') return;
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();

      const isMobile = window.innerWidth < 1024;
      const offset = isMobile ? 60 : 24;
      const top = target.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: 'smooth' });

      // Close mobile sidebar
      if (isMobile && window._alpine) {
        // Let Alpine handle it via x-data
      }
    });
  });
}

/* ─── Docs Search ────────────────────────────────────────────────────────── */

function initSearch() {
  const input = document.getElementById('docs-search');
  if (!input) return;

  const navItems = document.querySelectorAll('#sidebar-nav .nav-item, #sidebar-nav .nav-group');

  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();

    if (!q) {
      navItems.forEach(el => el.style.display = '');
      return;
    }

    navItems.forEach(item => {
      if (item.classList.contains('nav-group')) {
        // Show group if any sub-item matches
        const subs = item.querySelectorAll('.nav-item');
        let anyVisible = false;
        subs.forEach(sub => {
          const matches = sub.textContent.toLowerCase().includes(q);
          sub.style.display = matches ? '' : 'none';
          if (matches) anyVisible = true;
        });
        item.style.display = anyVisible ? '' : 'none';
      } else if (!item.closest('.nav-group')) {
        item.style.display = item.textContent.toLowerCase().includes(q) ? '' : 'none';
      }
    });
  });
}

/* ─── Splitting.js Hero Title ─────────────────────────────────────────────── */

function initSplitting() {
  if (typeof Splitting === 'undefined') return;
  const title = document.getElementById('hero-title');
  if (!title) return;

  // Splitting.js splits into .char spans with CSS custom property --char-index
  // Our CSS does the animation via char-in keyframe
  Splitting({ target: title, by: 'chars' });

  // Add staggered class per half (OPEN vs OSINT)
  title.querySelectorAll('.char').forEach(ch => {
    ch.style.animationDelay = `calc(0.04s * var(--char-index))`;
  });
}

/* ─── Prism re-highlight (called after Alpine/DOM changes) ──────────────── */

function rehighlight() {
  if (typeof Prism !== 'undefined') Prism.highlightAll();
}

/* ─── Init ───────────────────────────────────────────────────────────────── */

function init() {
  initCopyButtons();
  initActiveNav();
  initScrollReveal();
  initSmoothScroll();
  initSearch();

  // Hero terminal — start after a short delay so page has painted
  setTimeout(() => { new TerminalAnimation(); }, 400);

  // Splitting.js runs after fonts are ready for best results
  if (document.fonts) {
    document.fonts.ready.then(initSplitting);
  } else {
    initSplitting();
  }

  // Prism highlight runs after a tick to find all code blocks
  setTimeout(rehighlight, 200);
}

// DOMContentLoaded or immediate if already loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// Re-highlight after Alpine mutates DOM (e.g. theme change reveals code blocks)
document.addEventListener('alpine:initialized', rehighlight);
