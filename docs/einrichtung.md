# PKM mit LLM-Wiki – Einrichtung

Diese Anleitung richtet das PKM auf dem **PKM-Rechner** ein (Spezifikation 5.5, 7.6, 11, 13).
Der PKM-Rechner ist der eine Rechner, auf dem Claude Desktop, der MCP-Server `pkm-mcp`, die CLI
`pkm` und der Git-Verlauf liegen. Das kann ein **Mac** oder ein **Windows-PC** sein; beide
Varianten sind gleichwertig. Weitere Rechner brauchen nur Obsidian und Nextcloud.

**Pro Vault genau ein PKM-Rechner.** Der Versionsverlauf liegt lokal auf diesem Rechner und wird
nicht synchronisiert. Ein zweiter PKM-Rechner für denselben Vault würde einen zweiten, abweichenden
Verlauf anlegen.

Wo sich Mac und Windows unterscheiden, stehen beide Varianten untereinander. Befehle für Windows
sind für **PowerShell** geschrieben.

Platzhalter:

| Platzhalter | Mac | Windows |
|---|---|---|
| `<HOME>` | Home-Verzeichnis, z. B. `/Users/name` | Benutzerordner, z. B. `C:\Users\name` |
| `<VAULT>` | Name des Vault-Ordners in der Nextcloud | ebenso |
| `<REPO>` | Ort dieses Repositorys (außerhalb der Nextcloud) | ebenso |
| `<APPDIR>` | `<HOME>/Library/Application Support/pkm` | `%APPDATA%\pkm`, z. B. `C:\Users\name\AppData\Roaming\pkm` |

`<APPDIR>` ist der Standardort für Git-Verzeichnis (`<APPDIR>/git`) und Suchindex
(`<APPDIR>/index.db`). Er muss nicht eingestellt werden.

---

## 1. Voraussetzungen

- Nextcloud-Desktop-Client, Obsidian, Claude Desktop
- **Git** in einer aktuellen Version, Installation nach <https://git-scm.com/install/>.
  Unter Windows im Installer die Standardoption „Git from the command line and also from
  3rd-party software“ beibehalten, dann steht Git im System-`PATH`.
  Prüfen (neues Terminal bzw. neue PowerShell öffnen):

  ```bash
  git --version
  ```

- **uv** (Python-Werkzeug), installiert nach `<HOME>/.local/bin`.

  Mac:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  Windows:

  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

Python selbst muss nicht installiert sein, `uv` bringt eine passende Version mit.

## 2. Paket installieren

Repository holen (außerhalb der Nextcloud), dann die Befehle `pkm`, `pkm-mcp` und `pkm-pflege-mcp`
installieren:

```bash
git clone https://github.com/achim0x/pkm-llm-wiki.git <REPO>
```

```bash
uv tool install <REPO>/pkm-tools
```

Danach liegen `pkm`, `pkm-mcp` und `pkm-pflege-mcp` in `<HOME>/.local/bin/` (unter Windows mit
Endung `.exe`). Meldet `uv`, dass der Ordner nicht im `PATH` steht, einmal `uv tool update-shell`
ausführen und das Terminal neu öffnen.

Aktualisieren nach einem `git pull`:

```bash
uv tool install --reinstall <REPO>/pkm-tools
```

## 3. Git-Identität

Ohne Name und E-Mail verweigert der Server alle schreibenden Tools:

```bash
git config --global user.name "Vorname Nachname"
```

```bash
git config --global user.email "name@example.org"
```

Ist in deiner globalen Git-Konfiguration `commit.gpgsign` eingeschaltet, kann das Signieren aus
Claude Desktop heraus scheitern (`pkm doctor` warnt). Dann für das PKM-Repo abschalten (nach
Schritt 4):

Mac:

```bash
git --git-dir="<HOME>/Library/Application Support/pkm/git" config commit.gpgsign false
```

Windows:

```powershell
git --git-dir="$env:APPDATA\pkm\git" config commit.gpgsign false
```

## 4. Vault anlegen

Der Vault liegt in der Nextcloud, Git-Verzeichnis und Suchindex liegen außerhalb unter
`<APPDIR>` (Standard, nichts einzustellen).

Mac:

```bash
export PKM_ROOT="<HOME>/Nextcloud/<VAULT>"
```

Windows:

