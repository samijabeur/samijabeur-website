#!/usr/bin/env python3
"""Erzeugt .pages.yml (Konfiguration für Pages CMS) aus layout/*.json und content/pages/*.json.

Nur nötig, wenn sich das feste Seitenraster ändert (neue Textfelder, neue Abschnitte).
Aufruf im Repository-Hauptordner:   python3 tools/make_cms_config.py
(braucht PyYAML:  pip install pyyaml)
"""
import json
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return json.load(f)


# ----------------------------------------------------------------------------- Beschriftungen
SEC_LABELS = {
    ('home', 1): 'Startbild (Vollbild-Hintergrund)',
    ('home', 3): 'Projekt-Kacheln',
    ('about', 1): 'Über mich',
    ('becoming', 1): 'Titelbereich', ('becoming', 2): 'Galerie', ('becoming', 3): 'Credits',
    ('ragavara', 1): 'Titel und Film', ('ragavara', 2): 'Galerie', ('ragavara', 3): 'Credits',
    ('eunoia', 1): 'Film und Credits',
    ('letzter-anruf', 1): 'Beschreibung, Film und Credits',
    ('protests-for-justice', 1): 'Texte', ('protests-for-justice', 2): 'Galerie',
    ('vortex', 1): 'Titel, Einleitung und Film', ('vortex', 2): 'Galerie', ('vortex', 3): 'Credits',
    ('gallery', 2): 'Galerie oben (Raster)', ('gallery', 4): 'Drei Hintergrundvideos',
    ('gallery', 5): 'Galerie (alle Fotos)',
}
PAGE_LABELS = {
    'home': 'Startseite', 'about': 'About', 'becoming': 'Becoming', 'ragavara': 'Ragavara', 'eunoia': 'Eunoia',
    'letzter-anruf': 'Letzter Anruf', 'protests-for-justice': 'Protests for Justice', 'vortex': 'Vortex',
    'gallery': 'Gallery',
}
TAG_HINT = {'h1': 'Großer Text', 'h2': 'Große Überschrift', 'h3': 'Überschrift', 'h4': 'Kleiner Text', 'p': 'Fußnote'}


def short(s, n=45):
    s = re.sub(r'\s+', ' ', s or '').strip()
    return s if len(s) <= n else s[:n - 1] + '…'


# ----------------------------------------------------------------------------- Feld-Bausteine
def img_field(name='image', label='Bild'):
    return {'name': name, 'label': label, 'type': 'image', 'options': {'media': 'images'}}


def vid_field(name='video', label='Video (MP4)'):
    return {'name': name, 'label': label, 'type': 'file', 'options': {'media': 'videos', 'extensions': ['mp4', 'webm']}}


def select(name, label, values, description=None, default=None):
    f = {'name': name, 'label': label, 'type': 'select',
         'options': {'values': [{'value': v, 'label': l} for v, l in values]}}
    if description: f['description'] = description
    if default is not None: f['default'] = default
    return f


ALT = {'name': 'alt', 'label': 'Bildbeschreibung (für Blinde und Google, optional)', 'type': 'string'}
FOCAL = {'name': 'focal', 'label': 'Bildausschnitt (optional, für Fortgeschrittene)', 'type': 'string',
         'description': 'Zwei Zahlen zwischen 0 und 1, z. B. 0.5,0.3. Leer lassen = Bildmitte.'}


def image_obj(name, label, description=None):
    f = {'name': name, 'label': label, 'type': 'object', 'fields': [img_field(), dict(ALT), dict(FOCAL)]}
    if description: f['description'] = description
    return f


def image_list(name, label, description=None):
    """Mehrere Bilder in einem Feld: per Ziehen hochladen oder aus der Mediathek wählen, Reihenfolge per Ziehen."""
    f = {'name': name, 'label': label, 'type': 'image', 'options': {'media': 'images', 'multiple': True, 'unique': True}}
    if description: f['description'] = description
    return f


