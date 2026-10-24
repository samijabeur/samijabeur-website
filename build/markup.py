"""Einfache Auszeichnung für Texte im CMS -> HTML.

Im CMS tippst du ganz normalen Text. Erlaubt sind nur wenige Sonderzeichen:

    Neue Zeile                  Enter-Taste (wird zu einem Zeilenumbruch)
    **fett**                    fetter Text
    *kursiv*                    kursiver Text
    [Linktext](https://...)     Link (externe Links öffnen in neuem Tab)
    [Linktext](/vortex)         Link auf eine Seite dieser Website

Alles andere (auch spitze Klammern) wird als normaler Text angezeigt.
"""
import html
import re


def esc_text(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _link(m):
    text, href = m.group(1), m.group(2)
    ext = href.startswith(('http://', 'https://', 'mailto:'))
    return '<a href="%s"%s>%s</a>' % (href, ' target="_blank" rel="noopener"' if ext else '', text)


def to_html(md):
    s = esc_text(md or '')
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', _link, s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s, flags=re.S)
    s = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', s, flags=re.S)
    return re.sub(r'\r\n|\r|\n', '<br>', s)


def slugify(s):
    s = (s or '').lower()
    for a, b in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        s = s.replace(a, b)
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s