```powershell
$env:PKM_ROOT = "$env:USERPROFILE\Nextcloud\<VAULT>"
```

Dann auf beiden Systemen:

```bash
pkm init
```

```bash
pkm doctor
```

`pkm init` ist idempotent und legt an: `documents/_inbox/`, `documents/_attachments/`,
`wiki/` (mit `index.md`, `log.md`, `_status.md` und den Unterordnern), `scratch/`, `CLAUDE.md`,
`.pkm/state.json`, `.gitignore`, `.obsidian/types.json` (Property-Typen, siehe Abschnitt 8) sowie das Git-Verzeichnis mit einem ersten Commit.
Liegen im Ordner schon Notizen, bleiben sie unverändert; sie bekommen beim ersten Pflegelauf
eine ID (`pkm ids`). Unter Windows schaltet `pkm init` für das PKM-Repo `core.autocrlf` ab, damit
Git die Zeilenenden nicht verändert.

Die CLI findet den Vault auch ohne `PKM_ROOT`, wenn sie in einem Ordner des Vaults aufgerufen
wird (sie sucht aufwärts nach `.pkm/state.json`).

**Wichtig:** `PKM_GIT_DIR` und `PKM_CACHE_DIR` dürfen nie in der Nextcloud liegen.
`pkm doctor` prüft das.

## 5. MCP-Server in Claude Desktop

Konfigurationsdatei (anlegen, falls nicht vorhanden; bestehende Einträge unter `mcpServers`
behalten). In Claude Desktop erreichbar über Einstellungen → Entwickler → „Konfiguration
bearbeiten“.

| System | Datei |
|---|---|
| Mac | `<HOME>/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Mac:

```json
{
  "mcpServers": {
    "pkm": {
      "command": "<HOME>/.local/bin/pkm-mcp",
      "env": {
        "PKM_ROOT": "<HOME>/Nextcloud/<VAULT>",
        "PKM_VAULT_NAME": "<VAULT>",
        "PATH": "<GITDIR>:/usr/bin:/bin"
      }
    },
    "pkm-pflege": {
      "command": "<HOME>/.local/bin/pkm-pflege-mcp",
      "env": {
        "PKM_ROOT": "<HOME>/Nextcloud/<VAULT>",
        "PKM_VAULT_NAME": "<VAULT>",
        "PATH": "<GITDIR>:/usr/bin:/bin"
      }
    }
  }
}
```

Windows (in JSON jeden Backslash verdoppeln):

```json
{
  "mcpServers": {
    "pkm": {
      "command": "C:\\Users\\name\\.local\\bin\\pkm-mcp.exe",
      "env": {
        "PKM_ROOT": "C:\\Users\\name\\Nextcloud\\<VAULT>",
        "PKM_VAULT_NAME": "<VAULT>"
      }
    },
    "pkm-pflege": {
      "command": "C:\\Users\\name\\.local\\bin\\pkm-pflege-mcp.exe",
      "env": {
        "PKM_ROOT": "C:\\Users\\name\\Nextcloud\\<VAULT>",
        "PKM_VAULT_NAME": "<VAULT>"
      }
    }
  }
}
```

- **Zwei Server:** `pkm` (Tools für alle Chats: suchen, lesen, ablegen, fortschreiben) und
  `pkm-pflege` (Wiki-Pflege: `begin_maintenance`, `write_wiki_page`, `set_document_metadata`,
  `finish_maintenance` plus die lesenden Tools). Beide laufen auf diesem Rechner; Claude Desktop und Cowork erreichen sie,
  solange Claude Desktop geöffnet ist.
- JSON kennt weder `~` noch Umgebungsvariablen (`%APPDATA%`, `$HOME`): alle Pfade absolut.
- **`PATH` (Mac):** Claude Desktop startet MCP-Server mit minimaler Umgebung, ohne das
  Shell-Profil. `pkm-mcp` ruft intern `git` auf und muss es über `PATH` finden. `<GITDIR>` ist der
  Ordner, in dem `git` liegt:

  ```bash
  dirname "$(command -v git)"
  ```

  | Ausgabe von `command -v git` | Eintrag in der Config |
  |---|---|
  | `/usr/bin/git` (Xcode Command Line Tools) | `"PATH": "/usr/bin:/bin"` |
  | `/opt/homebrew/bin/git` (Homebrew, Apple Silicon) | `"PATH": "/opt/homebrew/bin:/usr/bin:/bin"` |
  | `/usr/local/bin/git` (Homebrew Intel, Installer) | `"PATH": "/usr/local/bin:/usr/bin:/bin"` |
- **`PATH` (Windows):** normalerweise nicht nötig, weil der Git-Installer Git in den System-`PATH`
  einträgt. Meldet `pkm-mcp` trotzdem `git_unavailable`, ergänzen:
  `"PATH": "C:\\Program Files\\Git\\cmd;C:\\Windows\\System32"` (Trennzeichen `;`).
- `PKM_VAULT_NAME` ist optional und sorgt für klickbare `obsidian://`-Links in Quellenangaben.
- Alternative ohne Installation (wie Spezifikation 7.6):
  `"command": "<HOME>/.local/bin/uvx"` (Windows: `uvx.exe`),
  `"args": ["--from", "<REPO>/pkm-tools", "pkm-mcp"]`.