SIZES = [('full', 'Volle Breite (bis an den Rand)'), ('wide', 'Breit (mit Rand)'), ('medium', 'Mittel'), ('small', 'Klein')]


def block_defs():
    """Flexible Bausteine ("Weitere Inhalte" und neue Seiten)."""
    return [
        {'name': 'text', 'label': 'Text / Überschrift', 'fields': [
            {'name': 'text', 'label': 'Text', 'type': 'text',
             'description': 'Enter = neue Zeile. **fett**, *kursiv*, [Linktext](https://…) oder [Linktext](/vortex) sind möglich.'},
            select('style', 'Aussehen', [('title-xl', 'Sehr große Überschrift'), ('title', 'Große Überschrift'),
                                         ('lead', 'Großer Text'), ('body', 'Normaler Text'), ('small', 'Kleiner Text (Fußnote)')]),
            select('align', 'Ausrichtung', [('center', 'Zentriert'), ('left', 'Linksbündig'), ('right', 'Rechtsbündig'), ('justify', 'Blocksatz')]),
        ]},
        {'name': 'image', 'label': 'Bild', 'fields': [
            img_field(), dict(ALT), select('size', 'Größe', SIZES),
        ]},
        {'name': 'film', 'label': 'Film / Video', 'fields': [
            vid_field(),
            select('mode', 'Wiedergabe', [('player', 'Mit Abspielleiste (Ton, Pause, Vollbild)'), ('loop', 'Dauerschleife ohne Ton (wie ein bewegtes Bild)')]),
            select('ratio', 'Seitenverhältnis', [('16:9', '16:9 (Querformat)'), ('4:3', '4:3'), ('3:2', '3:2'), ('1:1', 'Quadrat'), ('9:16', '9:16 (Hochformat)')]),
            select('size', 'Größe', SIZES),
            img_field('poster', 'Vorschaubild (optional; sonst wird ein Bild aus dem Video genommen)'),
            {'name': 'title', 'label': 'Titel des Videos (für Blinde, optional)', 'type': 'string'},
        ]},
        {'name': 'gallery', 'label': 'Galerie', 'fields': [
            select('layout', 'Anordnung', [('masonry', 'Mauerwerk (Bilder in ihrer eigenen Höhe)'), ('grid', 'Raster (alle gleich groß)'), ('strips', 'Streifen (Bilder nebeneinander in einer Zeile)')]),
            select('columns', 'Spalten (bei Mauerwerk und Raster)', [(str(i), str(i)) for i in (2, 3, 4, 5)]),
            select('gap', 'Abstand zwischen den Bildern', [('none', 'Kein Abstand'), ('small', 'Klein'), ('medium', 'Mittel')]),
            select('width', 'Breite', [('inset', 'Mit Rand'), ('full-bleed', 'Randlos (bis an den Bildschirmrand)'), ('full', 'Fast randlos')]),
            select('ratio', 'Bildformat (nur bei Raster)', [('4:3', '4:3 Querformat'), ('2:3', '2:3 Hochformat'), ('1:1', 'Quadrat')]),
            {'name': 'lightbox', 'label': 'Bild beim Anklicken groß zeigen', 'type': 'boolean', 'default': True},
            image_list('images', 'Bilder', 'Fotos hier hineinziehen oder hochladen. Reihenfolge durch Ziehen ändern, Foto entfernen über den Papierkorb.'),
        ]},
        {'name': 'credits', 'label': 'Credits (Rollen und Namen)', 'fields': [
            {'name': 'rows', 'label': 'Zeilen', 'type': 'object', 'list': {'collapsible': {'collapsed': False, 'summary': '{role}: {names}'}},
             'fields': [{'name': 'role', 'label': 'Rolle (z. B. director)', 'type': 'string'},
                        {'name': 'names', 'label': 'Name(n)', 'type': 'text', 'description': 'Mehrere Namen: jeweils in eine neue Zeile.'}]},
        ]},
        {'name': 'tiles', 'label': 'Projekt-Kacheln', 'fields': [
            {'name': 'items', 'label': 'Kacheln', 'type': 'object', 'list': {'collapsible': {'collapsed': False, 'summary': '{title}'}},
             'fields': [{'name': 'title', 'label': 'Titel', 'type': 'string'},
                        {'name': 'link', 'label': 'Link', 'type': 'string', 'description': 'Seite dieser Website (z. B. /vortex) oder eine Adresse mit https://'},
                        img_field('image', 'Bild'), vid_field('video', 'oder Video (hat Vorrang vor dem Bild)')]},
        ]},
        {'name': 'spacer', 'label': 'Abstand', 'fields': [
            select('height', 'Höhe', [('small', 'Klein'), ('medium', 'Mittel'), ('large', 'Groß')]),
        ]},
    ]


