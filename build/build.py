#!/usr/bin/env python3
"""Baut die Website (reines HTML/CSS/JS) aus den Dateien im Repository.

    python3 build/build.py                 -> Ergebnis in dist/
    python3 build/build.py --out ordner    -> Ergebnis in einem anderen Ordner
    python3 build/build.py --local         -> Vorschau, die per Doppelklick auf index.html funktioniert

Eingaben:
    layout/*.json            festes Raster der bestehenden Seiten (Positionen, Größen) – ändert sich selten
    content/pages/*.json     Texte, Bilder, Videos der bestehenden Seiten (im CMS bearbeitbar)
    content/new-pages/*.json neue Seiten, die du im CMS anlegst
    content/site.json        Website-Einstellungen (Fußzeile, Domain, Social-Links, Cookie-Text)
    content/navigation.json  Menü
    media/images, media/video  Originale
    theme/                   Stylesheet, Skript, Schrift, Icons
"""
import argparse
import html
import json
import math
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from markup import to_html, slugify          # noqa: E402
from media import Media, warn, basename      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESERVED = {'assets', 'media', '404', 'index', 'layout', 'content', 'theme', 'build', 'dist'}
GAL_RATIO = {'four-three': '4/3', 'standard-vertical': '2/3', 'square': '1/1'}

# Größen der flexiblen Bausteine -> Raster-Spalten (Handy / Desktop)
SIZE_COLS = {
    'full': ('1/1/2/11', '1/1/2/27'),
    'wide': ('1/2/2/10', '1/3/2/25'),
    'medium': ('1/2/2/10', '1/7/2/21'),
    'small': ('1/3/2/9', '1/9/2/19'),
}
RATIO_PAD = {'16:9': '56.25%', '4:3': '75%', '1:1': '100%', '3:2': '66.667%', '9:16': '177.778%'}
TEXT_STYLE = {'title-xl': ('h3', False), 'title': ('h2', False), 'lead': ('h1', False),
              'body': ('h4', False), 'small': ('p', True)}
GAP_TOKEN = {'none': 0, 'small': 10, 'medium': 20}
SPACER = {'small': 'var(--pad-xs)', 'medium': 'var(--pad-s)', 'large': 'var(--pad-m)'}