Claude Desktop vollständig beenden (unter Windows auch im Infobereich der Taskleiste) und neu
starten. Im Chat sollten unter den Werkzeugen die 14 `pkm`-Tools erscheinen (`search`, `read`,
`read_image`, `history`, `show_citations`, `read_index`, `list_unprocessed`, `create_document`,
`rewrite_document`, `append_to_document`, `edit_document`, `update_frontmatter`, `add_image`,
`restore_document`) sowie der Server `pkm-pflege`.

**Importordner für Bilder:** Fotos und Screenshots aus einem Chat übernimmt der Server nur aus
`PKM_IMPORT_DIR` (Standard `<HOME>/Downloads/pkm-import`, unter Windows
`%USERPROFILE%\Downloads\pkm-import`). Den Ordner einmal anlegen. Er muss außerhalb des Vaults
liegen (`pkm doctor` prüft das). Weitere Einstellungen für Bilder (alle optional, in `env` der
Config): `PKM_INLINE_MAX_KB` (24), `PKM_SVG_MAX_KB` (200), `PKM_IMAGE_MAX_MB` (5),
`PKM_IMAGE_PARAM_MAX_KB` (512), `PKM_SVG_RASTER` (`false`; zum Rastern von SVG zusätzlich das Paket
`cairosvg` installieren).

**`pkm-pflege` nur zur Pflege einschalten.** Claude Desktop gibt Server allen Unterhaltungen frei;
auf ein Projekt beschränken lässt er sich nicht. Deshalb `pkm-pflege` in normalen Unterhaltungen
im Werkzeug-Menü der Unterhaltung ausschalten und nur in Pflege-Unterhaltungen einschalten. Der
Server schreibt nur in `wiki/` und `.pkm/state.json`, an Dokumenten nur `id`/`version` und nach
deiner Bestätigung `title`, `context`, `tags`, `kind`, `short_citation`; jeder Pflegelauf ist ein eigener
Agenten-Commit und lässt sich mit `git revert` zurücknehmen.

## 6. Skills installieren

Die Skills liegen in `<REPO>/pkm-tools/skills/`. Jeden Ordner als ZIP packen:

Mac:

```bash
cd <REPO>/pkm-tools/skills && zip -r pkm-access.zip pkm-access && zip -r pkm-wiki.zip pkm-wiki
```

Windows:

```powershell
cd <REPO>\pkm-tools\skills; Compress-Archive -Force pkm-access pkm-access.zip; Compress-Archive -Force pkm-wiki pkm-wiki.zip
```

In Claude Desktop unter den Einstellungen bei den Skills (je nach App-Version „Einstellungen →
Funktionen → Skills“) beide ZIP-Dateien hochladen und aktivieren:

- `pkm-access` – für alle normalen Chats (Ablegen, Fortsetzen, Abfragen, Quellen).
- `pkm-wiki` – für das Pflegeprojekt.

Bestehende andere Skills bleiben unberührt (keine Startbefüllung).

## 7. Projekt „PKM-Pflege“

Die Pflege läuft in Claude Desktop (Chat oder Cowork) über den Server `pkm-pflege`. Eine Shell auf
diesem Rechner ist nicht nötig: Cowork führt Befehle ohnehin nur in einer abgeschotteten
Umgebung aus, in der `pkm` und das Git-Verzeichnis fehlen.

