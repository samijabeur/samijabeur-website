# samijabeur.com – Website-Quelle

Dieses Repository enthält alles, was die Website samijabeur.com ausmacht. Bei jeder Änderung baut
GitHub die Seite automatisch neu und veröffentlicht sie (GitHub Pages). Eine ausführliche
Schritt-für-Schritt-Anleitung (Einrichtung, Domain-Umzug, Bedienung des Editors) liegt separat bei.

## So bearbeitest du die Website

1. Öffne <https://app.pagescms.org>, melde dich mit GitHub an und wähle dieses Repository.
2. Links siehst du **Seiten**, **Neue Seiten**, **Menü und Einstellungen** sowie die **Mediathek** (Bilder, Videos).
3. Texte ändern, Bilder austauschen oder hinzufügen, neue Seiten anlegen, Speichern.
4. Nach etwa ein bis zwei Minuten ist die Änderung online (Fortschritt im Reiter „Actions“ auf GitHub).

Du kannst die Dateien auch direkt auf GitHub bearbeiten – der Editor ist nur eine bequemere Oberfläche dafür.

## Ordner

| Ordner / Datei | Inhalt |
|---|---|
| `content/pages/*.json` | Texte, Bilder und Videos der bestehenden Seiten (im Editor bearbeitbar) |
| `content/new-pages/*.json` | Neue Seiten, die du im Editor anlegst |
| `content/navigation.json`, `content/site.json` | Menü, Fußzeile, Domain, Social-Links, Cookie-Hinweis |
| `layout/*.json` | Festes Raster der bestehenden Seiten (Positionen und Größen wie bei Squarespace) |
| `media/images/` | Originalbilder (JPG, PNG, WebP). Verkleinerte Fassungen entstehen beim Bauen automatisch |
| `media/video/` | Videos (MP4, H.264). Vorschaubilder entstehen automatisch, falls keine vorhanden sind |
| `theme/` | Stylesheet, Skript, Schrift, Icons |
| `build/` | Der Generator (Python) |
| `.pages.yml` | Konfiguration des Editors (Pages CMS) |
| `.github/workflows/deploy.yml` | Automatisches Bauen und Veröffentlichen |

## Lokal bauen und ansehen

Voraussetzung: Python 3.10 oder neuer, `pip install -r build/requirements.txt`, für automatische Video-Vorschaubilder `ffmpeg`.

```bash
python3 build/build.py --out dist          # baut die Seite nach dist/
python3 -m http.server -d dist 8000        # dann http://localhost:8000 öffnen
python3 build/build.py --local --out vorschau   # Variante, die man per Doppelklick auf vorschau/index.html öffnen kann
```

## Hinweise

- **Dateigrößen:** GitHub nimmt Dateien bis 100 MB an, der Editor im Browser meist nur deutlich kleinere
  (bei großen Filmen lieber GitHub Desktop benutzen). Pro Video empfehlen sich MP4 (H.264), 720p oder 1080p.
- **Bilder:** Bitte keine Leerzeichen oder Umlaute im Dateinamen (der Editor ersetzt sie beim Hochladen automatisch).
- **Texte:** `**fett**`, `*kursiv*`, `[Linktext](https://…)`, `[Linktext](/vortex)`; Enter = neue Zeile.
- **Neue Seiten:** Die Adresse entsteht aus dem Namen („MEIN PROJEKT“ → `/mein-projekt/`).
- **Raster ändern** (zusätzliche Textfelder auf bestehenden Seiten): bei Bedarf in `layout/` ergänzen und danach
  `python3 tools/make_cms_config.py` ausführen, damit der Editor die neuen Felder kennt.
