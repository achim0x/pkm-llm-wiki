# PKM mit LLM-Wiki – Einrichtung

Diese Anleitung richtet das PKM auf dem **PKM-Rechner** ein (Spezifikation 5.5, 7.6, 11, 13, 15.1).
Wie Installer und `pkm setup` intern ablaufen, beschreibt [architecture.md](architecture.md) (englisch,
mit Ablaufdiagrammen).
Der PKM-Rechner ist der eine Rechner, auf dem Claude Desktop, die MCP-Server `pkm-mcp` und
`pkm-pflege-mcp`, die CLI `pkm` und (mit Git) der Versionsverlauf liegen. Das kann ein **Mac** oder
ein **Windows-PC** sein; beide Varianten sind gleichwertig. Weitere Rechner brauchen nur Obsidian und
den Client des Cloud-Speichers.

**Pro Vault genau ein PKM-Rechner.** Der Versionsverlauf liegt lokal auf diesem Rechner und wird
nicht synchronisiert. Ein zweiter PKM-Rechner für denselben Vault würde einen zweiten, abweichenden
Verlauf anlegen.

Kurzfassung:

1. Installer ausführen (installiert uv und das Paket, startet `pkm setup`).
2. Die Fragen von `pkm setup` beantworten (Vault-Ordner, ggf. Git-Name und E-Mail).
3. Die beiden Skill-ZIPs in Claude Desktop hochladen.
4. Projekt „PKM-Pflege“ anlegen.
5. Claude Desktop und Obsidian neu starten.

Platzhalter:

| Platzhalter | Mac | Windows |
|---|---|---|
| `<HOME>` | Home-Verzeichnis, z. B. `/Users/name` | Benutzerordner, z. B. `C:\Users\name` |
| `<VAULT>` | Vault-Ordner im Ordner des Cloud-Speichers | ebenso |
| `<APPDIR>` | `<HOME>/Library/Application Support/pkm` | `%APPDATA%\pkm`, z. B. `C:\Users\name\AppData\Roaming\pkm` |

`<APPDIR>` enthält die Konfigurationsdatei `config.toml`, das Git-Verzeichnis (`<APPDIR>/git`),
den Suchindex (`<APPDIR>/index.db`) und die Skill-ZIPs (`<APPDIR>/skills`). Er liegt bewusst
außerhalb des Cloud-Ordners.

---

## 1. Voraussetzungen

- Client des Cloud-Speichers (Nextcloud, OneDrive, Google Drive, Dropbox, iCloud Drive …),
  Obsidian, Claude Desktop.
- **Git ist optional.** Mit Git bekommt jedes Dokument einen vollständigen Versionsverlauf
  (`history`, Diffs, alte Versionen zurückholen, Pflegeläufe mit `git revert` zurücknehmen). Ohne
  Git läuft das PKM ohne Versionsverwaltung: Dokumente bekommen weiter IDs und Versionsnummern,
  Änderungen erkennt der Pflegelauf über Hashes, aber es gibt keinen Verlauf und nichts
  wiederherzustellen. Git lässt sich jederzeit nachrüsten (Abschnitt 3).

  Installation von Git, falls gewünscht: <https://git-scm.com/install/>. Auf dem Mac genügt
  `xcode-select --install`, unter Windows `winget install Git.Git` (Standardoption „Git from the
  command line and also from 3rd-party software“ beibehalten).
- Python muss nicht installiert sein; der Installer bringt `uv` mit, das eine passende
  Python-Version verwaltet.

## 2. Installation

Mac (Terminal):

```bash
curl -LsSf https://raw.githubusercontent.com/achim0x/pkm-llm-wiki/main/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/achim0x/pkm-llm-wiki/main/install.ps1 | iex"
```

Der Installer

1. installiert `uv` nach `<HOME>/.local/bin`, falls es fehlt,
2. prüft, ob Git vorhanden ist, und gibt sonst einen Hinweis aus,
3. lädt `pkm-tools` von GitHub und installiert die Befehle `pkm`, `pkm-mcp` und `pkm-pflege-mcp`
   nach `<HOME>/.local/bin` (unter Windows mit Endung `.exe`),
4. startet `pkm setup` (Abschnitt 3).

Außer `uv` und dem Paket ändert der Installer nichts ohne Rückfrage. **Aktualisieren:** den
Installer erneut ausführen. Meldet ein neues Terminal, dass `pkm` nicht gefunden wird, einmal
`uv tool update-shell` ausführen.

Installation von Hand statt mit dem Installer: Anhang A.