def blocks_field(name, label, description=None):
    # Die Baustein-Definitionen stehen einmal unter "components" und werden hier nur referenziert.
    f = {'name': name, 'label': label, 'type': 'block', 'blockKey': 'type',
         'list': {'collapsible': {'collapsed': True, 'summary': '{type}'}},
         'blocks': [{'name': b['name'], 'label': b['label'], 'component': 'block_' + b['name']} for b in block_defs()]}
    if description: f['description'] = description
    return f


# ----------------------------------------------------------------------------- Seiten
def section_fields(slug, L, C):
    """Felder einer Layout-Sektion (nach den vorhandenen Inhalten)."""
    n = L['n']
    c = C.get('s%d' % n)
    if not c: return None
    fields = []
    if L['kind'] == 'gallery':
        fields.append(image_list('images', 'Bilder', 'Fotos hier hineinziehen oder hochladen. Reihenfolge durch Ziehen ändern, Foto entfernen über den Papierkorb.'))
        return fields
    if L.get('hero'):
        fields.append(image_obj('bg', 'Startbild'))
    blocks = L.get('blocks', [])
    texts = [b for b in blocks if b['type'] == 'text']
    credit_like = len(texts) >= 8
    home_tiles = slug == 'home' and L['n'] == 3
    tile_no = 0
    keyed = {b['key']: b for b in blocks if b.get('key')}
    order = sorted(keyed.values(), key=lambda b: (b['type'] != 'text', b['key']))
    # Reihenfolge der Felder: Texte in Lesereihenfolge, dann Bilder/Videos – bei den Startseiten-Kacheln nach Blöcken
    seq = blocks if home_tiles else order
    k = 0
    for b in seq:
        if not b.get('key'): continue
        key = b['key']
        if b['type'] == 'text':
            k += 1
            orig = c.get(key)
            orig_txt = orig.get('text') if isinstance(orig, dict) else orig
            desc = 'Ursprünglich: „%s“' % short(orig_txt) if orig_txt else None
            if b.get('link'):
                tile_no_label = 'Kachel %d · Titel und Link' % (tile_no)
                f = {'name': key, 'label': tile_no_label, 'type': 'object', 'fields': [
                    {'name': 'text', 'label': 'Titel', 'type': 'string'},
                    {'name': 'link', 'label': 'Link', 'type': 'string', 'description': 'Seite dieser Website, z. B. /vortex'}]}
            else:
                if credit_like:
                    role = b.get('align') == 'right'
                    label = 'Credits %02d · %s' % (k, 'Rolle' if role else 'Name')
                    typ = 'string' if role else 'text'
                else:
                    label = '%s (Text %d)' % (TAG_HINT.get(b['tag'], 'Text'), k)
                    typ = 'text'
                f = {'name': key, 'label': label, 'type': typ}
                if desc: f['description'] = desc
            fields.append(f)
        elif b['type'] == 'image':
            if home_tiles: tile_no += 1
            fields.append(image_obj(key, ('Kachel %d · Bild' % tile_no) if home_tiles else 'Bild'))
        elif b['type'] == 'bgvideo':
            if home_tiles: tile_no += 1
            fields.append({'name': key, 'label': ('Kachel %d · Video' % tile_no) if home_tiles else 'Hintergrundvideo (läuft ohne Ton in Dauerschleife)',
                           'type': 'object', 'fields': [vid_field()]})
        elif b['type'] == 'film':
            fields.append({'name': key, 'label': 'Film', 'type': 'object',
                           'description': 'Zum Austauschen ein neues Video hochladen oder auswählen (MP4, H.264).', 'fields': [vid_field()]})
    return fields or None


