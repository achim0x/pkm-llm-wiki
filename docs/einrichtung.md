# PKM mit LLM-Wiki – Einrichtung

Diese Anleitung richtet das PKM auf dem **Mac** ein (Spezifikation 5.5, 7.6, 11, 13).
Der Windows-Rechner braucht nur Obsidian und Nextcloud.

Platzhalter: `<HOME>` = Home-Verzeichnis auf dem Mac (z. B. `/Users/name`), `<VAULT>` = Name
des Vault-Ordners in der Nextcloud, `<REPO>` = Ort dieses Repositorys auf dem Mac.

---

## 1. Voraussetzungen (Mac)

- Nextcloud-Desktop-Client, Obsidian, Claude Desktop
- Git (Xcode Command Line Tools):

  ```bash
  xcode-select --install
  ```

- `uv` (Python-Werkzeug), installiert nach `~/.local/bin`:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

## 2. Paket installieren

Repository auf den Mac holen (außerhalb der Nextcloud), dann die Befehle `pkm` und `pkm-mcp`
installieren:

```bash
git clone https://github.com/achim0x/pkm-llm-wiki.git <REPO>
```

```bash
uv tool install <REPO>/pkm-tools
```

Danach liegen `pkm` und `pkm-mcp` in `<HOME>/.local/bin/`. Aktualisieren nach einem `git pull`:

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

```bash
git --git-dir="<HOME>/Library/Application Support/pkm/git" config commit.gpgsign false
```

## 4. Vault anlegen

Der Vault liegt in der Nextcloud, Git-Verzeichnis und Suchindex liegen außerhalb unter
`~/Library/Application Support/pkm/` (Standard, nichts einzustellen).

```bash
export PKM_ROOT="<HOME>/Nextcloud/<VAULT>"
```

```bash
pkm init
```

```bash
pkm doctor
```

`pkm init` ist idempotent und legt an: `documents/_inbox/`, `documents/_attachments/`,
`wiki/` (mit `index.md`, `log.md`, `_status.md` und den Unterordnern), `CLAUDE.md`,
`.pkm/state.json`, `.gitignore` sowie das Git-Verzeichnis mit einem ersten Commit.
Liegen im Ordner schon Notizen, bleiben sie unverändert; sie bekommen beim ersten Pflegelauf
eine ID (`pkm ids`).

Die CLI findet den Vault auch ohne `PKM_ROOT`, wenn sie in einem Ordner des Vaults aufgerufen
wird (sie sucht aufwärts nach `.pkm/state.json`).

**Wichtig:** `PKM_GIT_DIR` und `PKM_CACHE_DIR` dürfen nie in der Nextcloud liegen.
`pkm doctor` prüft das.

## 5. MCP-Server in Claude Desktop

Datei `<HOME>/Library/Application Support/Claude/claude_desktop_config.json` (anlegen, falls
nicht vorhanden; bestehende Einträge unter `mcpServers` behalten):

```json
{
  "mcpServers": {
    "pkm": {
      "command": "<HOME>/.local/bin/pkm-mcp",
      "env": {
        "PKM_ROOT": "<HOME>/Nextcloud/<VAULT>",
        "PKM_VAULT_NAME": "<VAULT>",
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

- JSON kennt weder `~` noch Umgebungsvariablen: alle Pfade absolut.
- `PATH` muss `git` enthalten, weil Claude Desktop Server mit minimaler Umgebung startet.
- `PKM_VAULT_NAME` ist optional und sorgt für klickbare `obsidian://`-Links in Quellenangaben.
- Alternative ohne Installation (wie Spezifikation 7.6):
  `"command": "<HOME>/.local/bin/uvx", "args": ["--from", "<REPO>/pkm-tools", "pkm-mcp"]`.

Claude Desktop neu starten. Im Chat sollten unter den Werkzeugen die zwölf `pkm`-Tools
erscheinen (`search`, `read`, `history`, `show_citations`, `read_index`, `list_unprocessed`,
`create_document`, `rewrite_document`, `append_to_document`, `edit_document`,
`update_frontmatter`, `restore_document`).

## 6. Skills installieren