1. In Claude Desktop ein Projekt „PKM-Pflege“ anlegen.
2. Projektanweisung:

   > Dies ist das Pflegeprojekt für das PKM. Nutze den Skill `pkm-wiki` und die Tools des Servers
   > `pkm-pflege`. Dokumente in `documents/` änderst du nicht.

3. In der Pflege-Unterhaltung den Server `pkm-pflege` einschalten (siehe Abschnitt 5).
4. Optional den Vault-Ordner verbinden („+“ → „Ordner hinzufügen“). Das ist nur nötig, damit
   Claude den Inhalt von PDFs und Bildern lesen kann; Markdown liest es über `read`.
5. Pflegeläufe werden manuell angestoßen: „Verarbeite neue Dokumente“, „Lint“.
   Eine geplante Aufgabe (täglich „Ingest, danach Lint“) wird erst später und nur auf
   ausdrückliche Anweisung eingerichtet. Geplante Cowork-Aufgaben laufen in der Cloud und
   erreichen `pkm-pflege` voraussichtlich nur, solange dieser Rechner an und Claude Desktop
   geöffnet ist.

Die CLI `pkm` bleibt für Einrichtung und Fehlersuche im Terminal (`pkm init`, `pkm doctor`,
`pkm fix-frontmatter` …).

## 8. Obsidian

Den Vault-Ordner in der Nextcloud als Vault öffnen und einstellen:

| Einstellung | Wert |
|---|---|
| Dateien & Links → Interne Links automatisch aktualisieren | an |
| Dateien & Links → Neues Link-Format | Absoluter Pfad im Vault |
| Dateien & Links → Wikilinks verwenden | an |
| Dateien & Links → Standardordner für Anhänge | `documents/_attachments` |
| Dateien & Links → Ausgeschlossene Dateien | `.pkm/` |

**Property-Typen:** `pkm init` legt `.obsidian/types.json` an bzw. ergänzt fehlende Felder;
von dir gesetzte Typen bleiben unverändert, Abweichungen meldet `pkm init` als Warnung und
`pkm doctor`. Läuft Obsidian dabei, liest es die Datei erst nach einem Neustart. Obsidian legt den
Typ vault-weit pro Feldname fest:

| Feld | Typ |
|---|---|
| `date_markdown`, `date_updated` | Datum & Uhrzeit |
| `version` | Zahl |
| `related`, `sources` | Liste |
| `title`, `short_citation`, `date_document`, `status_markdown`, `toolchain_markdown`, `id`, `context`, `kind` | Text |
| `tags`, `aliases` | Obsidian-Standard |

Von Hand geht es in Obsidian so (es gibt keine eigene Einstellungsseite dafür):

1. Eine Notiz öffnen, die das Feld im Frontmatter hat (z. B. ein aus dem Chat abgelegtes Dokument).
2. Im Eigenschaften-Bereich oben in der Notiz auf das **Symbol links neben dem Feldnamen** klicken.
3. **Eigenschaftstyp** (*Property type*) wählen.

Alle Felder des Vaults auf einmal zeigt die Seitenleiste **Alle Eigenschaften** (Kernplugin
„Eigenschaftenansicht“, Befehl „Eigenschaften anzeigen“); dort per Rechtsklick auf ein Feld den Typ
ändern.

Alternativ die Datei `<VAULT>/.obsidian/types.json` bei **geschlossenem** Obsidian anlegen bzw.
ergänzen (bestehende Einträge behalten):

```json
{
  "types": {
    "date_markdown": "datetime",
    "date_updated": "datetime",
    "version": "number",
    "related": "multitext",
    "sources": "multitext",
    "title": "text",
    "short_citation": "text",
    "date_document": "text",
    "status_markdown": "text",
    "toolchain_markdown": "text",
    "id": "text",
    "context": "text",
    "kind": "text"
  }
}
```

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

**Bilder testen:** Eingebettete Bilder (Data-URIs) zeigt Obsidian im Lese- und Live-Vorschau-Modus.
Nach der Einrichtung einmal ein Dokument mit einem eingebetteten PNG und SVG (auch mit `|400`
im Alternativtext) aus einem Chat anlegen lassen und in Obsidian prüfen.

Optional: Dataview, Graph View. Die Einstellungen in `.obsidian/` werden über Nextcloud auch
auf die anderen Rechner übertragen. Kein Obsidian-Git-Plugin verwenden.

