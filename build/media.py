"""Bilder und Videos für die fertige Website aufbereiten.

Bilder: Du legst nur das Original in media/images ab. Hier entstehen daraus
verkleinerte WebP-Fassungen (500, 1000, 1600 px breit), die der Browser je nach
Bildschirm auswählt. Videos werden unverändert übernommen; für jedes Video
entsteht außerdem ein Vorschaubild (Poster).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageOps

WIDTHS = [500, 1000, 1600]
ALLOWED_IMG = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
VERSION = 'v1'          # bei Änderung der Verfahren hochzählen (macht den Cache ungültig)


def warn(msg, file=None):
    if os.environ.get('GITHUB_ACTIONS'):
        print('::warning%s::%s' % ((' file=' + file) if file else '', msg))
    else:
        print('WARNUNG:', msg, file=sys.stderr)


def basename(ref):
    return os.path.basename((ref or '').split('?')[0])


class Media:
    def __init__(self, root, out_dir, cache_dir=None):
        self.img_src = os.path.join(root, 'media', 'images')
        self.vid_src = os.path.join(root, 'media', 'video')
        self.out_img = os.path.join(out_dir, 'assets', 'img')
        self.out_vid = os.path.join(out_dir, 'assets', 'video')
        self.cache = cache_dir
        os.makedirs(self.out_img, exist_ok=True)
        os.makedirs(self.out_vid, exist_ok=True)
        if cache_dir: os.makedirs(cache_dir, exist_ok=True)
        self._img = {}
        self._vid = {}
        self._names = {}
        for d in (self.img_src, self.vid_src):
            if os.path.isdir(d):
                for f in os.listdir(d): self._names[(d, f.lower())] = f

    def _find(self, d, ref):
        n = basename(ref)
        if not n: return None
        if os.path.exists(os.path.join(d, n)): return n
        return self._names.get((d, n.lower()))

    # ------------------------------------------------------------------ Bilder
    def image(self, ref):
        """-> dict(w, h, orig, variants=[[breite, datei], ...]) oder None, wenn das Bild fehlt."""
        n = self._find(self.img_src, ref)
        if n is None:
            if ref: warn('Bild nicht gefunden: %s (in media/images)' % ref)
            return None
        if n in self._img: return self._img[n]
        p = os.path.join(self.img_src, n)
        ext = os.path.splitext(n)[1].lower()
        if ext not in ALLOWED_IMG:
            warn('Bildformat %s wird nicht unterstützt (%s). Bitte JPG, PNG oder WebP verwenden.' % (ext, n), p)
            self._img[n] = None
            return None
        key = None
        if self.cache:
            h = hashlib.sha1(open(p, 'rb').read()).hexdigest()[:20]
            key = os.path.join(self.cache, '%s-%s' % (VERSION, h))
            meta = key + '.json'
            if os.path.exists(meta):
                d = json.load(open(meta))
                if all(os.path.exists(os.path.join(key + '.d', f)) for f in [d['orig']] + [v[1] for v in d['variants']]):
                    for f in [d['orig']] + [v[1] for v in d['variants']]:
                        shutil.copy(os.path.join(key + '.d', f), self.out_img)
                    self._img[n] = d
                    return d
        try:
            d = self._process(p, n)
        except Exception as e:           # kaputte oder unlesbare Datei
            warn('Bild konnte nicht gelesen werden: %s (%s)' % (n, e), p)
            self._img[n] = None
            return None
        if key:
            os.makedirs(key + '.d', exist_ok=True)
            for f in [d['orig']] + [v[1] for v in d['variants']]:
                shutil.copy(os.path.join(self.out_img, f), key + '.d')
            json.dump(d, open(key + '.json', 'w'))
        self._img[n] = d
        return d

    def _process(self, p, n):
        im = Image.open(p)
        im = ImageOps.exif_transpose(im)          # Handy-Fotos: Drehung aus den Metadaten übernehmen
        w, h = im.size
        stem, ext = os.path.splitext(n)
        if ext.lower() == '.png':
            im.save(os.path.join(self.out_img, stem + '.webp'), 'WEBP', quality=88, method=4)
            orig = stem + '.webp'
        else:
            shutil.copy(p, os.path.join(self.out_img, n))
            orig = n
        variants = []
        if ext.lower() != '.gif':
            im = im.convert('RGBA') if im.mode in ('RGBA', 'LA', 'P') else im.convert('RGB')
            for tw in WIDTHS:
                if tw < w * 0.9:
                    r = im.resize((tw, round(h * tw / w)), Image.LANCZOS)
                    fn = '%s-%d.webp' % (stem, tw)
                    r.save(os.path.join(self.out_img, fn), 'WEBP', quality=82, method=4)
                    variants.append([tw, fn])
        return {'w': w, 'h': h, 'orig': orig, 'variants': variants}

    # ------------------------------------------------------------------ Videos
    def video(self, ref):
        """-> (videodatei, postername) oder None."""
        n = self._find(self.vid_src, ref)
        if n is None:
            if ref: warn('Video nicht gefunden: %s (in media/video)' % ref)
            return None
        if n in self._vid: return self._vid[n]
        src = os.path.join(self.vid_src, n)
        stem = os.path.splitext(n)[0]
        shutil.copy(src, os.path.join(self.out_vid, n))
        poster = None
        for ext in ('.webp', '.jpg', '.jpeg', '.png'):
            pn = self._find(self.vid_src, stem + ext)
            if pn:
                if ext == '.webp':
                    shutil.copy(os.path.join(self.vid_src, pn), os.path.join(self.out_vid, stem + '.webp'))
                else:
                    im = Image.open(os.path.join(self.vid_src, pn)).convert('RGB'); im.thumbnail((1600, 1600))
                    im.save(os.path.join(self.out_vid, stem + '.webp'), 'WEBP', quality=82)
                poster = stem + '.webp'
                break
        if poster is None:
            poster = self._make_poster(src, stem)
        self._vid[n] = (n, poster)
        return self._vid[n]

    def _make_poster(self, src, stem):
        out_jpg = os.path.join(self.out_vid, stem + '.poster.jpg')
        for ss in ('2', '0'):
            try:
                subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', ss, '-i', src, '-frames:v', '1',
                                '-vf', "scale='min(1600,iw)':-2", out_jpg], check=True, timeout=120)
                if os.path.exists(out_jpg):
                    im = Image.open(out_jpg).convert('RGB')
                    im.save(os.path.join(self.out_vid, stem + '.webp'), 'WEBP', quality=82)
                    os.remove(out_jpg)
                    return stem + '.webp'
            except Exception:
                continue
        warn('Für das Video %s konnte kein Vorschaubild erzeugt werden (ffmpeg fehlt?).' % stem)
        return None
