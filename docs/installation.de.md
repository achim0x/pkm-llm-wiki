# PKM mit LLM-Wiki – Einrichtung

**Deutsch** · [English](installation.md)

Diese Anleitung richtet das PKM auf dem **PKM-Rechner** ein (Spezifikation 5.5, 7.6, 11, 13, 15.1).
Wie Installer und `pkm setup` intern ablaufen, beschreibt [architecture.md](architecture.md) (englisch,
mit Ablaufdiagrammen).
Der PKM-Rechner ist der eine Rechner, auf dem Claude Desktop, die MCP-Server `pkm-mcp` und
`pkm-pflege-mcp`, die CLI `pkm` und (mit Git) der Versionsverlauf liegen. Das kann ein **Mac** oder
ein **Windows-PC** sein; beide Varianten sind gleichwertig. Weitere Rechner (optional) brauchen nur
den Client des Cloud-Speichers und einen Markdown-Editor, z. B. Obsidian.

**Pro Vault genau ein PKM-Rechner.** Der Versionsverlauf liegt lokal auf diesem Rechner und wird
nicht synchronisiert. Ein zweiter PKM-Rechner für denselben Vault würde einen zweiten, abweichenden
Verlauf anlegen.

Kurzfassung:

1. Installer ausführen (installiert uv und das Paket, startet `pkm setup`).
2. Die Fragen von `pkm setup` beantworten (Vault-Ordner, Dokumentsprache, ggf. Git-Name und
   E-Mail).
3. Die beiden Skill-ZIPs in Claude Desktop hochladen.
4. Projekt „PKM-Pflege“ anlegen.
5. Claude Desktop neu starten (und Obsidian, falls du es nutzt).

Platzhalter:

| Platzhalter | Mac | Windows |
|---|---|---|
| `<HOME>` | Home-Verzeichnis, z. B. `/Users/name` | Benutzerordner, z. B. `C:\Users\name` |
| `<VAULT>` | Vault-Ordner, mit Cloud-Speicher im Ordner des Dienstes, sonst ein beliebiger lokaler Ordner | ebenso |
| `<APPDIR>` | `<HOME>/Library/Application Support/pkm` | `%APPDATA%\pkm`, z. B. `C:\Users\name\AppData\Roaming\pkm` |

`<APPDIR>` enthält die Konfigurationsdatei `config.toml`, das Git-Verzeichnis (`<APPDIR>/git`),
den Suchindex (`<APPDIR>/index.db`) und die Skill-ZIPs (`<APPDIR>/skills`). Er liegt bewusst
außerhalb des Vaults und eines Cloud-Ordners.

---

## 1. Voraussetzungen

- **Claude Desktop** (Pflicht).
- **Obsidian ist optional**, aber empfohlen. Der Vault besteht aus normalen Markdown-Dateien; du
  kannst sie mit jedem Editor lesen und bearbeiten. Obsidian bringt Wikilinks, Backlinks, die Anzeige
  der Eigenschaften und eingebetteter Bilder, die Graph-Ansicht und das automatische Umschreiben von
  Links beim Verschieben. Ohne Obsidian beim Verschieben von Dokumenten bedenken: Belege und Wikilinks in
  Wiki-Seiten korrigiert der Pflegelauf (`fix-citations`), Links in deinen eigenen Dokumenten nicht.
  Die Dateien unter `.obsidian/` legt `pkm init` trotzdem an; sie stören ohne Obsidian nicht.
- **Cloud-Speicher ist optional.** Das PKM funktioniert auch rein lokal: Der Vault ist dann ein
  normaler Ordner auf dem PKM-Rechner, und du arbeitest nur auf diesem Rechner. Ein Cloud-Speicher
  (Nextcloud, OneDrive, Google Drive, Dropbox, iCloud Drive, Syncthing …) wird erst gebraucht, wenn
  du den Vault auch auf weiteren Rechnern oder dem Smartphone nutzen willst; dann liegt der Vault im
  Ordner des Dienstes (Abschnitt 7). Ein lokaler Vault lässt sich später in den Cloud-Ordner
  verschieben; danach `pkm setup` erneut ausführen und den neuen Ort angeben.
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

