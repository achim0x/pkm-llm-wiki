# Release Notes

**Deutsch** · [English](release-notes.md)

## Änderungen seit V0.1.0

Verglichen mit dem Tag `V0.1.0` (Spezifikation 0.18). Spezifikation jetzt **0.26**, Umsetzungsplan
Version 4. Die Paketversion in `pkm-tools/pyproject.toml` steht noch auf `0.1.0`; als nächstes
Release wird **0.2.0** vorgeschlagen.

### Das Wichtigste

- **Installation mit einem Befehl** über `install.sh` / `install.ps1` und den neuen
  Einrichtungsassistenten `pkm setup` – ohne Git und ohne JSON von Hand.
- **Git ist optional**: ohne Git läuft das PKM ohne Versionsgeschichte (`PKM_VERSIONING`).
- **Bilder** in Dokumenten: PNG, JPEG und SVG, eingebettet oder als Anhang, mit Prüfung und Korrektur.
- **Windows** ist gleichwertiger PKM-Rechner neben dem Mac.
- **Beliebiger Cloud-Speicher** (oder keiner): Konfliktkopien aller gängigen Dienste werden erkannt.
- **Durchgehend Englisch**: Code, Meldungen, erzeugte Vault-Dateien und Skills; deutsche
  Abschnittsnamen werden weiter akzeptiert.
- **Obsidian und Cloud-Speicher sind optional.**

### Installation und Einrichtung

- Neue Installer `install.sh` (Mac/Linux) und `install.ps1` (Windows): installieren `uv`, laden das
  Repository-Archiv von GitHub (funktioniert ohne Git), installieren `pkm-tools` und starten
  `pkm setup`. `PKM_ARCHIVE` und `PKM_SETUP_ARGS` erlauben ein lokales Archiv und Läufe ohne Rückfragen.
- Neuer Befehl **`pkm setup`** (wiederholbar): Vault-Ordner (`--vault`), Git-Prüfung und
  -Identität, `config.toml`, `pkm init`, Claude-Desktop-Einträge, Skill-ZIPs, Projektanweisungen
  für „PKM-Pflege“, `pkm doctor`.
- Claude Desktop: `pkm setup` prüft zuerst, ob `pkm` und `pkm-pflege` schon richtig eingetragen
  sind. Nur wenn nicht, zeigt es die Änderung und fragt einmal um Erlaubnis (Sicherung, andere
  Server bleiben erhalten). Bei „nein“ gibt es die JSON-Einträge zum Eintragen von Hand aus.
  `--yes` beantwortet alle Fragen mit Ja; `--claude-config` zeigt auf eine andere Datei.
- Konfiguration in **`config.toml`** im App-Ordner (`PKM_CONFIG`); Umgebungsvariablen haben Vorrang.
- Git wird über `PKM_GIT`, `PATH` und die üblichen Installationsorte gesucht; nur ein
  funktionierendes Git wird verwendet.
- `pkm init` schreibt Obsidian-Einstellungen nach `.obsidian/app.json` und die Obsidian-Eigenschaftstypen.
- Die Skills sind Teil des Python-Pakets (`src/pkm/skills/`).
- Release-Workflow `release.yml` hängt Skill-ZIPs und Wheel an jeden Tag `v*`.
- Die manuelle Installation ohne Installer ist Schritt für Schritt beschrieben
  ([installation.de.md](installation.de.md), Anhang A).

### Betrieb ohne Git

- `PKM_VERSIONING=off` (setzt `pkm setup`, wenn Git fehlt): schreibende Tools schreiben ohne
  Commit, zählen `version:` aber weiter hoch.
- `history`, `read(version)`, `show`, `restore` liefern `not_versioned`; `pkm versions` und
  `commit-wiki` tun nichts; `pending` erkennt Handänderungen über Hashes.
- Zitate älterer Versionen werden gegen den aktuellen Text geprüft, wenn der zitierte Abschnitt
  unverändert ist. Die Schreibsperre liegt in `PKM_CACHE_DIR`. `pkm doctor` meldet einen Hinweis,
  keinen Fehler.
- Wird Git später ergänzt, committet der nächste Pflegelauf die Dokumente.

### Bilder (Spezifikation 0.21, 0.23, 0.24)

- Neue Tools `add_image` und `read_image` (auch in `pkm-pflege`), neuer Parameter `images` mit
  `{{image:<name>}}`-Markern für create/rewrite/append/edit.
- SVG wird bereinigt und verkleinert, PNG geprüft und von Textblöcken befreit, **JPEG**-Import mit
  entfernten Metadaten (Ausrichtung bleibt).
- Kleine Bilder bleiben als Data-URI im Text, große kommen nach `_attachments/` und werden mit dem
  Dokument committet; `read` zeigt Platzhalter, die bytegenau wiederhergestellt werden.
- Standard-Importordner `<vault>/pkm_img_import/` (legt `pkm init` an, steht in `.gitignore`,
  wird von Pflege, Lint und Suche ignoriert).
- Data-URIs werden in jeder Schreibweise erkannt (inline, spitze Klammern, Referenzstil, HTML
  `img`). Nicht konforme werden mit `nonconforming_image` abgelehnt und nur auf Wunsch korrigiert
  (`fix_images=true`, Tool `fix_images`, CLI **`pkm fix-images`**).