Die Skills liegen in `<REPO>/pkm-tools/skills/`. Jeden Ordner als ZIP packen:

```bash
cd <REPO>/pkm-tools/skills && zip -r pkm-access.zip pkm-access && zip -r pkm-wiki.zip pkm-wiki
```

In Claude Desktop unter den Einstellungen bei den Skills (je nach App-Version „Einstellungen →
Funktionen → Skills“) beide ZIP-Dateien hochladen und aktivieren:

- `pkm-access` – für alle normalen Chats (Ablegen, Fortsetzen, Abfragen, Quellen).
- `pkm-wiki` – für das Pflegeprojekt.

Bestehende andere Skills bleiben unberührt (keine Startbefüllung).

## 7. Projekt „PKM-Pflege“

1. In Claude Desktop ein Projekt „PKM-Pflege“ anlegen.
2. Projektanweisung:

   > Dies ist das Pflegeprojekt für das PKM unter `<HOME>/Nextcloud/<VAULT>`. Nutze den Skill
   > `pkm-wiki`. Arbeite im Vault-Ordner und rufe die CLI über `<HOME>/.local/bin/pkm` auf.

3. In einem Chat des Projekts den Vault-Ordner verbinden („+“ → „Add folder“ bzw. „Ordner
   hinzufügen“).
4. Pflegeläufe werden manuell angestoßen: „Verarbeite neue Dokumente“, „Lint“.
   Eine geplante Aufgabe (täglich „Ingest, danach Lint“) wird erst später und nur auf
   ausdrückliche Anweisung eingerichtet.

## 8. Obsidian

Den Ordner `<HOME>/Nextcloud/<VAULT>` als Vault öffnen und einstellen:

| Einstellung | Wert |
|---|---|
| Dateien & Links → Interne Links automatisch aktualisieren | an |
| Dateien & Links → Neues Link-Format | Absoluter Pfad im Vault |
| Dateien & Links → Wikilinks verwenden | an |
| Dateien & Links → Standardordner für Anhänge | `documents/_attachments` |
| Dateien & Links → Ausgeschlossene Dateien | `.pkm/` |
| Web Clipper → Zielordner | `documents/_inbox` |

Optional: Dataview, Graph View. Die Einstellungen in `.obsidian/` werden über Nextcloud auch
auf den Windows-Rechner übertragen. Kein Obsidian-Git-Plugin verwenden.

`pkm doctor` prüft die Einstellungen aus `.obsidian/app.json`.

## 9. Nextcloud

Keine Ausnahmen nötig, weil Git und Suchindex außerhalb liegen. Optional
`.obsidian/workspace*.json` in Nextcloud ignorieren (geräteabhängige Dateien).

## 10. Probelauf

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

Die vollständige Abnahme steht in Abschnitt 14 der Spezifikation.

## 11. Fehlersuche

| Problem | Prüfen |
|---|---|
| Tools erscheinen nicht in Claude Desktop | Pfad zu `pkm-mcp` in der Config, App neu starten, Log von Claude Desktop |
| `git_unavailable` | `pkm doctor`: Git-Repo vorhanden (`pkm init`), Identität gesetzt, `PATH` in der Config |
| `commit_failed` | Signierung (`commit.gpgsign`), Schreibrechte; die Datei wurde zurückgesetzt |
| `conflict` | Datei wurde inzwischen geändert (z. B. in Obsidian oder per Sync) – neu lesen |
| Suche findet nichts Neues | `pkm reindex` (der Index ist nur ein Cache) |
| Konfliktkopien („conflicted copy“) | In Obsidian zusammenführen, Kopie löschen, dann `pkm versions` |

Protokoll aller MCP-Vorgänge: `<VAULT>/.pkm/mcp.log`.
Versionsgeschichte direkt ansehen:

```bash
git --git-dir="<HOME>/Library/Application Support/pkm/git" --work-tree="<HOME>/Nextcloud/<VAULT>" log --oneline
```

Die Versionsgeschichte existiert nur auf dem Mac und wird über Time Machine gesichert
(`~/Library/Application Support/pkm/` ist darin enthalten).
