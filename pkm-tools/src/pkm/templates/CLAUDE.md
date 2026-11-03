# PKM – Schema und Regeln

Dieser Ordner ist ein persönliches Wissensmanagement (PKM) mit LLM-Wiki. Die Pflege
übernimmt der Skill `pkm-wiki` im Claude-Projekt „PKM-Pflege“. Änderungen an dieser Datei
nur nach Zustimmung des Nutzers.

## Bereiche und Besitz

| Bereich | Gehört | Wer schreibt |
|---|---|---|
| `documents/` (inkl. `_inbox/`, `_attachments/`) | Nutzer | Nutzer (Obsidian), pkm-mcp auf Anweisung des Nutzers; der Agent `id`/`version` über `pkm ids`/`pkm versions` sowie `title`, `context`, `tags`, `kind`, `short_citation` nach Bestätigung des Nutzers |
| `wiki/` | Pflege-Agent | nur der Agent; aus Chats nur lesbar |
| `scratch/` | Nutzer | Nutzer (Obsidian), pkm-mcp auf Anweisung; ohne Version und Commit, nie im Wiki, nicht in Git |
| `.pkm/state.json` | Pflege-Agent | `pkm mark` |
| `CLAUDE.md` | Nutzer | Agent nur nach Zustimmung; Änderungen erfasst `pkm versions` als Nutzer-Commit |

Neue Dokumente aus Chats und vom Web Clipper landen in `documents/_inbox/`. Einsortiert wird
frei in Obsidian; Dokumente werden über ihre ID gefunden, nicht über den Pfad.

## Dokumente

- Frontmatter-Pflichtfelder: `id` (`d-YYYYMMDD-HHMM-xxxx`) und `version` (ab 1).
- Weitere Felder (Schema der digitalisierten Normen, zuerst in dieser Reihenfolge): `title`,
  `short_citation`, `date_document`, `status_markdown`, `date_markdown`, `toolchain_markdown`;
  danach `id`, `version`, `date_updated`, `context`, `tags`, `related`,
  `kind` (`note` | `standard` | `regulation` | `correction`).
- `id`, `version`, `date_markdown`, `date_updated` setzen nur pkm-mcp bzw. die `pkm`-CLI.
  `status_markdown` wird unverändert übernommen und von keinem Werkzeug geändert.
- `context`: eine Zeile „<Art>: <Inhalt>“ (Art: Chat, Podcast, Buch, Artikel, Recherche, Notiz).
  `tags`: 4–8, klein, Bindestriche, Umlaute ausgeschrieben, vorhandene wiederverwenden.
  Fehlen sie bei neuen Dokumenten, schlägt der Pflege-Agent Werte vor und trägt sie erst nach
  Bestätigung ein.
- Datumsfelder `date_markdown`/`date_updated`: `YYYY-MM-DDTHH:MM:SS` in Ortszeit ohne Zeitzone.
- Feldnamen ohne Leerzeichen. Werte mit `: ` oder führendem YAML-Sonderzeichen in doppelte
  Anführungszeichen setzen. `source` bleibt dem Web Clipper vorbehalten.
- Jede Version ist genau ein Git-Commit mit den Zeilen `PKM-Id`, `PKM-Version`,
  `PKM-Source` (`chat` | `user` | `agent`). Der Verlauf liegt in Git, nicht im Dokument.
- Bilder (4.9): PNG, JPEG und SVG (Diagramme als SVG). Übergabe aus dem Chat über `pkm_img_import/`
  (nicht in Git, nie im Wiki). Bis 24 KB eingebettet als Data-URI mit Titel
  `"pkm:<name>"`, größere als Datei in `documents/_attachments/`. Jedes neue Bild hat einen
  Alternativtext. Bestehende eingebettete PNG bleiben unverändert. Belege auf Bilder zitieren
  `[img:<name>]`.
- Empfohlene Gliederung für Chat-Ergebnisse: `## Ergebnis`, `## Entscheidungen`,
  `## Offene Punkte`, `## Kontext / Begründung`. Fortsetzungen aktualisieren diese Abschnitte.
- Abschnitte sind Überschriften der Ebene 1 und 2 (`#`, `##`). Doppelte Überschriften, die
  Zeichen `# ^ [ ] |` und Überschriften, die auf `#` plus Ziffern enden („Version#2“ →
  besser „Version 2“), vermeiden.

## Wiki

- Seitentypen: `wiki/topics/` (topic), `wiki/entities/` (entity), `wiki/summaries/` (summary,
  eine Seite je Dokument), `wiki/syntheses/` (synthesis).
- Frontmatter: `type`, `title`, `aliases`, `tags`, `sources` (erzeugt), `date_updated`,
  `confidence` (`high` | `medium` | `low`).
- Erste Zeile nach dem Frontmatter: `> **Kurzfassung:** …`
- Jede Sachaussage in „Inhalt“ und „Widersprüche / offene Fragen“ endet mit einer Fußnote auf
  ein Dokument in `documents/`:
  `[^b1]: [[<pfad>#<anker>]] · „<zitat>“ · id:<id> · v:<version> · sha:<6 zeichen>`
  (PDF/Bild: `[[<pfad>.pdf#page=<n>]] · „<zitat>“ · sha:<6 zeichen>`).
- Wiki-Seiten gelten nicht als Beleg. Nichts erfinden, Lücken als offene Frage markieren.
- Im Wiki wird nichts gelöscht; überholte Aussagen behalten ihren Beleg auf die alte Version.
- Generiert, nicht von Hand ändern: `wiki/index.md`, `wiki/_status.md`, `sources`.
- `wiki/log.md` wird nur angehängt.

## Sprache

Inhalte, Überschriften, Änderungsnotizen und Berichte: Deutsch. Schnittstellen (Felder,
Werte, Tools, CLI): Englisch.
