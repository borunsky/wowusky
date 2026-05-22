# wowusky 0.4.9 — AUR-Veröffentlichung

Diese Anleitung beschreibt die Schritte, um wowusky 0.4.9 im Arch
User Repository (AUR) zu veröffentlichen. PKGBUILD und .SRCINFO sind
fertig vorbereitet; was bleibt, sind Schritte, die einen Git-Tag,
einen GitHub-Release und einen AUR-Account brauchen.

Reihenfolge ist wichtig: Erst taggen und releasen, dann Checksumme,
dann AUR.

---

## 1. Release auf GitHub taggen

Der PKGBUILD lädt den Quell-Tarball von
`github.com/borunsky/wowusky/archive/refs/tags/v0.4.9.tar.gz`.
Dieser Tag muss also existieren.

```bash
# Im wowusky-Repo, auf dem fertigen 0.4.9-Stand:
git add -A
git commit -m "Release v0.4.9 — AUR packaging"
git tag -a v0.4.9 -m "wowusky 0.4.9"
git push origin main --tags
```

Danach unter github.com/borunsky/wowusky/releases aus dem Tag `v0.4.9`
einen Release anlegen. GitHub erzeugt den Quell-Tarball automatisch.

## 2. Echte Checksumme eintragen

`sha256sums` steht aktuell auf `SKIP` — ein Platzhalter. Sobald der
Tag gepusht ist und der Tarball abrufbar ist:

```bash
# Im Verzeichnis mit dem PKGBUILD:
updpkgsums
```

`updpkgsums` lädt den Tarball, berechnet die Summe und ersetzt `SKIP`
im PKGBUILD automatisch. Alternativ von Hand:

```bash
curl -sL https://github.com/borunsky/wowusky/archive/refs/tags/v0.4.9.tar.gz \
  | sha256sum
```

und den Wert im PKGBUILD bei `sha256sums=(...)` eintragen.

## 3. Lokal bauen und testen

Bevor irgendetwas zur AUR geht — der PKGBUILD muss in einer sauberen
Umgebung durchlaufen:

```bash
makepkg -si        # baut UND installiert lokal
```

`makepkg` führt automatisch `build()`, `check()` (die 109 Tests) und
`package()` aus. Läuft das durch, ist das Paket gültig. Die Schritte
`build()` und `package()` wurden bereits verifiziert; `check()` läuft
die volle Testsuite.

> Wenn `check()` fehlschlägt, weil `python-pytest` fehlt: Das ist als
> `checkdepends` deklariert, `makepkg` sollte es ziehen. Falls nicht:
> `sudo pacman -S python-pytest`.

## 4. .SRCINFO regenerieren

Die `.SRCINFO` im Repo ist bereits korrekt für 0.4.9 — aber sie
muss zur *finalen* PKGBUILD-Version passen (insbesondere nach dem
Eintragen der echten Checksumme in Schritt 2). Nach jeder
PKGBUILD-Änderung:

```bash
makepkg --printsrcinfo > .SRCINFO
```

Das ist die maßgebliche Methode. Die mitgelieferte `.SRCINFO` ist
von Hand im korrekten Format erstellt, sollte aber vor dem AUR-Push
einmal so neu generiert werden, damit sie garantiert konsistent ist.

## 5. Zum AUR pushen

Voraussetzung: ein AUR-Account mit hinterlegtem SSH-Key
(aur.archlinux.org → My Account → SSH Public Key).

```bash
# AUR-Repo klonen (leeres Repo, der Paketname ist neu):
git clone ssh://aur@aur.archlinux.org/wowusky.git aur-wowusky
cd aur-wowusky

# Nur PKGBUILD und .SRCINFO gehören ins AUR-Repo — sonst nichts:
cp /pfad/zu/wowusky/PKGBUILD .
cp /pfad/zu/wowusky/.SRCINFO .

git add PKGBUILD .SRCINFO
git commit -m "wowusky 0.4.9 — initial release"
git push
```

> Das AUR-Repo enthält **nur** `PKGBUILD` und `.SRCINFO`. Der
> Quellcode bleibt auf GitHub; der PKGBUILD lädt ihn von dort.

## 6. Maintainer-Zeile anpassen

Im PKGBUILD steht aktuell:

```
# Maintainer: Kevin <your-email@example.com>
```

Vor dem AUR-Push die echte E-Mail eintragen — die AUR zeigt den
Maintainer öffentlich an, und Nutzer-Bugreports laufen darüber.

---

## Was bereits erledigt und verifiziert ist

- **GitHub-URL korrigiert** auf `github.com/borunsky/wowusky` —
  PKGBUILD, .SRCINFO und alle Doku zeigten auf das falsche Repo
  `wowusky/wowusky`. Der PKGBUILD hätte den Quell-Tarball nicht
  finden können (404 beim Build).
- **PKGBUILD** auf die aktuelle Version aktualisiert und vollständig
  (`checkdepends`, `.SRCINFO`) — die 0.4.1→aktuell-Korrektur und das
  Anlegen der fehlenden `.SRCINFO` erfolgten in v0.4.8.
- **`build()`** real getestet: `python -m build --wheel
  --no-isolation` läuft durch, erzeugt `wowusky-0.4.9-...whl`.
- **`package()`** real getestet: `python -m installer` legt
  Entry-Point und alle Module korrekt ab (104 Dateien).
- Alle neun im PKGBUILD referenzierten Dateien (README, LICENSE,
  .desktop, SVG, 5 PNGs) existieren und sind gültig.
- PKGBUILD und `.SRCINFO` gegeneinander auf Konsistenz geprüft.

## Was nur du tun kannst

- Git-Tag `v0.4.9` setzen und pushen (Schritt 1)
- GitHub-Release anlegen (Schritt 1)
- Echte sha256-Summe eintragen — geht erst, wenn der Tarball
  online ist (Schritt 2)
- `makepkg -si` auf einem echten Arch-System (Schritt 3)
- AUR-Account + SSH-Key, dann Push (Schritt 5)
- Maintainer-E-Mail eintragen (Schritt 6)