Es gibt drei Wege:

| Weg | Für wen | Wo beschrieben |
|---|---|---|
| **Installer** (empfohlen) | Normalfall: ein Befehl, danach führt `pkm setup` durch die Einrichtung | dieser Abschnitt und Abschnitt 3 |
| **Manuelle Installation** | Wer jeden Schritt selbst ausführen und sehen will, keine Skripte aus dem Internet ausführen möchte oder eine abweichende Einrichtung braucht (z. B. andere Ordner) | [Anhang A](#anhang-a-manuelle-installation) |
| **Entwicklungsinstallation** | Wer den Code oder die Skills ändern will: die Programme laufen direkt aus einer lokalen Kopie (Clone) des Repositorys | [Anhang B](#anhang-b-entwicklungsinstallation) |

Alle Wege führen zum selben Ergebnis; man kann sie auch mischen (z. B. das Paket von Hand
installieren und danach `pkm setup` ausführen).

### 2.1 Mit dem Installer

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
Installer erneut ausführen; `pkm setup` bietet an, die vorhandene Konfiguration zu übernehmen
(Abschnitt 3), auch aus einer Installation aus der Zeit vor `pkm setup`. Meldet ein neues Terminal, dass `pkm` nicht gefunden wird, einmal
`uv tool update-shell` ausführen.

Installation ohne Installer: [Anhang A](#anhang-a-manuelle-installation).

## 3. `pkm setup`

`pkm setup` führt durch die Einrichtung und lässt sich jederzeit erneut ausführen; jeder Schritt ist
idempotent.

1. **Vorhandene Konfiguration prüfen:** `pkm setup` sucht Einstellungen in den
   Umgebungsvariablen, in den PKM-Einträgen von Claude Desktop (Installationen aus der Zeit vor
   `pkm setup` hatten sie dort in einem `env`-Block; erkannt an den Namen `pkm`/`pkm-pflege` oder an
   den Programmen `pkm-mcp`/`pkm-pflege-mcp`) und in `config.toml`. Nennt keine davon den Vault,
   liest es ihn aus dem vorhandenen Git-Verzeichnis (dort ist der Vault-Ordner vermerkt). Findet es
   Einstellungen (z. B. `PKM_ROOT`, `PKM_GIT_DIR`, `PKM_CACHE_DIR`), zeigt es sie mit ihrer Herkunft und
   fragt, ob es sie **übernehmen** soll. Ja: Die Werte sind die Vorgaben der folgenden Fragen und
   kommen in `config.toml`, damit ein vorhandenes Git-Verzeichnis samt Verlauf weiter genutzt wird.
   Nein: Die Einrichtung beginnt mit einer neuen Konfiguration; eine vorhandene `config.toml` wird
   vorher gesichert (`config.toml.<Zeit>.bak`).
2. **Vault-Ordner** abfragen (absoluter Pfad; mit Cloud-Speicher im Ordner des Dienstes; wird
   angelegt, wenn er fehlt). Erkannt wird auch der Cloud-Dienst; Dateien, die nur online vorliegen, meldet der
   Assistent (Abschnitt 7).
3. **Git prüfen.** Ist Git vorhanden, wird die Versionsverwaltung eingeschaltet. Fehlt die
   Git-Identität, fragt `pkm setup` nach Name und E-Mail und trägt sie nur für das PKM-Repo ein;
   die Commit-Signierung wird für das PKM-Repo abgeschaltet. **Fehlt Git**, erscheint ein Hinweis
   und das PKM läuft ohne Versionsverwaltung.
4. **Dokumentsprache** abfragen: Sollen im Chat erzeugte Dokumente hauptsächlich englisch oder
   deutsch sein (`en` oder `de`, Vorgabe Englisch bzw. die bisherige Antwort; Option `--language`)?
   Der Server `pkm` nennt Claude diese Sprache und die passenden Abschnittsnamen (Result, Decisions,
   Open points, Context / rationale bzw. Ergebnis, Entscheidungen, Offene Punkte, Kontext /
   Begründung). Fortgeführte Dokumente behalten ihre Sprache. Später ändern: `pkm setup` erneut
   ausführen und Claude Desktop neu starten.
5. **Konfigurationsdatei** `<APPDIR>/config.toml` schreiben (Vault-Pfad, Vault-Name,
   Versionsverwaltung an oder aus, Pfad zu Git, Dokumentsprache). Server und CLI lesen sie; gesetzte
   Umgebungsvariablen haben Vorrang.
6. **`pkm init`** ausführen: Ordnerstruktur, `CLAUDE.md`, `.gitignore`, `.pkm/state.json`,
   Obsidian-Einstellungen (`.obsidian/app.json`) und Property-Typen (`.obsidian/types.json`), mit
   Git zusätzlich das Repo außerhalb des Vaults mit einem ersten Commit. Bestehende Notizen bleiben
   unverändert.
7. **Claude Desktop prüfen:** `pkm setup` prüft, ob die Server `pkm` und `pkm-pflege` in
   `claude_desktop_config.json` schon passend eingetragen sind (nur mit `command`, ohne weitere
   Angaben). Fehlt ein Eintrag oder weicht er ab, zeigt der Assistent die Änderung und **fragt, ob er
   die Datei ändern darf**. Bei „ja“ legt er eine Sicherungskopie an und trägt die Server ein; andere
   Server bleiben unverändert. Bei „nein“ ändert er nichts und zeigt den JSON-Text, den du selbst
   unter `mcpServers` einträgst (in Claude Desktop: Einstellungen → Entwickler → „Konfiguration
   bearbeiten“). Ist die Datei kein gültiges JSON, bleibt sie unangetastet und der Text wird ebenfalls
   angezeigt.
8. **Skill-ZIPs** nach `<APPDIR>/skills/` schreiben (Abschnitt 4).
9. Die **Projektanweisung** für „PKM-Pflege“ ausgeben (Abschnitt 5).
10. **`pkm doctor`** ausführen und Fehler nennen.

Optionen (alle optional): `--vault <ordner>`, `--vault-name <name>`, `--git-name <name>`,
`--git-email <adresse>`, `--language en|de`, `--yes` (Standardwerte ohne Rückfrage), `--claude-config <datei>`,
`--skills-dir <ordner>`, `--json`.

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

## 6. Obsidian (optional)

Ohne Obsidian entfällt dieser Abschnitt. Mit Obsidian den Vault-Ordner als Vault öffnen.
`pkm init` (über `pkm setup`) trägt die Einstellungen aus Spezifikation 13 in `.obsidian/app.json` ein; Obsidian übernimmt sie nach einem Neustart:

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
ausgenommen; liegt der Vault im Cloud-Speicher, kannst du Bilder auch vom Smartphone hineinlegen.
Eingebettete Bilder (Data-URIs) zeigt Obsidian im Lese- und Live-Vorschau-Modus. Nach der
Einrichtung einmal ein Dokument mit einem eingebetteten PNG und SVG aus einem Chat anlegen lassen
und in Obsidian prüfen.

Optional: Dataview, Graph View. Die Einstellungen in `.obsidian/` werden über den Cloud-Speicher auch
auf die anderen Rechner übertragen. Kein Obsidian-Git-Plugin verwenden.

## 7. Cloud-Speicher (optional)

Ohne Cloud-Speicher entfällt dieser Abschnitt; `pkm setup` meldet dann „no recognized cloud folder“,
das ist kein Fehler. Geeignet ist jeder Dienst, der einen normalen lokalen Ordner synchronisiert
(Nextcloud/ownCloud, OneDrive, Google Drive, Dropbox, iCloud Drive, Syncthing …). Wichtig ist vor allem, den
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

Die vollständige Abnahme steht in [acceptance.md](acceptance.md) bzw. Abschnitt 14 der Spezifikation.

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

## Anhang A: Manuelle Installation

Diese Anleitung ersetzt Installer und `pkm setup` vollständig. Jeder Schritt lässt sich einzeln
prüfen. Wer nur das Paket von Hand installieren will, macht die Schritte A.1–A.3 und führt danach
`pkm setup` aus (Abschnitt 3).

### A.1 uv installieren

`uv` installiert das Paket in eine eigene Umgebung und bringt eine passende Python-Version mit.

Mac:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Danach ein neues Terminal öffnen. Prüfen:

```bash
uv --version
```

### A.2 Git (optional)

Mit Git gibt es die Versionsverwaltung, ohne Git läuft das PKM ohne sie (Abschnitt 1). Prüfen, ob
Git vorhanden ist und läuft (auf dem Mac ohne Developer Tools erscheint stattdessen ein
Installationsdialog):

```bash
git --version
```

Den Pfad von Git braucht Schritt A.4. Mac:

```bash
command -v git
```

Windows:

```powershell
(Get-Command git).Source
```

### A.3 Paket installieren

Variante 1 – mit Git direkt aus GitHub (Aktualisieren später mit `uv tool upgrade pkm-tools`):

```bash
uv tool install "git+https://github.com/achim0x/pkm-llm-wiki#subdirectory=pkm-tools"
```

Variante 2 – ohne Git: auf GitHub das Repository als ZIP herunterladen („Code“ → „Download ZIP“),
entpacken und den Ordner `pkm-tools` installieren (Aktualisieren: neues ZIP, gleicher Befehl):

```bash
uv tool install --force --reinstall <ENTPACKT>/pkm-tools
```

Danach liegen `pkm`, `pkm-mcp` und `pkm-pflege-mcp` in `<HOME>/.local/bin` (Windows mit `.exe`).
Meldet ein neues Terminal, dass `pkm` nicht gefunden wird:

```bash
uv tool update-shell
```

Prüfen:

```bash
pkm --help
```

### A.4 Konfigurationsdatei anlegen

`<APPDIR>/config.toml` anlegen (Ordner `<APPDIR>` bei Bedarf erstellen). Die Schlüssel heißen wie
die Umgebungsvariablen aus Spezifikation 7.1.

Mac, z. B. `~/Library/Application Support/pkm/config.toml`:

```toml
PKM_ROOT = "/Users/name/Nextcloud/Vault"
PKM_VAULT_NAME = "Vault"
PKM_VERSIONING = true
PKM_GIT = "/usr/bin/git"
PKM_LANGUAGE = "en"
```

Windows, z. B. `%APPDATA%\pkm\config.toml` (Pfade in einfachen Anführungszeichen, dann bleiben die
Backslashes, wie sie sind):

```toml
PKM_ROOT = 'C:\Users\name\Nextcloud\Vault'
PKM_VAULT_NAME = "Vault"
PKM_VERSIONING = true
PKM_GIT = 'C:\Program Files\Git\cmd\git.exe'
PKM_LANGUAGE = "en"
```

- `PKM_ROOT`: absoluter Pfad des Vault-Ordners (mit Cloud-Speicher im Ordner des Dienstes, sonst ein
  lokaler Ordner).
- `PKM_VERSIONING = false`, wenn Git fehlt oder nicht genutzt werden soll; `PKM_GIT` entfällt dann.
- `PKM_LANGUAGE`: Hauptsprache von im Chat erzeugten Dokumenten, `"en"` (Englisch, Standard) oder
  `"de"` (Deutsch).
- Weitere optionale Schlüssel: `PKM_GIT_DIR`, `PKM_CACHE_DIR` (beide nie in einen Cloud-Ordner),
  `PKM_TZ`, `PKM_MAX_KB`, `PKM_GIT_AUTHOR`, `PKM_IMPORT_DIR`, `PKM_INLINE_MAX_KB` (24),
  `PKM_SVG_MAX_KB` (200), `PKM_IMAGE_MAX_MB` (5), `PKM_IMAGE_PARAM_MAX_KB` (512), `PKM_SVG_RASTER`
  (`false`; zum Rastern von SVG zusätzlich das Paket `cairosvg` installieren).
- Eine Datei an einem anderen Ort wählt die Umgebungsvariable `PKM_CONFIG`; sie muss dann auch im
  Eintrag für Claude Desktop stehen (A.7).

### A.5 Vault anlegen

```bash
pkm init
```

`pkm init` legt Ordnerstruktur, `CLAUDE.md`, `.gitignore`, `.pkm/state.json`,
`.obsidian/app.json` und `.obsidian/types.json` an und, mit `PKM_VERSIONING = true`, das
Git-Verzeichnis unter `<APPDIR>/git`. Bestehende Notizen bleiben unverändert.

### A.6 Git-Identität und Signierung (nur mit Git)

Ohne Name und E-Mail verweigert der Server alle schreibenden Tools. Ist global keine Identität
gesetzt, für das PKM-Repo setzen (Mac):

```bash
git --git-dir="$HOME/Library/Application Support/pkm/git" config user.name "Vorname Nachname"
```

```bash
git --git-dir="$HOME/Library/Application Support/pkm/git" config user.email "name@example.org"
```

Windows:

```powershell
git --git-dir="$env:APPDATA\pkm\git" config user.name "Vorname Nachname"
```

```powershell
git --git-dir="$env:APPDATA\pkm\git" config user.email "name@example.org"
```

Commit-Signierung für das PKM-Repo abschalten (sonst scheitern Commits aus Claude Desktop, wenn
der Signaturschlüssel dort nicht erreichbar ist). Mac:

```bash
git --git-dir="$HOME/Library/Application Support/pkm/git" config commit.gpgsign false
```

Windows:

```powershell
git --git-dir="$env:APPDATA\pkm\git" config commit.gpgsign false
```

Fehlte die Identität bei `pkm init`, gibt es noch keinen ersten Commit; dann `pkm init` noch
einmal ausführen.

### A.7 Claude Desktop

`claude_desktop_config.json` öffnen (in Claude Desktop: Einstellungen → Entwickler →
„Konfiguration bearbeiten“; Mac `<HOME>/Library/Application Support/Claude/`, Windows
`%APPDATA%\Claude\`) und unter `mcpServers` die beiden Einträge ergänzen. Andere Server bleiben
stehen. Alle Pfade absolut.

Mac:

```json
{
  "mcpServers": {
    "pkm": { "command": "/Users/name/.local/bin/pkm-mcp" },
    "pkm-pflege": { "command": "/Users/name/.local/bin/pkm-pflege-mcp" }
  }
}
```

Windows (in JSON jeden Backslash verdoppeln):

```json
{
  "mcpServers": {
    "pkm": { "command": "C:\\Users\\name\\.local\\bin\\pkm-mcp.exe" },
    "pkm-pflege": { "command": "C:\\Users\\name\\.local\\bin\\pkm-pflege-mcp.exe" }
  }
}
```

Liegt `config.toml` nicht im Standardordner, in beiden Einträgen
`"env": { "PKM_CONFIG": "<pfad zur config.toml>" }` ergänzen. Umgebungsvariablen in `env` haben
Vorrang vor `config.toml`. Danach Claude Desktop vollständig beenden und neu starten.

### A.8 Skills packen und hochladen

Die Skills liegen im Paket unter `pkm/skills/` (im Repository `pkm-tools/src/pkm/skills/`). Fertige
ZIP-Dateien hängen an jeder GitHub-Release; selbst packen geht so (im entpackten bzw. geklonten
Repository).

Mac:

```bash
cd <REPO>/pkm-tools/src/pkm/skills && zip -r pkm-access.zip pkm-access && zip -r pkm-wiki.zip pkm-wiki
```

Windows:

```powershell
cd <REPO>\pkm-tools\src\pkm\skills; Compress-Archive -Force pkm-access pkm-access.zip; Compress-Archive -Force pkm-wiki pkm-wiki.zip
```

Beide ZIP-Dateien in Claude Desktop hochladen (Abschnitt 4).

### A.9 Abschluss

```bash
pkm doctor
```

Erwartet: `"status": "ok"`. Danach weiter mit Abschnitt 5 (Projekt „PKM-Pflege“) und, falls
genutzt, Abschnitt 6 (Obsidian neu starten, damit es die Einstellungen aus `app.json` liest).

**Aktualisieren:** Paket neu installieren (A.3), Skills neu packen und hochladen (A.8). Die
übrigen Schritte bleiben gültig.

## Anhang B: Entwicklungsinstallation

Für die Arbeit am PKM selbst: Das Paket wird **editierbar** aus einer lokalen Kopie (Clone) des
Repositorys installiert. Die Programme `pkm`, `pkm-mcp` und `pkm-pflege-mcp` laden Code und Skills
dann direkt aus `<REPO>/pkm-tools/src/pkm`; eine Änderung in der Kopie braucht keine neue
Installation. Voraussetzungen wie in Abschnitt 1, dazu Git zum Klonen; uv wie in A.1.

### B.1 Installieren

```bash
git clone https://github.com/achim0x/pkm-llm-wiki.git <REPO>
```

```bash
uv tool install --editable <REPO>/pkm-tools
```

Unter Windows dieselben Befehle mit `<REPO>\pkm-tools`. Danach wie gewohnt einrichten:

```bash
pkm setup
```

`pkm setup` (Abschnitt 3) fragt den Vault ab, prüft Git, fragt die Dokumentsprache ab, schreibt
`config.toml`, trägt die Server in Claude Desktop ein und baut die Skill-ZIPs – aus den Skills in
der Kopie. Weiter mit den Abschnitten 4–6.

### B.2 Damit arbeiten

| Änderung | Was zu tun ist |
|---|---|
| Python-Code | Wirkt beim nächsten Start eines Programms. Für die MCP-Server: Claude Desktop ganz beenden und neu starten |
| Skills (`pkm-tools/src/pkm/skills/`) | `pkm setup` erneut ausführen (packt die ZIPs neu), in Claude Desktop erneut hochladen (Abschnitt 4) |
| Anderer Branch (`git checkout …`) | Die installierten Programme nutzen den Code des ausgecheckten Branches; Claude Desktop neu starten |
| Abhängigkeiten in `pyproject.toml` | Neu installieren: `uv tool install --editable --force <REPO>/pkm-tools` |

Tests und Prüfungen laufen in einer eigenen Umgebung `<REPO>/pkm-tools/.venv` (siehe
[README von pkm-tools](../pkm-tools/README.md)); sie berührt die installierten Programme nicht.

**Beim Entwickeln einen Testvault nutzen**, damit der echte Vault und sein Verlauf unberührt
bleiben. Er braucht eine eigene Konfigurationsdatei mit **eigenem Git-Verzeichnis und Suchindex**;
sonst nutzt der Testvault das Git-Verzeichnis des echten (beide liegen standardmäßig im
App-Ordner). Zuerst `<HOME>/pkm-dev/config.toml` anlegen (absolute Pfade, außerhalb jedes
Cloud-Ordners; Schrägstriche funktionieren auch unter Windows):

```toml
PKM_GIT_DIR = "<HOME>/pkm-dev/git"
PKM_CACHE_DIR = "<HOME>/pkm-dev/cache"
```

Dann `pkm setup` mit dieser Datei ausführen (es behält die beiden Schlüssel und ergänzt den Rest):

```bash
PKM_CONFIG=<HOME>/pkm-dev/config.toml pkm setup --vault <HOME>/pkm-dev/vault
```

Windows (PowerShell):

```powershell
$env:PKM_CONFIG = "<HOME>\pkm-dev\config.toml"; pkm setup --vault <HOME>\pkm-dev\vault
```

`pkm setup` trägt `PKM_CONFIG` in die Einträge von Claude Desktop ein; Claude Desktop arbeitet dann
mit dem Testvault. Zurück zum echten Vault: `pkm setup` ohne `PKM_CONFIG` erneut ausführen (in
PowerShell vorher `Remove-Item Env:PKM_CONFIG`).

### B.3 Zurück zur normalen Installation

Den Installer erneut ausführen (Abschnitt 2.1) oder das Paket ohne `--editable` installieren (A.3).
Beides ersetzt die editierbare Installation; Konfiguration und Vault bleiben, wie sie sind.

**Einen festen Stand der Kopie installieren** (ohne editierbar): Der Installer nimmt auch ein
lokales ZIP des Repositorys, z. B. `git -C <REPO> archive --format=zip --prefix=pkm-llm-wiki/ -o
<HOME>/pkm.zip HEAD` und danach `PKM_ARCHIVE=file://<HOME>/pkm.zip sh <REPO>/install.sh` (Windows:
`$env:PKM_ARCHIVE = "<HOME>\pkm.zip"` vor `install.ps1`).