- Pflege: geänderte verlinkte Bilddateien erzeugen neue Versionen der nutzenden Dokumente;
  verwaiste Anhänge erscheinen in `_status.md` und im Lint. Lint prüft `[img:<name>]`-Zitate,
  Alternativtext, doppelte Namen und unsichere SVG.

### Pflege und Wiki (Spezifikation 0.19, 0.20)

- Neues Tool `set_document_metadata` in `pkm-pflege` (Titel, Kontext, Tags, Art, Kurzzitat – nach
  Bestätigung); `begin_maintenance` meldet fehlende Felder und bekannte Tags.
- Frontmatter-Felder stehen in Schema-Reihenfolge; einfache Listen ohne Anführungszeichen.
- `read` kann einzelne Abschnitte und Teile liefern (`section`, `offset`/`max_chars`,
  `content=false`); sehr langer Inhalt wird nur auf Anforderung geliefert.
- Lint: weniger Fehlalarme (Unterüberschriften, reine Hervorhebungs-/Linkzeilen, Tabellen mit
  Fußnote), neue Warnung `citation_empty_section`.
- `fix-citations` schreibt Wikilinks verschobener Dokumente um; `finish_maintenance` hebt
  Zitatversionen bei unveränderten Abschnitten und bei Abschnitten, die sich nur in der
  Bildschreibweise geändert haben.
- `pkm versions` committet Handänderungen an `CLAUDE.md` als Nutzer-Commit.
- Inbox-Dateinamen enden jetzt auf das Datum: `<slug>_JJJJ-MM-TT.md` (bei Namensgleichheit
  `<slug>-2_JJJJ-MM-TT.md`). Bei langen Dateinamen wird nur der Slug gekürzt.

### Cloud-Speicher (Spezifikation 0.25)

- Konfliktkopien von Nextcloud/ownCloud, Dropbox, Google Drive, OneDrive, iCloud, Syncthing,
  pCloud, Box und deutschen Clients werden erkannt, am Namen oder als Kopie mit gleicher
  Dokument-ID neben dem Original. Das alte Muster für jedes „Konflikt“ wurde eingeengt, um
  Fehlalarme zu vermeiden.
- `pkm doctor` erkennt Cloud-Ordner aller Dienste, den Dienst des Vaults und nur online
  verfügbare Dateien.
- Ein rein lokaler Vault ohne Cloud-Speicher wird unterstützt.

### Windows

- Windows als PKM-Rechner: Standardordner `%APPDATA%\pkm`, Sperre über `msvcrt`, `os.replace`
  mit Wiederholungen, `core.autocrlf=false` im PKM-Repository, Abhängigkeit `tzdata`,
  UTF-8-Ausgabe der CLI.
- CI testet auf Linux, macOS und Windows (Python 3.12) und führt beide Installer auf allen drei
  Systemen aus.

### Sprache

- Quellcode, Meldungen, CLI-Hilfe, MCP-Tool-Beschreibungen, Commit-Vermerke und erzeugte Dateien
  (`wiki/index.md`, `wiki/_status.md`, `wiki/log.md`, Lint-Berichte) sind englisch.
- Wiki-Seiten nutzen englische Abschnitte (`Content`, `Contradictions / open questions`,
  `See also`, `Citations`); die deutschen Namen werden weiter akzeptiert.

### Dokumentation

- `README.md` ist zweisprachig (erst Englisch, dann Deutsch); neue englische
  Installationsanleitung [installation.md](installation.md) neben der deutschen
  [installation.de.md](installation.de.md).
- Neue [architecture.md](architecture.md) (englisch) mit Installationsablauf und Aufbau von
  pkm-tools, Mermaid-Diagramme.
- Dateien in `docs/` englisch benannt: `specification.md`, `implementation-plan.md`,
  `acceptance.md`, `installation.de.md` (Inhalte weiterhin deutsch).
- Abnahmeprotokoll mit Schritt 0 (Installer und `pkm setup`) und Prüfungen ohne Git.

### Inkompatible Änderungen

- Erzeugte Vault-Dateien und neue Wiki-Seiten sind englisch. Bestehende deutsche Seiten
  funktionieren weiter.
- Neue Inbox-Dateinamen haben das Datum am Ende.
- Die Skills liegen nicht mehr in `pkm-tools/skills/`, sondern im Paket; mit `pkm setup` neu packen.
- Links auf die alten Dateinamen in `docs/` (`spezifikation.md`, `umsetzungsplan.md`,
  `abnahme.md`, `einrichtung.md`) funktionieren nicht mehr.

### Aktualisieren von V0.1.0

1. Installer erneut ausführen (manuelle Aktualisierung: [installation.de.md](installation.de.md),
   Anhang A.3).
2. `pkm setup` ausführen: legt `config.toml` an, prüft die
   Claude-Desktop-Einträge, packt die Skill-ZIPs neu und führt `pkm init` (Importordner,
   `.gitignore`, Obsidian-Einstellungen) und `pkm doctor` aus.
3. Die neuen Skill-ZIPs in Claude Desktop hochladen und Claude Desktop neu starten.