## 3. `pkm setup`

`pkm setup` führt durch die Einrichtung und lässt sich jederzeit erneut ausführen; jeder Schritt ist
idempotent.

1. **Vault-Ordner** abfragen (absoluter Pfad im Ordner des Cloud-Speichers; wird angelegt, wenn er
   fehlt). Erkannt wird auch der Cloud-Dienst; Dateien, die nur online vorliegen, meldet der
   Assistent (Abschnitt 7).
2. **Git prüfen.** Ist Git vorhanden, wird die Versionsverwaltung eingeschaltet. Fehlt die
   Git-Identität, fragt `pkm setup` nach Name und E-Mail und trägt sie nur für das PKM-Repo ein;
   die Commit-Signierung wird für das PKM-Repo abgeschaltet. **Fehlt Git**, erscheint ein Hinweis
   und das PKM läuft ohne Versionsverwaltung.
3. **Konfigurationsdatei** `<APPDIR>/config.toml` schreiben (Vault-Pfad, Vault-Name,
   Versionsverwaltung an oder aus, Pfad zu Git). Server und CLI lesen sie; gesetzte
   Umgebungsvariablen haben Vorrang.
4. **`pkm init`** ausführen: Ordnerstruktur, `CLAUDE.md`, `.gitignore`, `.pkm/state.json`,
   Obsidian-Einstellungen (`.obsidian/app.json`) und Property-Typen (`.obsidian/types.json`), mit
   Git zusätzlich das Repo außerhalb des Vaults mit einem ersten Commit. Bestehende Notizen bleiben
   unverändert.
5. **Claude Desktop** einrichten: Die Server `pkm` und `pkm-pflege` werden in
   `claude_desktop_config.json` eingetragen (nur mit `command`, ohne weitere Angaben). Andere Server
   bleiben unverändert; vorher wird eine Sicherungskopie der Datei angelegt; ein abweichender
   Eintrag wird erst nach Bestätigung ersetzt.
6. **Skill-ZIPs** nach `<APPDIR>/skills/` schreiben (Abschnitt 4).
7. Die **Projektanweisung** für „PKM-Pflege“ ausgeben (Abschnitt 5).
8. **`pkm doctor`** ausführen und Fehler nennen.

Optionen (alle optional): `--vault <ordner>`, `--vault-name <name>`, `--git-name <name>`,
`--git-email <adresse>`, `--yes` (Standardwerte ohne Rückfrage), `--claude-config <datei>`,
`--no-claude` (Claude Desktop nicht anfassen), `--skills-dir <ordner>`, `--json`.

**Versionsverwaltung nachträglich einschalten:** Git installieren (Abschnitt 1) und `pkm setup`
erneut ausführen. Der Assistent findet Git, legt das Repo an und committet die Grunddateien
(`pkm: init`). Die Dokumente kommen zu Beginn des nächsten Pflegelaufs (`pkm versions`) bzw. vor ihrer
nächsten Änderung aus einem Chat mit ihrer aktuellen Versionsnummer in Git (Notiz „first version by
hand“). Ein Verlauf für die Zeit davor entsteht nicht.

**Nach `pkm setup`:** Claude Desktop vollständig beenden (unter Windows auch im Infobereich der
Taskleiste) und neu starten. Im Chat erscheinen unter den Werkzeugen die 15 `pkm`-Tools (`search`,
`read`, `read_image`, `history`, `show_citations`, `read_index`, `list_unprocessed`,
`create_document`, `rewrite_document`, `append_to_document`, `edit_document`, `update_frontmatter`,
`add_image`, `fix_images`, `restore_document`) sowie der Server `pkm-pflege`.

**`pkm-pflege` nur zur Pflege einschalten.** Claude Desktop gibt Server allen Unterhaltungen frei;
auf ein Projekt beschränken lässt er sich nicht. Deshalb `pkm-pflege` in normalen Unterhaltungen im
Werkzeug-Menü der Unterhaltung ausschalten und nur in Pflege-Unterhaltungen einschalten. Der Server
schreibt nur in `wiki/` und `.pkm/state.json`, an Dokumenten nur `id`/`version` und nach deiner
Bestätigung `title`, `context`, `tags`, `kind`, `short_citation`. Mit Git ist jeder Pflegelauf ein
eigener Agenten-Commit und lässt sich mit `git revert` zurücknehmen.

## 4. Skills hochladen