def page_entry(slug):
    L = load('layout/%s.json' % slug)
    C = load('content/pages/%s.json' % slug)
    fields = [
        {'name': 'title', 'label': 'Seitentitel (Browser-Tab und Google)', 'type': 'string'},
        {'name': 'description', 'label': 'Beschreibung für Google (1 bis 2 Sätze, optional)', 'type': 'text'},
    ]
    for sec in L['sections']:
        fs = section_fields(slug, sec, C)
        if not fs: continue
        label = SEC_LABELS.get((slug, sec['n'])) or ('Galerie' if sec['kind'] == 'gallery' else 'Bereich %d' % sec['n'])
        fields.append({'name': 's%d' % sec['n'], 'label': label, 'type': 'object', 'fields': fs})
    fields.append(blocks_field('extra', 'Weitere Inhalte (werden unter dem bisherigen Inhalt angehängt)',
                               'Hier kannst du Texte, Bilder, Filme, Galerien und mehr hinzufügen, ohne am bestehenden Aufbau etwas zu ändern.'))
    return {'name': 'page_' + slug.replace('-', '_'), 'label': PAGE_LABELS.get(slug, slug), 'type': 'file',
            'path': 'content/pages/%s.json' % slug, 'format': 'json', 'fields': fields}


def build():
    index = load('layout/index.json')['pages']
    pages = [page_entry(s) for s in index]
    new_pages = {
        'name': 'new_pages', 'label': 'Neue Seiten', 'type': 'collection', 'path': 'content/new-pages', 'format': 'json',
        'filename': '{primary}.json', 'subfolders': False,
        'view': {'fields': ['name', 'menu'], 'primary': 'name', 'default': {'sort': 'name', 'order': 'asc'}, 'sort': ['name']},
        'fields': [
            {'name': 'name', 'label': 'Name der Seite (z. B. MEIN PROJEKT)', 'type': 'string', 'required': True,
             'description': 'Der Name bestimmt auch die Adresse der Seite: „MEIN PROJEKT“ wird zu samijabeur.com/mein-projekt/'},
            {'name': 'description', 'label': 'Beschreibung für Google (1 bis 2 Sätze, optional)', 'type': 'text'},
            select('menu', 'Im Menü anzeigen', [('projects', 'Unter „projects“'), ('main', 'Im Hauptmenü'), ('none', 'Nicht im Menü')], default='projects'),
            {'name': 'menu_label', 'label': 'Name im Menü (optional, sonst der Seitenname)', 'type': 'string'},
            {'name': 'order', 'label': 'Reihenfolge im Menü (optional; 1 = zuerst, sonst alphabetisch hinten)', 'type': 'number'},
            blocks_field('blocks', 'Inhalt der Seite', 'Baustein für Baustein von oben nach unten. Mit „Hinzufügen“ kommt ein neuer Baustein dazu.'),
        ],
    }
    nav = {
        'name': 'navigation', 'label': 'Menü', 'type': 'file', 'path': 'content/navigation.json', 'format': 'json',
        'fields': [{
            'name': 'items', 'label': 'Menüpunkte', 'type': 'object', 'list': {'collapsible': {'collapsed': False, 'summary': '{label}'}},
            'description': 'Reihenfolge durch Ziehen ändern. Ein Menüpunkt mit Unterpunkten ist ein Ordner (Link dann leer lassen).',
            'fields': [
                {'name': 'label', 'label': 'Name im Menü', 'type': 'string'},
                {'name': 'link', 'label': 'Seite (z. B. /about; Startseite = /)', 'type': 'string'},
                {'name': 'children', 'label': 'Unterpunkte (nur bei Ordnern)', 'type': 'object', 'list': {'collapsible': {'collapsed': True, 'summary': '{label}'}},
                 'fields': [{'name': 'label', 'label': 'Name im Menü', 'type': 'string'},
                            {'name': 'link', 'label': 'Seite (z. B. /vortex)', 'type': 'string'}]},
            ]}],
    }
    site = {
        'name': 'site', 'label': 'Website-Einstellungen', 'type': 'file', 'path': 'content/site.json', 'format': 'json',
        'fields': [
            {'name': 'site_name', 'label': 'Name der Website (Logo oben links)', 'type': 'string'},
            {'name': 'title_prefix', 'label': 'Vorspann der Seitentitel (z. B. „Sami Jabeur“ ergibt „Sami Jabeur | Vortex“)', 'type': 'string'},
            {'name': 'domain', 'label': 'Domain (z. B. www.samijabeur.com)', 'type': 'string',
             'description': 'Nur ändern, wenn sich die Adresse der Website ändert. Muss auch in GitHub unter Settings → Pages eingetragen sein.'},
            {'name': 'footer', 'label': 'Fußzeile (unten auf jeder Seite)', 'type': 'string'},
            {'name': 'default_description', 'label': 'Standard-Beschreibung für Google (wenn eine Seite keine eigene hat)', 'type': 'text'},
            {'name': 'cookie_text', 'label': 'Cookie-Hinweis (Text; leer lassen = kein Banner)', 'type': 'text'},
            {'name': 'cookie_button', 'label': 'Cookie-Hinweis (Button)', 'type': 'string'},
            {'name': 'social', 'label': 'Social-Media-Links (About-Seite)', 'type': 'object', 'list': {'collapsible': {'collapsed': True, 'summary': '{network}'}},
             'fields': [select('network', 'Netzwerk', [('instagram', 'Instagram'), ('linkedin', 'LinkedIn')]),
                        {'name': 'url', 'label': 'Adresse (https://…)', 'type': 'string'}]},
        ],
    }
    cfg = {
        'components': {'block_' + b['name']: {'type': 'object', 'fields': b['fields']} for b in block_defs()},
        'media': [
            {'name': 'images', 'label': 'Bilder', 'input': 'media/images', 'output': '/media/images', 'rename': 'safe',
             'extensions': ['jpg', 'jpeg', 'png', 'webp', 'gif']},
            {'name': 'videos', 'label': 'Videos und Filme', 'input': 'media/video', 'output': '/media/video', 'rename': 'safe',
             'extensions': ['mp4', 'webm']},
        ],
        'content': [
            {'name': 'pages', 'label': 'Seiten', 'type': 'group', 'items': pages},
            new_pages,
            {'name': 'config', 'label': 'Menü und Einstellungen', 'type': 'group', 'items': [nav, site]},
        ],
        'settings': {'commit': {'templates': {
            'create': 'Neu angelegt: {path}', 'update': 'Geändert: {path}', 'delete': 'Gelöscht: {path}',
            'rename': 'Umbenannt: {oldPath} → {newPath}'}}},
    }
    return cfg


HEADER = """# Konfiguration für Pages CMS (https://pagescms.org) – steuert, was du im Editor siehst.
# Erzeugt mit tools/make_cms_config.py aus dem festen Seitenraster (layout/*.json).
# Bitte nicht von Hand ändern, außer du weißt, was du tust: Eine Änderung hier verändert nur die
# Eingabemaske, nicht die Website.
"""


def main():
    cfg = build()
    out = os.path.join(ROOT, '.pages.yml')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(HEADER)
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False, width=140, default_flow_style=False)
    print('geschrieben:', out)


if __name__ == '__main__':
    main()