def load(p, default=None):
    try:
        with open(os.path.join(ROOT, p), encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def esc(s):
    return html.escape(s or '', quote=True)


class Builder:
    def __init__(self, out, local=False, cache=None):
        self.out = out
        self.local = local
        self.site = load('content/site.json', {})
        self.nav = load('content/navigation.json', {'items': []})
        self.domain = self.site.get('domain', '')
        self.base = ('https://' + self.domain) if self.domain else ''
        self.media = None
        self.dims = load('layout/image-dims.json', {})
        self.cache = cache

    # ------------------------------------------------------------------ URLs
    def url(self, R, slug):
        slug = (slug or '').strip('/')
        if self.local:
            return R + (slug + '/' if slug else '') + 'index.html'
        return R + slug + '/' if slug else (R or './')

    def rewrite_links(self, h, R):
        def f(m):
            href = m.group(1)
            if href.startswith('/') and not href.startswith('//'):
                return 'href="%s"' % self.url(R, href.strip('/'))
            if href and not re.match(r'^(https?:|mailto:|tel:|#|\.|\?)', href) and '/' not in href[:1]:
                return 'href="%s"' % self.url(R, href.strip('/'))
            return m.group(0)
        return re.sub(r'href="([^"]*)"', f, h)

    def link_href(self, R, link):
        if not link: return None
        if re.match(r'^(https?:|mailto:|tel:|#)', link): return link
        return self.url(R, link.strip('/'))

    # ------------------------------------------------------------------ Bilder
    def img_tag(self, R, ref, sizes, alt='', style='', eager=False, cls='', d=None, wh=None):
        d = d or self.media.image(ref)
        if d is None: return ''
        wh = wh or (d['w'], d['h'])
        ss = ['%s%s%s %dw' % (R, 'assets/img/', v[1], v[0]) for v in d['variants']]
        ss.append('%sassets/img/%s %dw' % (R, d['orig'], d['w']))
        return '<img%s src="%sassets/img/%s" srcset="%s" sizes="%s" width="%d" height="%d" alt="%s"%s%s>' % (
            (' class="%s"' % cls) if cls else '', R, d['orig'], ', '.join(ss), sizes, wh[0], wh[1], esc(alt),
            (' style="%s"' % style) if style else '',
            ' fetchpriority="high"' if eager else ' loading="lazy" decoding="async"')

    @staticmethod
    def focal(f):
        try:
            x, y = [float(v) * 100 for v in f.split(',')]
            return 'object-position:%g%% %g%%' % (round(x, 2), round(y, 2))
        except Exception:
            return ''

    @staticmethod
    def span_sizes(d):
        try:
            a, b = [int(x) for x in d.split('/')][1:4:2]
            pct = (b - a) / 24 * 100
            return '(min-width: 768px) min(%dpx, %dvw), 100vw' % (round(1200 * (b - a) / 24), round(pct))
        except Exception:
            return '100vw'

    # ------------------------------------------------------------------ Bausteine der bestehenden Seiten
    def render_block(self, R, b, c):
        st = []
        if 'm' in b: st.append('--m:%s' % b['m'])
        if 'd' in b: st.append('--d:%s' % b['d'])
        if 'zm' in b: st.append('--zm:%d' % b['zm'])
        if 'zd' in b: st.append('--zd:%d' % b['zd'])
        if b.get('jc_m'): st.append('--jm:%s' % b['jc_m'])
        if b.get('jc_d'): st.append('--jd:%s' % b['jc_d'])
        cls = ['cell']
        t = b['type']
        inner = ''
        if t in ('text', 'footer'):
            if t == 'footer':
                text = self.site.get('footer', '')
            elif b.get('link'):
                c = c or {}
                text = ('[%s](%s)' % (c.get('text', ''), c.get('link', ''))) if c.get('text') else ''
            else:
                text = c if isinstance(c, str) else ''
            if not text.strip(): return ''
            if b.get('fit'):
                cls.append('fit'); st.append('--fit:%g' % b['fit'])
            if t == 'footer': cls.append('footer-text')
            if b.get('tile'): cls.append('tile')
            k = []
            if b.get('align'): k.append('ta-' + b['align'])
            if b.get('left_m'): k.append('ta-left-m')
            if b.get('small'): k.append('small')
            inner = '<%s%s>%s</%s>' % (b['tag'], (' class="%s"' % ' '.join(k)) if k else '',
                                       self.rewrite_links(to_html(text), R), b['tag'])
        elif t == 'image':
            c = c or {}
            im = self.img_tag(R, c.get('image'), self.span_sizes(b.get('d', '')), c.get('alt', ''), self.focal(c.get('focal') or '0.5,0.5'))
            if not im: return ''
            cls.append('cell--media')
            inner = im
        elif t == 'bgvideo':
            inner = self.video_tag(R, (c or {}).get('video'), 'loop')
            if not inner: return ''
            cls.append('cell--media cell--bgvideo')
            if b.get('fit') == 'contain': cls.append('cell--vcontain')
        elif t == 'film':
            inner = self.video_tag(R, (c or {}).get('video'), 'player')
            if not inner: return ''
            cls.append('cell--media cell--film')
            st.append('--film-pad:%s' % b.get('film_pad', '56.25%'))
        elif t == 'social':
            cls.append('social')
            for s in self.site.get('social', []):
                if s.get('network') in self.icons and s.get('url'):
                    label = {'instagram': 'Instagram', 'linkedin': 'LinkedIn'}.get(s['network'], s['network'])
                    inner += '<a href="%s" target="_blank" rel="noopener" aria-label="%s"><svg viewBox="0 0 64 64" aria-hidden="true"><use href="#i-%s"/></svg></a>' % (esc(s['url']), label, s['network'])
        return '<div class="%s" style="%s">%s</div>' % (' '.join(cls), ';'.join(st), inner)

    def video_tag(self, R, ref, mode, title=None, poster_ref=None):
        """<video>-Element für ein Video aus media/video (oder '' wenn die Datei fehlt)."""
        v = self.media.video(ref)
        if not v: return ''
        name, poster = v
        ps = ''
        if poster_ref:
            pd = self.media.image(poster_ref)
            if pd: ps = ' poster="%sassets/img/%s"' % (R, pd['orig'])
        if not ps and poster:
            ps = ' poster="%sassets/video/%s"' % (R, poster)
        if mode == 'loop':
            return ('<video src="%sassets/video/%s"%s autoplay muted loop playsinline '
                    'preload="metadata" aria-hidden="true"></video>') % (R, name, ps)
        t = title or re.sub(r'^film-', '', os.path.splitext(name)[0])
        return ('<video src="%sassets/video/%s"%s controls playsinline '
                'preload="none" title="%s"></video>') % (R, name, ps, esc(t))

    def render_gallery(self, R, items, g):
        t = g['type']
        wcls = {'full': 'gal--full', 'inset': 'gal--inset', 'full-bleed': 'gal--bleed'}[g['width']]
        attrs = ' data-lightbox' if g.get('lightbox') else ''
        st = ['--g:%d' % g['gutter']]
        if g.get('cols'): st.append('--cols:%d' % g['cols'])
        if t == 'grid': st.append('--ar:%s' % GAL_RATIO[g['ratio']])
        if t == 'masonry': attrs += ' data-cols="%d" data-gutter="%d"' % (g['cols'], g['gutter'])
        if t == 'strips': attrs += ' data-row-height="%d"' % g['row_height']
        n = g.get('cols') or 2
        if t == 'strips': sizes = '(min-width: 1000px) 50vw, 100vw'
        else:
            base = '100vw' if g['width'] == 'full-bleed' else 'min(1200px, 96vw)'
            sizes = '(min-width: 1000px) calc(%s / %d), (min-width: 800px) calc(%s / %d), 50vw' % (base, n, base, min(n, 3))
        out = ''
        for it in items:
            if isinstance(it, str): it = {'image': it}          # Bilder-Listen im CMS sind einfache Pfade
            d = self.media.image(it.get('image'))
            if d is None: continue
            wh = self.dims.get(basename(it.get('image')), (d['w'], d['h']))   # bei den ursprünglichen Bildern: die im Original angegebenen Maße
            ar = '%.5f' % (wh[0] / wh[1])
            im = self.img_tag(R, None, sizes, it.get('alt', ''), self.focal(it.get('focal') or '0.5,0.5') if t == 'grid' else '', d=d, wh=wh)
            if g.get('lightbox'):
                out += '<figure class="gal__item" data-ar="%s"><a href="%sassets/img/%s">%s</a></figure>' % (ar, R, d['orig'], im)
            else:
                out += '<figure class="gal__item is-static" data-ar="%s">%s</figure>' % (ar, im)
        if not out: return ''
        return ('<section class="section"><div class="gal gal--%s %s"%s style="%s"><div class="gal__wrap">%s</div></div></section>'
                % (t, wcls, attrs, ';'.join(st), out))

    def render_section(self, R, sec, c, first, new_tiles=None):
        if sec['kind'] == 'gallery':
            return self.render_gallery(R, (c or {}).get('images', []), sec['gallery'])
        cls = ['section', 'section--' + sec['height'], 'section--' + sec['valign']]
        if first and not sec.get('hero'): cls.append('section--first')
        st = []
        if sec.get('pt'): st.append('--pt:var(--pad-%s)' % sec['pt'])
        if sec.get('pb'): st.append('--pb:var(--pad-%s)' % sec['pb'])
        if sec.get('credits_h1'):
            cls.append('credits'); st.append('--credits-h1:%dpx' % sec['credits_h1'])
        if sec.get('intro'): cls.append('section--intro')
        bg = ''
        if sec.get('hero'):
            cls.append('section--hero')
            b = (c or {}).get('bg') or {}
            bg = '<div class="section__bg">%s</div>' % self.img_tag(R, b.get('image'), '100vw', b.get('alt', ''),
                                                                    self.focal(b.get('focal') or '0.5,0.5'), eager=True)
        g = sec['grid']
        rows_m, rows_d = g['rows_m'], g['rows_d']
        cells = ''.join(self.render_block(R, b, (c or {}).get(b.get('key'))) for b in sec['blocks'])
        slots = sec.get('tile_slots')
        if slots and new_tiles:
            # Neue Kacheln: am Rechner unter der gewählten Spalte (gleicher Abstand wie bei den anderen),
            # am Handy der Reihe nach unter allen bisherigen Kacheln.
            nxt = dict(slots['start'])
            span = slots['rows']
            for it in new_tiles:
                if not isinstance(it, dict) or not (it.get('title') or it.get('image') or it.get('video')): continue
                side = 'right' if it.get('place') == 'right' else 'left'
                r = nxt[side]
                nxt[side] = r + span
                rows_d = max(rows_d, r + span - 1)
                c1, c2 = (14, 27) if side == 'right' else (1, 14)
                rows_m += 1
                cells += self.tile_cells(R, it, '%d/2/%d/10' % (rows_m, rows_m + 1), '%d/%d/%d/%d' % (r, c1, r + span, c2), cls='cell--slot')
        gst = ['--rows-m:%d' % rows_m, '--rows-d:%d' % rows_d, '--rg:%gpx' % g['row_gap'], '--cg:%gpx' % g['col_gap']]
        return '<section class="%s"%s>%s<div class="grid" style="%s">%s</div></section>' % (
            ' '.join(cls), (' style="%s"' % ';'.join(st)) if st else '', bg, ';'.join(gst), cells)

    # ------------------------------------------------------------------ Flexible Bausteine (neue Seiten, "Weitere Inhalte")
    def flex_section(self, cells, rows_m=1, rows_d=1, rg=0, cg=0, cls='', pad=('xs', 'xs'), first=False, valign='top', extra_style=''):
        c = ['section', 'section--custom', 'section--' + valign, 'flex']
        if cls: c.append(cls)
        if first: c.append('section--first')
        st = ['--pt:var(--pad-%s)' % pad[0], '--pb:var(--pad-%s)' % pad[1]]
        if extra_style: st.append(extra_style)
        return '<section class="%s" style="%s"><div class="grid" style="--rows-m:%d;--rows-d:%d;--rg:%gpx;--cg:%gpx">%s</div></section>' % (
            ' '.join(c), ';'.join(st), rows_m, rows_d, rg, cg, cells)

    def render_flex(self, R, blocks, first_is_page_start=False):
        out = ''
        first = first_is_page_start
        for b in blocks or []:
            if not isinstance(b, dict): continue
            t = b.get('type')
            fn = getattr(self, 'flex_' + (t or '').replace('-', '_'), None)
            if fn is None:
                warn('Unbekannter Baustein-Typ "%s" wird übersprungen.' % t)
                continue
            try:
                s = fn(R, b, first)
            except Exception as e:          # ein kaputter Baustein soll nicht die ganze Website blockieren
                warn('Der Baustein "%s" konnte nicht dargestellt werden und wird übersprungen (%s: %s).' % (t, type(e).__name__, e))
                continue
            if s:
                out += s
                first = False
        return out

    def flex_text(self, R, b, first):
        text = b.get('text') or ''
        if not text.strip(): return ''
        tag, small = TEXT_STYLE.get(b.get('style') or 'body', ('h4', False))
        k = ['ta-' + (b.get('align') or 'center')]
        if small: k.append('small')
        cell = '<div class="cell" style="--m:1/2/2/10;--d:1/2/2/26"><%s class="%s">%s</%s></div>' % (
            tag, ' '.join(k), self.rewrite_links(to_html(text), R), tag)
        return self.flex_section(cell, first=first)

    def flex_image(self, R, b, first):
        d = self.media.image(b.get('image'))
        if d is None: return ''
        m, dd = SIZE_COLS.get(b.get('size') or 'wide', SIZE_COLS['wide'])
        pad = '%.3f%%' % (d['h'] / d['w'] * 100)
        sizes = '(min-width: 768px) %dvw, 100vw' % {'full': 100, 'wide': 92, 'medium': 58, 'small': 42}.get(b.get('size') or 'wide', 92)
        im = self.img_tag(R, None, sizes, b.get('alt', ''), d=d)
        cell = '<div class="cell cell--media cell--ratio" style="--m:%s;--d:%s;--ratio:%s;--jm:center;--jd:center">%s</div>' % (m, dd, pad, im)
        return self.flex_section(cell, first=first, pad=('xs', 'xs'))

    def flex_film(self, R, b, first):
        mode = 'loop' if b.get('mode') == 'loop' else 'player'
        vt = self.video_tag(R, b.get('video'), mode, title=b.get('title'), poster_ref=b.get('poster'))
        if not vt: return ''
        m, dd = SIZE_COLS.get(b.get('size') or 'wide', SIZE_COLS['wide'])
        pad = RATIO_PAD.get(b.get('ratio') or '16:9', '56.25%')
        cell = '<div class="cell cell--media cell--film" style="--m:%s;--d:%s;--film-pad:%s;--jm:center;--jd:center">%s</div>' % (m, dd, pad, vt)
        return self.flex_section(cell, first=first)

    def flex_gallery(self, R, b, first):
        items = [i for i in (b.get('images') or []) if (i.get('image') if isinstance(i, dict) else i)]
        kind = {'masonry': 'masonry', 'grid': 'grid', 'strips': 'strips'}.get(b.get('layout') or 'masonry', 'masonry')
        try: cols = max(1, min(6, int(b.get('columns') or 3)))
        except (TypeError, ValueError): cols = 3
        g = {'type': kind, 'gutter': GAP_TOKEN.get(b.get('gap') or 'small', 10), 'cols': None if kind == 'strips' else cols,
             'width': {'full-bleed': 'full-bleed', 'inset': 'inset', 'full': 'full'}.get(b.get('width') or 'inset', 'inset'),
             'lightbox': bool(b.get('lightbox', True)), 'ratio': {'4:3': 'four-three', '2:3': 'standard-vertical', '1:1': 'square'}.get(b.get('ratio') or '4:3', 'four-three'),
             'row_height': 300}
        if g['gutter'] == 0 and g['width'] == 'inset': g['width'] = 'inset'
        return self.render_gallery(R, items, g)

    def flex_credits(self, R, b, first):
        rows = [r for r in (b.get('rows') or []) if (r.get('role') or r.get('names'))]
        if not rows: return ''
        cells = ''
        for i, r in enumerate(rows):
            n = 3 * i + 1
            if r.get('role'):
                cells += '<div class="cell" style="--m:%d/2/%d/5;--d:%d/8/%d/13"><h3 class="ta-right">%s</h3></div>' % (
                    n, n + 2, n, n + 2, self.rewrite_links(to_html(r['role']), R))
            if r.get('names'):
                cells += '<div class="cell" style="--m:%d/6/%d/10;--d:%d/14/%d/21"><h3>%s</h3></div>' % (
                    n, n + 2, n, n + 2, self.rewrite_links(to_html(r['names']), R))
        return self.flex_section(cells, rows_m=3 * len(rows), rows_d=3 * len(rows), rg=11, cg=11, cls='credits',
                                 pad=('s', 's'), first=first, extra_style='--credits-h1:20px')

    def flex_spacer(self, R, b, first):
        h = SPACER.get(b.get('height') or 'medium', SPACER['medium'])
        return '<section class="section%s flex" style="padding-top:%s" aria-hidden="true"></section>' % (' section--first' if first else '', h)

    def tile_cells(self, R, it, area_m, area_d, cls='cell--ratio'):
        """Bild- oder Videozelle plus Titelzelle (Titel als Kontur, Link auf die Seite) für eine Projekt-Kachel."""
        media = self.video_tag(R, it.get('video'), 'loop') if it.get('video') else ''
        if not media and it.get('image'):
            media = self.img_tag(R, it['image'], '(min-width: 768px) 50vw, 100vw', it.get('alt', ''))
        out = ('<div class="cell cell--media %s" style="--m:%s;--d:%s;--zm:1;--zd:1;--ratio:56.25%%">%s</div>'
               % (cls, area_m, area_d, media))
        if it.get('title'):
            href = self.link_href(R, it.get('link')) or '#'
            out += ('<div class="cell tile" style="--m:%s;--d:%s;--zm:2;--zd:2;--jm:center;--jd:center">'
                    '<h1 class="ta-center"><a href="%s">%s</a></h1></div>') % (area_m, area_d, esc(href), esc(it['title']))
        return out

    def flex_tiles(self, R, b, first):
        items = [i for i in (b.get('items') or []) if i.get('title') or i.get('image') or i.get('video')]
        if not items: return ''
        cells = ''
        n = len(items)
        for i, it in enumerate(items):
            r = i // 2 + 1
            left = i % 2 == 0
            c1, c2 = (1, 14) if left else (14, 27)
            cells += self.tile_cells(R, it, '%d/1/%d/11' % (i + 1, i + 2), '%d/%d/%d/%d' % (r, c1, r + 1, c2))
        return self.flex_section(cells, rows_m=n, rows_d=math.ceil(n / 2), rg=11, cg=11, cls='flex--tiles', first=first)

    # ------------------------------------------------------------------ Seitengerüst
    def header(self, R, nav_items):
        desk = mob_root = mob_sub = ''
        for it in nav_items:
            if it.get('children'):
                subs = ''.join('<li><a href="%s">%s</a></li>' % (self.url(R, c['link']), esc(c['label'])) for c in it['children'])
                desk += ('<li class="has-sub"><button type="button" aria-expanded="false" aria-controls="sub-projects">%s</button>'
                         '<ul class="sub" id="sub-projects">%s</ul></li>') % (esc(it['label']), subs)
                mob_root += ('<button type="button" class="mobile-menu__item" data-panel-open="projects">%s'
                             '<svg viewBox="0 0 9 16" aria-hidden="true"><polyline points="1.6,1.2 6.5,7.9 1.6,14.7"/></svg></button>') % esc(it['label'])
                mob_sub = ('<button type="button" class="mobile-menu__item mobile-menu__back" data-panel-open="root">'
                           '<svg viewBox="0 0 9 16" aria-hidden="true"><polyline points="1.6,1.2 6.5,7.9 1.6,14.7"/></svg>Zurück</button>' +
                           ''.join('<a class="mobile-menu__item" href="%s">%s</a>' % (self.url(R, c['link']), esc(c['label'])) for c in it['children']))
            else:
                desk += '<li><a href="%s">%s</a></li>' % (self.url(R, it['link']), esc(it['label']))
                mob_root += '<a class="mobile-menu__item" href="%s">%s</a>' % (self.url(R, it['link']), esc(it['label']))
        return ('<header class="site-header"><div class="site-header__inner">'
                '<a class="site-title" href="%s">%s</a>'
                '<nav class="site-nav" aria-label="Hauptnavigation"><ul>%s</ul></nav>'
                '<button type="button" class="menu-toggle" aria-label="Menü öffnen" aria-expanded="false"><span></span><span></span></button>'
                '</div><div class="mobile-menu"><div class="mobile-menu__panel is-active" data-panel="root">%s</div>'
                '<div class="mobile-menu__panel" data-panel="projects">%s</div></div></header>') % (
            self.url(R, ''), esc(self.site.get('site_name', '')), desk, mob_root, mob_sub)

    def sprite(self):
        return ('<svg width="0" height="0" style="position:absolute" aria-hidden="true">' +
                ''.join('<symbol id="i-%s" viewBox="0 0 64 64">%s</symbol>' % (k, v) for k, v in self.icons.items()) + '</svg>')

    def page(self, slug, title, desc, body_html, R, nav_items, home=False, sprite=False):
        canon = self.base + ('/' + slug + '/' if slug else '/')
        site = self.base
        preload = '' if self.local else '<link rel="preload" href="%sassets/fonts/oswald-latin.woff2" as="font" type="font/woff2" crossorigin>\n' % R
        cookie_text = self.site.get('cookie_text', '')
        cookie_btn = self.site.get('cookie_button', 'OK')
        cookie = ('<div class="cookie-banner" role="region" aria-label="Cookie-Banner" hidden>\n<p>%s</p>\n<button type="button">%s</button>\n</div>\n'
                  % (esc(cookie_text), esc(cookie_btn))) if cookie_text else ''
        return '''<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<meta name="theme-color" content="#000000">
<link rel="canonical" href="%(canon)s">
<meta property="og:site_name" content="%(sitename)s">
<meta property="og:type" content="website">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(canon)s">
<meta property="og:image" content="%(site)s/assets/img/og-image.jpg">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="%(R)sfavicon.ico" sizes="any">
%(preload)s<link rel="stylesheet" href="%(R)sassets/css/site.css">
<script>document.documentElement.classList.add("js")</script>
</head>
<body class="page-%(cls)s%(home)s">
%(sprite)s
%(header)s
<main>
%(body)s
</main>
%(cookie)s<script src="%(R)sassets/js/site.js" defer></script>
</body>
</html>
''' % dict(title=esc(title), desc=esc(desc), canon=canon, site=site, R=R, preload=preload, sitename=esc(self.site.get('site_name', '')),
           cls=slug or 'home', home=' homepage' if home else '', sprite=self.sprite() if sprite else '',
           header=self.header(R, nav_items), body=body_html, cookie=cookie)

    # ------------------------------------------------------------------ Hauptablauf
    def build(self):
        out = self.out
        if os.path.exists(out): shutil.rmtree(out)
        for d in ('assets/css', 'assets/js', 'assets/fonts', 'assets/img', 'assets/video'):
            os.makedirs(os.path.join(out, d))
        theme = os.path.join(ROOT, 'theme')
        shutil.copy(os.path.join(theme, 'site.css'), os.path.join(out, 'assets/css/'))
        shutil.copy(os.path.join(theme, 'site.js'), os.path.join(out, 'assets/js/'))
        for f in os.listdir(os.path.join(theme, 'fonts')):
            if f.endswith('.woff2'): shutil.copy(os.path.join(theme, 'fonts', f), os.path.join(out, 'assets/fonts/'))
        for f in ('favicon.ico', 'apple-touch-icon.png'):
            if os.path.exists(os.path.join(theme, f)): shutil.copy(os.path.join(theme, f), out)
        if os.path.exists(os.path.join(theme, 'og-image.jpg')):
            shutil.copy(os.path.join(theme, 'og-image.jpg'), os.path.join(out, 'assets/img/'))
        self.icons = load('theme/icons.json', {})
        self.media = Media(ROOT, out, self.cache)

        index = load('layout/index.json', {'pages': []})
        pages = []        # (slug, titel, beschreibung, body, home, sprite)
        nav_items = json.loads(json.dumps(self.nav.get('items', [])))

        # neue Seiten einsammeln (auch für das Menü)
        new_pages = []
        npdir = os.path.join(ROOT, 'content', 'new-pages')
        known = set(index['pages'])
        if os.path.isdir(npdir):
            for fn in sorted(os.listdir(npdir)):
                if not fn.endswith('.json'): continue
                try:
                    c = json.load(open(os.path.join(npdir, fn), encoding='utf-8'))
                except ValueError as e:
                    raise SystemExit('Die Datei content/new-pages/%s ist kein gültiges JSON: %s' % (fn, e))
                slug = slugify(c.get('slug') or os.path.splitext(fn)[0])
                if not slug or slug in RESERVED or slug in known:
                    warn('Die neue Seite %s wird übersprungen: Der Seitenname "%s" ist schon vergeben oder nicht erlaubt.' % (fn, slug), 'content/new-pages/' + fn)
                    continue
                known.add(slug)
                new_pages.append((slug, c))
        # Menü ergänzen
        def menu_sort(sc):
            try: o = float(sc[1].get('order'))
            except (TypeError, ValueError): o = 1e6
            return (o, sc[1].get('name', ''))
        for slug, c in sorted(new_pages, key=menu_sort):
            m = c.get('menu') or 'none'
            label = (c.get('menu_label') or c.get('name') or slug).strip().lower() if (c.get('menu_label') or c.get('name')) else slug
            item = {'label': label, 'link': '/' + slug}
            if m == 'projects':
                folder = next((i for i in nav_items if i.get('children') is not None and i.get('label') == 'projects'), None) or \
                    next((i for i in nav_items if i.get('children') is not None), None)
                if folder is not None: folder['children'].append(item)
                else: nav_items.insert(max(0, len(nav_items) - 1), item)
            elif m == 'main':
                nav_items.insert(max(0, len(nav_items) - 1), item)

        # bestehende Seiten
        for slug in index['pages']:
            L = load('layout/%s.json' % slug)
            C = load('content/pages/%s.json' % slug, {}) or {}
            R = '' if slug == 'home' else '../'
            secs = L['sections']
            body = ''
            footer = ''
            first_done = False
            for i, sec in enumerate(secs):
                c = C.get('s%d' % sec['n'])
                if sec.get('footer'):
                    footer += self.render_section(R, sec, c, False)
                    continue
                body += self.render_section(R, sec, c, i == 0, C.get('new_tiles') if sec.get('tile_slots') else None)
            body += self.render_flex(R, C.get('extra'))
            body += footer
            has_social = any(b['type'] == 'social' for s in secs for b in s.get('blocks', []))
            pages.append(('' if slug == 'home' else slug, C.get('title') or self.site.get('site_name', ''),
                          C.get('description', ''), body, R, slug == 'home', has_social))

        # neue Seiten
        for slug, c in new_pages:
            R = '../'
            name = (c.get('name') or slug)
            body = self.render_flex(R, c.get('blocks'), first_is_page_start=True)
            if not body:
                body = self.flex_section('<div class="cell" style="--m:1/2/2/10;--d:1/2/2/26"><h3 class="ta-center">%s</h3></div>' % esc(name), first=True)
            # Fußzeile wie auf den anderen Seiten
            ft = self.site.get('footer', '')
            if ft:
                body += ('<section class="section section--custom section--middle" style="--pt:var(--pad-xs);--pb:var(--pad-xs)">'
                         '<div class="grid" style="--rows-m:2;--rows-d:3;--rg:0px;--cg:0px">'
                         '<div class="cell footer-text" style="--m:2/2/3/10;--d:2/10/3/18;--jm:flex-start;--jd:center"><p class="ta-center small">%s</p></div>'
                         '</div></section>') % self.rewrite_links(to_html(ft), R)
            title = '%s | %s' % (self.site.get('title_prefix') or self.site.get('site_name', ''), name)
            pages.append((slug, c.get('title') or title, c.get('description', ''), body, R, False, False))

        for slug, title, desc, body, R, home, sprite in pages:
            h = self.page(slug, title, desc or self.site.get('default_description', ''), body, R, nav_items, home=home, sprite=sprite)
            d = out if slug == '' else os.path.join(out, slug)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f: f.write(h)

        slugs = [p[0] for p in pages]
        with open(os.path.join(out, 'sitemap.xml'), 'w') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                    ''.join('  <url><loc>%s/%s</loc></url>\n' % (self.base, (s + '/') if s else '') for s in slugs) + '</urlset>\n')
        with open(os.path.join(out, 'robots.txt'), 'w') as f:
            f.write('User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n' % self.base)
        open(os.path.join(out, '.nojekyll'), 'w').close()
        if not self.local:
            if self.domain:
                with open(os.path.join(out, 'CNAME'), 'w') as f: f.write(self.domain + '\n')
            with open(os.path.join(out, '_headers'), 'w') as f:
                f.write('/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n')
        nf = ('<section class="section section--middle" style="min-height:100vh"><div class="grid" style="--rows-m:1;--rows-d:1;--rg:0px;--cg:0px">'
              '<div class="cell" style="--m:1/2/2/10;--d:1/2/2/26;--jm:center;--jd:center"><h3 class="ta-center">404 – seite nicht gefunden</h3>'
              '<h4 class="ta-center" style="margin-top:20px"><a href="/">zurück zur startseite</a></h4></div></div></section>')
        h404 = self.page('404', 'Sami Jabeur | 404', 'Seite nicht gefunden', nf, '/', nav_items)
        h404 = h404.replace('<link rel="canonical" href="%s/404/">' % self.base, '<meta name="robots" content="noindex">')
        with open(os.path.join(out, '404.html'), 'w', encoding='utf-8') as f: f.write(h404)
        print('Fertig:', out, '-', len(pages), 'Seiten')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist'))
    ap.add_argument('--local', action='store_true')
    ap.add_argument('--cache', default=os.path.join(ROOT, 'build', '.cache'))
    a = ap.parse_args()
    Builder(os.path.abspath(a.out), local=a.local, cache=a.cache).build()


if __name__ == '__main__':
    main()