`pkm setup` legt `<APPDIR>/skills/pkm-access.zip` und `pkm-wiki.zip` an (zusätzlich hängen sie an
jeder GitHub-Release). In Claude Desktop unter den Einstellungen bei den Skills (je nach
App-Version „Einstellungen → Funktionen → Skills“) beide Dateien hochladen und aktivieren:

- `pkm-access` – für alle normalen Chats (Ablegen, Fortsetzen, Abfragen, Quellen).
- `pkm-wiki` – für das Pflegeprojekt.

Nach einem Update die Skills erneut hochladen (die alten ersetzen). Bestehende andere Skills
bleiben unberührt.

## 5. Projekt „PKM-Pflege“

Die Pflege läuft in Claude Desktop (Chat oder Cowork) über den Server `pkm-pflege`. Eine Shell auf
diesem Rechner ist nicht nötig.

1. In Claude Desktop ein Projekt „PKM-Pflege“ anlegen.
2. Projektanweisung (gibt auch `pkm setup` aus):

   > This is the maintenance project for the PKM. Use the skill `pkm-wiki` and the tools of the
   > server `pkm-pflege`. You do not change documents in `documents/`.

3. In der Pflege-Unterhaltung den Server `pkm-pflege` einschalten.
4. Optional den Vault-Ordner verbinden („+“ → „Ordner hinzufügen“). Das ist nur nötig, damit
   Claude den Inhalt von PDFs und Bildern lesen kann; Markdown liest es über `read`.
5. Pflegeläufe werden manuell angestoßen: „Verarbeite neue Dokumente“, „Lint“.
   Eine geplante Aufgabe (täglich „Ingest, danach Lint“) wird erst später und nur auf
   ausdrückliche Anweisung eingerichtet. Geplante Cowork-Aufgaben laufen in der Cloud und
   erreichen `pkm-pflege` voraussichtlich nur, solange dieser Rechner an und Claude Desktop
   geöffnet ist.

## 6. Obsidian

Den Vault-Ordner als Vault öffnen. `pkm init` (über `pkm setup`) trägt die Einstellungen aus
Spezifikation 13 in `.obsidian/app.json` ein; Obsidian übernimmt sie nach einem Neustart:

| Einstellung | Wert |
|---|---|
| Dateien & Links → Interne Links automatisch aktualisieren | an |
| Dateien & Links → Neues Link-Format | Absoluter Pfad im Vault |
| Dateien & Links → Wikilinks verwenden | an |
| Dateien & Links → Standardordner für Anhänge | `documents/_attachments` |
| Dateien & Links → Ausgeschlossene Dateien | `.pkm/` |

Fehlende Werte werden ergänzt, von dir gesetzte abweichende Werte bleiben und werden als Warnung
gemeldet (`pkm init`, `pkm doctor`). Ebenso legt `pkm init` die **Property-Typen** in
`.obsidian/types.json` an bzw. ergänzt sie:

| Feld | Typ |
|---|---|
| `date_markdown`, `date_updated` | Datum & Uhrzeit |
| `version` | Zahl |
| `related`, `sources` | Liste |
| `title`, `short_citation`, `date_document`, `status_markdown`, `toolchain_markdown`, `id`, `context`, `kind` | Text |
| `tags`, `aliases` | Obsidian-Standard |

Läuft Obsidian während `pkm setup`, Obsidian danach neu starten. Von Hand ändert man einen Typ im
Eigenschaften-Bereich einer Notiz über das Symbol links neben dem Feldnamen oder in der Seitenleiste
**Alle Eigenschaften** per Rechtsklick.