`pkm doctor` prüft die Einstellungen aus `.obsidian/app.json`.

## 9. Nextcloud

Keine Ausnahmen nötig, weil Git und Suchindex außerhalb liegen. Optional
`.obsidian/workspace*.json` in Nextcloud ignorieren (geräteabhängige Dateien).

## 10. Datensicherung

Der Versionsverlauf existiert nur auf dem PKM-Rechner unter `<APPDIR>/git`. Diesen Ordner in die
Datensicherung aufnehmen; der Suchindex (`<APPDIR>/index.db`) ist nur ein Cache und kann fehlen.

- **Mac:** Time Machine sichert `~/Library/Application Support/pkm/` automatisch mit.
- **Windows:** Der Dateiversionsverlauf sichert `AppData` standardmäßig **nicht**. Entweder
  `%APPDATA%\pkm\git` in einem Backup-Programm ausdrücklich aufnehmen, oder das Git-Verzeichnis
  von Anfang an in einen gesicherten Ordner außerhalb der Nextcloud legen, z. B.
  `C:\Users\name\Documents\pkm-git`, und `PKM_GIT_DIR` vor `pkm init` (in PowerShell) und in der
  Claude-Desktop-Config (`"PKM_GIT_DIR": "C:\\Users\\name\\Documents\\pkm-git"`) setzen.
  Der Dokumente-Ordner darf dabei nicht von OneDrive synchronisiert werden.

## 11. Probelauf

Mit drei bis fünf eigenen Dokumenten (es gibt keine Startbefüllung):

1. **Aus einem Chat ablegen:** „Leg das Ergebnis ins PKM.“ → Entwurf bestätigen → Datei in
   `documents/_inbox/` mit `id` und `version: 1`.
2. **Eigene Notiz:** in Obsidian eine Notiz unter `documents/…` anlegen (ohne Frontmatter).
3. **PDF:** ein Datenblatt nach `documents/…` legen.
4. **Pflegelauf** im Projekt: „Verarbeite neue Dokumente.“ → Zusammenfassungen, Themenseiten mit
   Belegen, Index, Status, Log, Agenten-Commit.
5. **Einsortieren** in Obsidian (Dokument aus `_inbox/` verschieben) → Belege zeigen auf den
   neuen Ort.
6. **Fortsetzen** in einem neuen Chat: „Führ die Diskussion zu … weiter“ → Vorher/Nachher,
   Bestätigung, `version: 2`.
7. **Quellen:** „Woher stammt die Angabe …?“ → Original, Abschnitt, Zitat, Version, Status.
8. Abschluss: `pkm doctor` und `pkm lint` ohne Fehler.

Die vollständige Abnahme steht in [abnahme.md](abnahme.md) bzw. Abschnitt 14 der Spezifikation.

## 12. Fehlersuche

| Problem | Prüfen |
|---|---|
| Tools erscheinen nicht in Claude Desktop | Pfad zu `pkm-mcp` in der Config (Windows: `.exe`, doppelte Backslashes), App vollständig beenden und neu starten, Log von Claude Desktop |
| `git_unavailable` | `pkm doctor`: Git-Repo vorhanden (`pkm init`), Identität gesetzt, `PATH` in der Config |
| `commit_failed` | Signierung (`commit.gpgsign`), Schreibrechte; die Datei wurde zurückgesetzt |
| `conflict` | Datei wurde inzwischen geändert (z. B. in Obsidian oder per Sync) – neu lesen |
| Suche findet nichts Neues | `pkm reindex` (der Index ist nur ein Cache) |
| Konfliktkopien („conflicted copy“) | In Obsidian zusammenführen, Kopie löschen, dann `pkm versions` |

Logs von Claude Desktop: Mac `~/Library/Logs/Claude/`, Windows `%APPDATA%\Claude\logs\`.
Protokoll aller MCP-Vorgänge: `<VAULT>/.pkm/mcp.log`.

Versionsgeschichte direkt ansehen:

Mac:

```bash
git --git-dir="<HOME>/Library/Application Support/pkm/git" --work-tree="<HOME>/Nextcloud/<VAULT>" log --oneline
```

Windows:

```powershell
git --git-dir="$env:APPDATA\pkm\git" --work-tree="$env:USERPROFILE\Nextcloud\<VAULT>" log --oneline
```
