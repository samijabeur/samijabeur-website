/* sami jabeur – site.js
   Kleine, abhängigkeitsfreie Skripte: Menü, Cookie-Banner, Einblenden beim Scrollen,
   Galerie-Layouts (Masonry, Strips) und Lightbox. Ohne JavaScript bleibt die Seite voll lesbar. */
(function () {
  'use strict';
  var doc = document, root = doc.documentElement;
  var $ = function (s, c) { return (c || doc).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || doc).querySelectorAll(s)); };

  /* ---------- Handy-Menü ------------------------------------------------ */
  var toggle = $('.menu-toggle'), menu = $('.mobile-menu');
  function setMenu(open) {
    root.classList.toggle('menu-open', open);
    doc.body.classList.toggle('is-locked', open);
    if (toggle) { toggle.setAttribute('aria-expanded', open); toggle.setAttribute('aria-label', open ? 'Menü schließen' : 'Menü öffnen'); }
    if (!open) showPanel('root');
  }
  function showPanel(name) {
    $$('.mobile-menu__panel').forEach(function (p) { p.classList.toggle('is-active', p.dataset.panel === name); });
  }
  if (toggle && menu) {
    toggle.addEventListener('click', function () { setMenu(!root.classList.contains('menu-open')); });
    $$('[data-panel-open]').forEach(function (b) { b.addEventListener('click', function () { showPanel(b.dataset.panelOpen); }); });
    $$('.mobile-menu a').forEach(function (a) { a.addEventListener('click', function () { setMenu(false); }); });
    window.addEventListener('resize', function () { if (innerWidth >= 800) setMenu(false); });
  }
  doc.addEventListener('keydown', function (e) { if (e.key === 'Escape') setMenu(false); });

  /* ---------- Untermenü (Desktop, für Touch per Klick) ------------------- */
  $$('.site-nav .has-sub > button').forEach(function (b) {
    var li = b.parentNode;
    b.addEventListener('click', function (e) { e.stopPropagation(); var o = li.classList.toggle('is-open'); b.setAttribute('aria-expanded', o); });
    doc.addEventListener('click', function () { li.classList.remove('is-open'); b.setAttribute('aria-expanded', false); });
  });

  /* ---------- Kopfleiste schrumpft beim Scrollen (nur Handy/Tablet, per CSS) -- */
  var ticking = false;
  function onScroll() {
    if (ticking) return; ticking = true;
    requestAnimationFrame(function () { root.classList.toggle('is-scrolled', window.scrollY > 20); ticking = false; });
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------- Cookie-Banner --------------------------------------------- */
  var banner = $('.cookie-banner');
  if (banner) {
    var accepted = false;
    try { accepted = localStorage.getItem('cookie-accepted') === '1'; } catch (e) {}
    banner.hidden = accepted;
    $('button', banner).addEventListener('click', function () {
      banner.hidden = true;
      try { localStorage.setItem('cookie-accepted', '1'); } catch (e) {}
    });
  }

  /* ---------- Einblenden beim Scrollen ---------------------------------- */
  if ('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('is-in'); io.unobserve(en.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.01 });
    $$('main .cell, .gal__item').forEach(function (el) { el.classList.add('reveal'); io.observe(el); });
  }

  /* ---------- Galerie: Masonry ------------------------------------------ */
  function masonry(g) {
    var wrap = $('.gal__wrap', g), items = $$('.gal__item', wrap);
    var N = +g.dataset.cols, gutter = +g.dataset.gutter, vw = innerWidth;
    var cols = N <= 2 ? N : vw >= 1000 ? N : vw >= 800 ? Math.min(N, 3) : 2;
    var factor = N <= 2 || cols === N ? 1 : cols === 3 ? 0.75 : vw >= 600 ? 0.5 : 0.25;
    var W = wrap.clientWidth, gap = gutter * W / 2000 * factor;
    var colW = (W - gap * (cols - 1)) / cols, hs = [], i;
    for (i = 0; i < cols; i++) hs.push(0);
    items.forEach(function (it) {
      var c = hs.indexOf(Math.min.apply(null, hs));
      var h = Math.ceil(colW / +it.dataset.ar);
      it.style.setProperty('--w', colW + 'px');
      it.style.setProperty('--h', h + 'px');
      it.style.setProperty('--x', c * (colW + gap) + 'px');
      it.style.setProperty('--y', hs[c] + 'px');
      hs[c] += h + gap;
    });
    wrap.style.height = Math.max.apply(null, hs) - gap + 'px';
    g.classList.add('is-ready');
  }

  /* ---------- Galerie: Strips (Zeilen gleicher Höhe) -------------------- */
  function strips(g) {
    var wrap = $('.gal__wrap', g), items = $$('.gal__item', wrap);
    if (innerWidth < 1000) {
      items.forEach(function (it) { it.style.removeProperty('--w'); it.style.setProperty('--h', Math.ceil(wrap.clientWidth / +it.dataset.ar - 0.25) + 'px'); });
      return;
    }
    var W = wrap.clientWidth, gap = 20, T = +g.dataset.rowHeight || 300, i = 0;
    while (i < items.length) {
      var ar0 = +items[i].dataset.ar, n = Math.max(2, Math.floor(W / (T * ar0)));
      if (items.length - (i + n) < Math.ceil(n / 2)) n = items.length - i;   // keine einzelnen Rest-Bilder
      n = Math.min(n, items.length - i);
      var row = items.slice(i, i + n), sum = 0;
      row.forEach(function (it) { sum += +it.dataset.ar; });
      var h = Math.ceil((W - gap * (n - 1)) / sum);
      var avail = W - gap * (n - 1);
      row.forEach(function (it) { it.style.setProperty('--w', avail * it.dataset.ar / sum + 'px'); it.style.setProperty('--h', h + 'px'); });
      i += n;
    }
  }

  var layouts = [];
  $$('.gal--masonry').forEach(function (g) { layouts.push(function () { masonry(g); }); });
  $$('.gal--strips').forEach(function (g) { layouts.push(function () { strips(g); }); });
  function relayout() { layouts.forEach(function (f) { f(); }); }
  relayout();
  var rt; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(relayout, 60); });
  window.addEventListener('load', relayout);

  /* ---------- Lightbox -------------------------------------------------- */
  var galleries = $$('.gal[data-lightbox]');
  if (galleries.length) {
    var lb = doc.createElement('div');
    lb.className = 'lightbox'; lb.setAttribute('role', 'dialog'); lb.setAttribute('aria-modal', 'true'); lb.setAttribute('aria-label', 'Bildansicht');
    lb.innerHTML =
      '<div class="lightbox__bg"></div>' +
      '<button class="lightbox__close" aria-label="Schließen"><svg viewBox="0 0 40 40"><path d="M4.3,35.7L35.7,4.3"/><path d="M4.3,4.3l31.4,31.4"/></svg></button>' +
      '<button class="lightbox__nav lightbox__nav--prev" aria-label="Vorheriges Bild"><svg viewBox="0 0 9 16"><polyline points="7.3,14.7 2.5,8 7.3,1.2"/></svg></button>' +
      '<div class="lightbox__stage"><img alt=""></div>' +
      '<button class="lightbox__nav lightbox__nav--next" aria-label="Nächstes Bild"><svg viewBox="0 0 9 16"><polyline points="1.6,1.2 6.5,7.9 1.6,14.7"/></svg></button>';
    doc.body.appendChild(lb);
    var img = $('img', lb), prev = $('.lightbox__nav--prev', lb), next = $('.lightbox__nav--next', lb);
    var list = [], idx = 0, opener = null;

    function show(i) {
      idx = (i + list.length) % list.length;
      img.style.opacity = 0;
      var src = list[idx].href, pre = new Image();
      pre.onload = function () { img.src = src; img.alt = list[idx].alt || ''; img.style.opacity = 1; };
      pre.src = src;
      prev.hidden = next.hidden = list.length < 2;
      [list[(idx + 1) % list.length], list[(idx - 1 + list.length) % list.length]].forEach(function (n) { new Image().src = n.href; });
    }
    function open(g, i, from) {
      list = $$('.gal__item a', g).map(function (a) { return { href: a.getAttribute('href'), alt: $('img', a).alt }; });
      opener = from; lb.classList.add('is-open'); doc.body.classList.add('is-locked'); show(i); $('.lightbox__close', lb).focus();
    }
    function close() { lb.classList.remove('is-open'); doc.body.classList.remove('is-locked'); if (opener) opener.focus(); }

    galleries.forEach(function (g) {
      $$('.gal__item a', g).forEach(function (a, i) {
        a.addEventListener('click', function (e) { e.preventDefault(); open(g, i, a); });
      });
    });
    $('.lightbox__close', lb).addEventListener('click', close);
    $('.lightbox__bg', lb).addEventListener('click', close);
    $('.lightbox__stage', lb).addEventListener('click', function (e) { if (e.target !== img) close(); });
    prev.addEventListener('click', function () { show(idx - 1); });
    next.addEventListener('click', function () { show(idx + 1); });
    doc.addEventListener('keydown', function (e) {
      if (!lb.classList.contains('is-open')) return;
      if (e.key === 'Escape') close();
      else if (e.key === 'ArrowLeft') show(idx - 1);
      else if (e.key === 'ArrowRight') show(idx + 1);
    });
    var sx = null;
    lb.addEventListener('touchstart', function (e) { sx = e.touches[0].clientX; }, { passive: true });
    lb.addEventListener('touchend', function (e) {
      if (sx === null) return; var dx = e.changedTouches[0].clientX - sx; sx = null;
      if (Math.abs(dx) > 50) show(idx + (dx < 0 ? 1 : -1));
    });
  }
})();