**Web Clipper (optional):** [Obsidian Web Clipper](https://obsidian.md/clipper) ist kein
Obsidian-Plugin, sondern eine Browser-Erweiterung (Chrome, Firefox, Safari, Edge). Die
Einstellungen liegen in der Erweiterung selbst (Symbol in der Browserleiste → Zahnrad):

- Allgemein → Vaults: Name des Vaults eintragen.
- Vorlagen → Standardvorlage → Speicherort der Notiz (*Note location*): `documents/_inbox`.

Die Vorlage außerdem an das Schema anpassen: `title` (Seitentitel), `source` (URL),
`date_document` (Veröffentlichungsdatum, falls vorhanden), `date_markdown` (Zeitpunkt des Clippens
im Format `YYYY-MM-DDTHH:MM:SS`), `toolchain_markdown: Obsidian Web Clipper`, `tags`.

**Bereits umgewandelte Normen** in den Vault legen: Normtitel enthalten oft `: ` und müssen dann in
Anführungszeichen stehen. `pkm lint` zeigt betroffene Dateien, `pkm fix-frontmatter` listet sie
auf, mit Ziel oder `--all` repariert er sie.

**Bilder:** Fotos und Screenshots aus einem Chat übernimmt der Server nur aus dem Importordner
`pkm_img_import/` im Vault (PNG, JPEG, SVG). Er ist nicht in Git und von Pflegelauf, Lint und Suche
ausgenommen; weil er im Cloud-Ordner liegt, kannst du Bilder auch vom Smartphone hineinlegen.
Eingebettete Bilder (Data-URIs) zeigt Obsidian im Lese- und Live-Vorschau-Modus. Nach der
Einrichtung einmal ein Dokument mit einem eingebetteten PNG und SVG aus einem Chat anlegen lassen
und in Obsidian prüfen.

Optional: Dataview, Graph View. Die Einstellungen in `.obsidian/` werden über den Cloud-Speicher auch
auf die anderen Rechner übertragen. Kein Obsidian-Git-Plugin verwenden.

## 7. Cloud-Speicher

Jeder Dienst, der einen normalen lokalen Ordner synchronisiert, ist geeignet (Nextcloud/ownCloud,
OneDrive, Google Drive, Dropbox, iCloud Drive, Syncthing …). Wichtig ist vor allem, den
**Vault-Ordner immer lokal** zu halten (keine Dateien „nur online“). Was je Dienst zu beachten ist,
steht in der README unter „Cloud-Speicher: Stolpersteine“ und in Spezifikation 5.5.

Ausnahmen von der Synchronisation sind nicht nötig, weil Git und Suchindex außerhalb liegen.
Optional `.obsidian/workspace*.json` ausschließen (geräteabhängige Dateien).

## 8. Datensicherung

Mit Git existiert der Versionsverlauf nur auf dem PKM-Rechner unter `<APPDIR>/git`. Diesen Ordner in
die Datensicherung aufnehmen; der Suchindex (`<APPDIR>/index.db`) ist nur ein Cache und kann fehlen.
Ohne Git sichert der Cloud-Speicher (mit seinen Dateiversionen, sofern der Dienst welche bietet) den
Vault; einen eigenen Verlauf gibt es dann nicht.

- **Mac:** Time Machine sichert `~/Library/Application Support/pkm/` automatisch mit.
- **Windows:** Der Dateiversionsverlauf sichert `AppData` standardmäßig **nicht**. Entweder
  `%APPDATA%\pkm\git` in einem Backup-Programm ausdrücklich aufnehmen, oder das Git-Verzeichnis
  von Anfang an in einen gesicherten Ordner außerhalb jedes Cloud-Ordners legen, z. B.
  `C:\Users\name\pkm-git`: in `<APPDIR>\config.toml` die Zeile
  `PKM_GIT_DIR = "C:\\Users\\name\\pkm-git"` ergänzen und `pkm setup` erneut ausführen.

## 9. Probelauf

Mit drei bis fünf eigenen Dokumenten (es gibt keine Startbefüllung):

1. **Aus einem Chat ablegen:** „Leg das Ergebnis ins PKM.“ → Entwurf bestätigen → Datei in
   `documents/_inbox/` mit `id` und `version: 1`.
2. **Eigene Notiz:** in Obsidian eine Notiz unter `documents/…` anlegen (ohne Frontmatter).
3. **PDF:** ein Datenblatt nach `documents/…` legen.
4. **Pflegelauf** im Projekt: „Verarbeite neue Dokumente.“ → Zusammenfassungen, Themenseiten mit
   Belegen, Index, Status, Log (mit Git zusätzlich ein Agenten-Commit).
5. **Einsortieren** in Obsidian (Dokument aus `_inbox/` verschieben) → Belege zeigen auf den
   neuen Ort.
6. **Fortsetzen** in einem neuen Chat: „Führ die Diskussion zu … weiter“ → Vorher/Nachher,
   Bestätigung, `version: 2`.
7. **Quellen:** „Woher stammt die Angabe …?“ → Original, Abschnitt, Zitat, Version, Status.
8. Abschluss: `pkm doctor` und `pkm lint` ohne Fehler.

Die vollständige Abnahme steht in [abnahme.md](abnahme.md) bzw. Abschnitt 14 der Spezifikation.

## 10. Fehlersuche

| Problem | Prüfen |
|---|---|
| Tools erscheinen nicht in Claude Desktop | `pkm setup` erneut ausführen (trägt die Server ein), Claude Desktop vollständig beenden und neu starten, Log von Claude Desktop |
| `git_unavailable` | `pkm doctor`: Git gefunden, Repo vorhanden, Identität gesetzt. Git deinstalliert? `pkm setup` erneut ausführen (schaltet die Versionsverwaltung ab) |
| `not_versioned` bei `history`/`restore_document` | Versionsverwaltung ist aus (kein Git) oder die Datei liegt in `scratch/` |
| `commit_failed` | Signierung (`commit.gpgsign`), Schreibrechte; die Datei wurde zurückgesetzt |
| `conflict` | Datei wurde inzwischen geändert (z. B. in Obsidian oder per Sync) – neu lesen |
| `config_error` | `<APPDIR>/config.toml` prüfen bzw. `pkm setup` erneut ausführen |
| Suche findet nichts Neues | `pkm reindex` (der Index ist nur ein Cache) |
| Konfliktkopien („conflicted copy“ …) | In Obsidian zusammenführen, Kopie löschen, dann `pkm versions` |

Logs von Claude Desktop: Mac `~/Library/Logs/Claude/`, Windows `%APPDATA%\Claude\logs\`.
Protokoll aller MCP-Vorgänge: `<VAULT>/.pkm/mcp.log`. `pkm doctor` nennt auch, ob die
Versionsverwaltung an ist und welches Git verwendet wird.

Versionsgeschichte direkt ansehen (mit Git):

Mac:

```bash
git --git-dir="<HOME>/Library/Application Support/pkm/git" --work-tree="<VAULT>" log --oneline
```

Windows:

```powershell
git --git-dir="$env:APPDATA\pkm\git" --work-tree="<VAULT>" log --oneline
```

---

## Anhang A: Installation von Hand

Statt des Installers geht es auch Schritt für Schritt.

1. `uv` installieren:

   Mac:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   Windows:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. Paket installieren. Mit Git direkt aus GitHub (Aktualisieren dann mit `uv tool upgrade pkm-tools`):

   ```bash
   uv tool install "git+https://github.com/achim0x/pkm-llm-wiki#subdirectory=pkm-tools"
   ```

   Ohne Git: das ZIP des Repositorys von GitHub laden, entpacken und den Ordner `pkm-tools`
   installieren:

   ```bash
   uv tool install --force <ENTPACKT>/pkm-tools
   ```

3. `pkm setup` ausführen.

**Ohne `pkm setup`** (nur für Sonderfälle): `config.toml` von Hand anlegen, `pkm init` ausführen und
die Server in Claude Desktop eintragen.

`<APPDIR>/config.toml` (flache Schlüssel wie die Umgebungsvariablen aus Spezifikation 7.1):

```toml
PKM_ROOT = "/Users/name/Nextcloud/Vault"
PKM_VAULT_NAME = "Vault"
PKM_VERSIONING = true
PKM_GIT = "/usr/bin/git"
```

`PKM_VERSIONING = false` schaltet die Versionsverwaltung ab. Weitere optionale Schlüssel:
`PKM_GIT_DIR`, `PKM_CACHE_DIR`, `PKM_TZ`, `PKM_MAX_KB`, `PKM_GIT_AUTHOR`, `PKM_IMPORT_DIR`,
`PKM_INLINE_MAX_KB` (24), `PKM_SVG_MAX_KB` (200), `PKM_IMAGE_MAX_MB` (5), `PKM_IMAGE_PARAM_MAX_KB`
(512), `PKM_SVG_RASTER` (`false`; zum Rastern von SVG zusätzlich das Paket `cairosvg` installieren).
Eine andere Datei wählt die Umgebungsvariable `PKM_CONFIG`.

Eintrag in `claude_desktop_config.json` (Mac
`<HOME>/Library/Application Support/Claude/`, Windows `%APPDATA%\Claude\`; in Claude Desktop auch
über Einstellungen → Entwickler → „Konfiguration bearbeiten“); in JSON alle Pfade absolut und unter
Windows jeden Backslash verdoppeln:

```json
{
  "mcpServers": {
    "pkm": { "command": "<HOME>/.local/bin/pkm-mcp" },
    "pkm-pflege": { "command": "<HOME>/.local/bin/pkm-pflege-mcp" }
  }
}
```

Unter Windows heißen die Programme `pkm-mcp.exe` und `pkm-pflege-mcp.exe`. Umgebungsvariablen in
`env` sind weiterhin möglich und haben Vorrang vor `config.toml`. Git findet der Server über
`PKM_GIT`, über `PATH` oder an den üblichen Orten (`/opt/homebrew/bin`, `/usr/local/bin`,
`/usr/bin`, `C:\Program Files\Git\cmd`).
