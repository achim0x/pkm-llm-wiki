---
name: pkm-wiki
description: Pflege des PKM-Wikis über den MCP-Server „pkm-pflege“ (Projekt „PKM-Pflege“) – neue und geänderte Dokumente verarbeiten (Ingest), Lint, Wiki-Fragen im Pflegeprojekt, Schema anpassen. Verwenden bei „verarbeite neue Dokumente“, „Ingest“, „Lint“, „prüf das Wiki“, „was steht im Wiki zu …“ im Pflegeprojekt.
---

# PKM-Wiki pflegen

Du arbeitest über die Tools des MCP-Servers **`pkm-pflege`**. Er läuft auf dem PKM-Rechner des
Nutzers; eine Shell oder die CLI `pkm` brauchst du nicht (in Cowork gibt es dort keine).

| Tool | Zweck |
|---|---|
| `begin_maintenance` | Vorlauf: Umgebung prüfen, Handänderungen als Versionen, fehlende IDs, `pending` (neue Dokumente mit `missing_fields`), `known_tags`, Belege auf verschobene Dokumente korrigieren |
| `read`, `history`, `search`, `read_index`, `show_citations`, `list_unprocessed` | Dokumente, Versionen, Diffs und Wiki-Seiten lesen |
| `read_image` | Bilder ansehen (PNG als Bild, SVG als Text) |
| `write_wiki_page` | Wiki-Seite anlegen oder vollständig ersetzen (ohne Commit) |
| `set_document_metadata` | Nur nach Bestätigung: `title`, `context`, `tags`, `kind`, `short_citation` eines Dokuments eintragen |
| `finish_maintenance` | Abschluss: Belege (verschoben, umbenannt, `v:` bei unveränderten Abschnitten angehoben), `sources`, Verarbeitungsstand, Log, Index, Status, Lint, Agenten-Commit |

Sprache aller Inhalte: **Deutsch**.

## Feste Regeln

- `wiki/` gehört dir. `documents/` gehört dem Nutzer: dort **nichts** ändern, verschieben oder
  löschen. `id`/`version` setzt `begin_maintenance`. Einzige weitere Ausnahme: `title`,
  `context`, `tags`, `kind`, `short_citation` – nur nach **ausdrücklicher Bestätigung** des
  Nutzers im Chat und nur mit `set_document_metadata` (siehe „Frontmatter-Vorschläge“). Die
  Dokument-Tools des Servers `pkm` (`create_document`, `edit_document`, `update_frontmatter` …)
  benutzt du in der Pflege nicht.
- `scratch/` (kurzlebige Notizen, Todo-Listen) wird **weder gelesen noch verarbeitet**. Kein
  Beleg zeigt auf eine Datei dort. Wird eine Notiz nach `documents/` verschoben, ist sie beim
  nächsten Lauf ein neues Dokument; aus `documents/` nach `scratch/` verschoben wirkt wie Löschen.
- Im Wiki **nichts löschen**. Aussagen und Belege ergänzen, aktualisieren oder als überholt
  kennzeichnen.
- **Keine Aussage ohne Beleg** auf ein Dokument in `documents/`. Wiki-Seiten sind keine Belege.
  Zitate **wörtlich** aus der genannten Version kopieren. Nichts erfinden; Lücken als offene
  Frage markieren.
- Eigene Schlussfolgerungen kennzeichnen: „(abgeleitet aus [^b1] und [^b4])“.
- `CLAUDE.md` nur nach Zustimmung des Nutzers ändern.
- `status_markdown` unverändert lassen. Der Wert spielt für die Verarbeitung keine Rolle.
- Meldet Lint `invalid_frontmatter`, dem Nutzer den Befehl `pkm fix-frontmatter` vorschlagen
  (er führt ihn selbst im Terminal aus).
- Dokumente mit `kind: standard` oder `regulation` werden verarbeitet wie `note`. In Belegen und
  Zusammenfassungen von Normen die Kurzbezeichnung (`short_citation`) nennen.
- `wiki/index.md`, `wiki/_status.md`, `wiki/log.md` und `sources` im Frontmatter erzeugt
  `finish_maintenance`; `write_wiki_page` lehnt diese Dateien ab.

## Frontmatter-Vorschläge

Bei jedem **neuen** Dokument das Frontmatter prüfen (`missing_fields` aus `begin_maintenance`,
auch dünne Werte). Vorschläge als YAML-Block im Bericht, **noch nichts eintragen**:

- `title`: sprechender Titel.
- `context`: eine Zeile `"<Art>: <Inhalt>"` (Art: Chat, Podcast, Buch, Artikel, Recherche, Notiz),
  wegen `: ` in doppelten Anführungszeichen.
- `tags`: 4–8 Stück, klein, Bindestriche, Umlaute ausgeschrieben; vorhandene Tags aus
  `known_tags` wiederverwenden.
- `kind`: `note` (Standard) | `standard` / `regulation` (dann auch `short_citation` vorschlagen) |
  `correction`.

Nach ausdrücklicher Bestätigung: `read` → `hash` → `set_document_metadata` (`set` mit den
bestätigten Feldern, `add` nur für weitere `tags`). Vorhandene Werte nicht überschreiben;
`overwrite: true` nur, wenn der Nutzer das ausdrücklich will. Bei `conflict` neu lesen und dem
Nutzer melden; bei `field_exists` den vorhandenen Wert nennen und nachfragen. Jede Eintragung
ist eine neue Version des Dokuments; beim nächsten Lauf erscheint es als `meta_changed`.

## Formate

**Wiki-Seite** (`wiki/topics/`, `wiki/entities/`, `wiki/summaries/`, `wiki/syntheses/`;
Dateiname klein, Bindestriche, Umlaute ausgeschrieben: `regenwasser-ertrag.md`):

```markdown
---
type: topic            # topic | entity | summary | synthesis
title: Regenwasser-Ertrag
aliases: [Regenertrag]
tags: [zisterne, wasser]
sources: []            # erzeugt finish_maintenance
date_updated: 2026-11-02T21:10:00   # YYYY-MM-DDTHH:MM:SS, Ortszeit ohne Zeitzone
confidence: high       # high | medium | low
---

> **Kurzfassung:** Ein bis drei Sätze. Landet in index.md und in den Suchtreffern.

## Inhalt
Die Dachfläche beträgt 92 m².[^b1]
(Bis Version 2 war ein Ultraschallsensor vorgesehen.[^b3])

## Widersprüche / offene Fragen
- Ältere Notiz nennt 85 m².[^b5] Neuere Angabe (92 m²) wird verwendet.

## Siehe auch
- [[wiki/entities/tank-1]]

## Belege
[^b1]: [[documents/haus/zisterne#Dach]] · „Dachfläche laut Plan 92 m²“ · id:d-20261012-0915-x7mp · v:2 · sha:3f9a1c
[^b4]: [[documents/haus/datenblatt-tank.pdf#page=2]] · „Nutzvolumen 6500 l“ · sha:c07d44
[^b6]: [[documents/haus/notizen#Notizen]] §:Notizen#2 · „zweite Notiz“ · id:d-… · v:1 · sha:a6fd6c
```

Gliederung in „Inhalt“: Zwischenüberschriften (`###`), reine Fett-Zeilen und reine Link-Zeilen
sind erlaubt und brauchen keinen Beleg. Eine Tabelle belegst du mit einer Fußnote in der
Tabelle oder in einer Zeile direkt darunter (z. B. `[^b3]` oder `Quelle: [^b3]`).

**Beleg-Zeile:** `[^b<n>]: [[<pfad>#<anker>]] · „<zitat>“ · id:<id> · v:<version> · sha:<6 zeichen>`
- Pfad vollständig ab Vault-Wurzel, Markdown ohne `.md`, PDF/Bild mit Endung. Nur `documents/`.
- Anker = Abschnittsschlüssel **ohne** Duplikat-Suffix; bei doppelten Überschriften zusätzlich
  `§:<schlüssel>` direkt nach dem Link. Text vor der ersten Überschrift: kein Anker.
  PDF: `#page=<n>`.
- Zitat ≤ 200 Zeichen, wörtlich aus genau dieser Version.
- `id`, `v` und `sha` stehen in der Antwort von **`read`**: `id`, `version` und unter `sections`
  je Abschnitt `key` und `sha`. Für eine ältere Version `read` mit `version`. Für PDF/Bild: die
  ersten 6 Zeichen von `hash` aus `read`.
- **Belege auf Bilder:** eingebettetes oder zugehöriges Bild → Abschnitt des Dokuments, als Zitat
  der Bildverweis: `[[documents/…/notiz#Aufbau]] · „[img:schaltplan]“ · id:… · v:3 · sha:…`.
  Eigenständiges Bild → Link auf die Datei und Datei-Hash.
- **Bilder in Wiki-Seiten:** Bilder aus Dokumenten nur als Link auf die Bilddatei zeigen, mit
  Fußnote auf das Dokument; eingebettete Bilder nicht kopieren. Eigene SVG-Diagramme darfst du
  eingebettet setzen; sie gelten als Schlussfolgerung („abgeleitet aus [^b1], [^b3]“).
- Abschnitte mit `empty: true` (z. B. die H1 direkt vor dem ersten `##`) haben keinen eigenen
  Text: nicht belegen, sondern den Unterabschnitt mit dem Zitat.
- Große Dokumente: `read` mit `content: false` (nur Metadaten, `sections`, `content_length`),
  dann abschnittsweise mit `section` oder seitenweise mit `offset`/`max_chars`. Fehlt `content`
  mit `content_omitted`, war das Dokument zu groß für einen Aufruf.
- Jede Sachaussage in „Inhalt“ und „Widersprüche / offene Fragen“ endet mit mindestens einer
  Fußnote (ein Absatz aus derselben Stelle: eine Fußnote am Absatzende genügt).
- Überholte Aussagen behalten ihren Beleg auf die **alte** Version.
- `confidence: low`, wenn Quellen sich widersprechen oder nur eine unsichere Quelle vorliegt.

**Zusammenfassung** (`wiki/summaries/<dateiname-des-dokuments>.md`, `type: summary`): fasst genau
ein Dokument in seiner aktuellen Version zusammen, mit Belegen wie oben.

**Log** (`wiki/log.md`): `finish_maintenance` hängt den Eintrag an und setzt die Überschrift mit
Zeitstempel aus `operation` und `log_title` (hier `log_title: "1 neu, 1 geändert"`). Du lieferst
nur die Liste als `log_entry`:

```markdown
## [2026-11-02 21:10] ingest | 1 neu, 1 geändert
- neu: wiki/summaries/bewaesserung-zeitplan
- aktualisiert: wiki/topics/regenwasser-ertrag, wiki/entities/tank-1
- überholt: „Ultraschallsensor“ → „Schwimmerschalter“ (zisterne-ueberlaufsensor v2 → v3)
```

## Ablauf „Ingest“ („Verarbeite neue Dokumente“)

1. `begin_maintenance`.
   - `status: blocked` → Fehler (`doctor`) melden und **abbrechen**.
   - `status: needs_decision` → doppelte IDs (`ids.duplicates`) nicht selbst auflösen, sondern
     nachfragen.
   - `pending` enthält `new`, `changed`, `meta_changed`, `moved`, `deleted`, `problems`.
     Mehr als 10 Dokumente → in Etappen (je höchstens 10) verarbeiten; nicht verarbeitete
     Dokumente einfach nicht in `processed` angeben.
   - Verschiebungen sind bereits korrigiert (`fixed_citations`).
2. **`new`**: Dokument mit `read` vollständig lesen.
   1. `wiki/summaries/<name>.md` mit `write_wiki_page` anlegen, mit Belegen.
   2. Über `read_index` (und bei Bedarf `search`) betroffene Seiten bestimmen. Höchstens
      10–15 Themen-, Entitäts- und Syntheseseiten aktualisieren oder anlegen. Jede neue oder
      geänderte Aussage bekommt eine Fußnote.
   3. Querverweise in beide Richtungen setzen („Siehe auch“).
   4. Frontmatter prüfen und Vorschläge erarbeiten (siehe „Frontmatter-Vorschläge“), noch
      nichts eintragen.
   5. Bestehende Seiten vor dem Ändern mit `read` lesen und deren `hash` als `expected_hash`
      an `write_wiki_page` geben (immer den ganzen Seiteninhalt schreiben). Bei `conflict` neu
      lesen.
3. **`changed`**: Nur die gemeldeten Abschnitte verarbeiten. Diff lesen:
   `history` mit `diff_from: <processed_version>`.
   - `changed`/`added`: betroffene Aussagen auf den neuen Stand bringen, Belege auf die **neue
     Version**.
   - Geänderte Entscheidung oder Tatsache: früheren Stand als „Bis Version n: …“ mit Beleg auf
     die **alte** Version behalten, wenn er für die Nachvollziehbarkeit wichtig ist; sonst nur
     im Log vermerken.
   - `removed`: betroffene Aussagen prüfen (überholt kennzeichnen statt löschen).
   - `renamed`: nur Anker anpassen (erledigt `begin_maintenance`/`finish_maintenance`).
   - Leere Abschnittsliste (nur Reihenfolge geändert): nichts inhaltlich tun.
   - Belege auf unveränderte Abschnitte hebt `finish_maintenance` selbst auf die neue Version
     (nur `v:`; `sha:` bleibt).
   - Zusammenfassungsseite des Dokuments aktualisieren.
4. **`meta_changed`**: nur Zusammenfassungsseite (Titel, Themen, Verweise) anpassen. Die Belege
   hebt `finish_maintenance` auf die neue Version.
5. **`deleted`**: betroffene Aussagen (siehe `wiki_pages`) **nicht löschen**, sondern unter
   „Widersprüche / offene Fragen“ vermerken: „Original nicht mehr vorhanden (letzter Stand in
   Git, v<n>)“, `confidence: low`, Rückfrage im Bericht. Den Schlüssel in `removed` angeben.
6. **Korrekturen** (`kind: correction` im Frontmatter): Die Korrektur des Nutzers hat Vorrang vor
   älteren Quellen und gilt selbst als Beleg. Betroffene Seite (siehe `related`) anpassen, die
   alte Aussage im Log als ersetzt vermerken. Widerspricht die Korrektur einer **neueren** Quelle
   → nachfragen.
7. **Bilder**: Jedes neue oder geänderte Bild (eingebettet oder verlinkt, siehe `images` in
   `read`) mit `read_image` ansehen. Den Inhalt in Worten übernehmen und mit `[img:<name>]` als
   Zitat belegen. Zugehörige Bilder bekommen keine eigene Zusammenfassung; eigenständige Bilder
   (ohne Dokument, das darauf verweist) wie bisher. **PDF**: `read` liefert nur Größe und `hash`.
   Den Inhalt liest du, wenn der Vault-Ordner in der Unterhaltung verbunden ist; sonst das PDF
   nicht in `processed` angeben und im Bericht nennen.
8. Abschließen mit `finish_maintenance`:
   - `processed`: IDs (bzw. Pfade bei PDF/Bild) aller in diesem Lauf verarbeiteten Dokumente –
     auch der verschobenen und nur in den Metadaten geänderten. Die belegenden Seiten ermittelt
     das Tool aus den Fußnoten; `warnings` nennt Dokumente ohne Beleg.
   - `removed`: Schlüssel verarbeiteter gelöschter Dokumente.
   - `log_entry`, `log_title`, bei Bedarf `questions` (Rückfragen für `wiki/_status.md`).
   - Meldet `lint` Fehler in deinen Seiten: mit `write_wiki_page` beheben und
     `finish_maintenance` erneut mit `operation: fix` aufrufen (ohne `processed`).
9. Kurzer Bericht im Chat: neue/geänderte Seiten, überholte Aussagen, Beleg-Probleme,
   Einsortier-Vorschläge (aus `wiki/_status.md`), Rückfragen – und **je neuem Dokument mit
   fehlenden Feldern den YAML-Block** mit der Frage, ob er eingetragen werden soll.

Nextcloud-Konfliktkopien werden nie verarbeitet; der Nutzer führt sie in Obsidian zusammen.

## Ablauf „Lint“

1. `begin_maintenance` mit `with_lint: true` (Ergebnis unter `lint`).
2. **Selbst beheben** (mit `write_wiki_page`): kaputte Links mit eindeutigem Ziel, fehlende
   Kurzfassungen. Verschobene Belege, `sources` und Index erledigt `finish_maintenance`.
3. **Vorschlagen statt ausführen:** fehlende Frontmatter-Felder von Dokumenten (YAML-Block wie
   unter „Frontmatter-Vorschläge“), inhaltliche Widersprüche, Zusammenlegen von Seiten, neue
   Seiten, doppelte IDs, Belege mit `newer_version`, die nicht automatisch angehoben werden
   konnten, Hinweise zu Dokumenten (`documents/` fasst du nicht an).
4. `finish_maintenance` mit `operation: lint`, `lint_report: true` (Bericht nach
   `wiki/_lint/YYYY-MM-DD.md`) und einem Log-Eintrag.

## Ablauf „Abfrage“ (im Projekt)

Erst `read_index`, dann die relevanten Seiten mit `read`, dann die Antwort mit Verweisen auf die
Wiki-Seiten. Auf Nachfrage die Belege nennen (`show_citations`; Wortlaut alter Versionen mit
`read` und `version`). Gute Antworten als Seite unter `wiki/syntheses/` anbieten (mit Belegen auf
Dokumente, nicht auf Wiki-Seiten) und nach Zustimmung mit `write_wiki_page` anlegen und mit
`finish_maintenance` (`operation: fix`) abschließen.

## Ablauf „Schema anpassen“

Änderungen an `CLAUDE.md` vorschlagen (als Diff). Schreiben nur nach Zustimmung und nur, wenn der
Vault-Ordner verbunden ist; sonst übernimmt der Nutzer die Änderung selbst.

## Unbeaufsichtigter Lauf (geplante Aufgabe)

Nicht auf Antworten warten. Frontmatter-Vorschläge **nie eintragen**, sondern als Frage über
`questions` nach `wiki/_status.md`. Konservativ entscheiden: Bei unklarer Einordnung, Duplikaten,
Widersprüchen zu neueren Quellen oder gelöschten Originalen **nichts Riskantes tun**, sondern
die Frage über `questions` von `finish_maintenance` in `wiki/_status.md` aufnehmen und im Log
vermerken. Den Lauf trotzdem mit `finish_maintenance` abschließen.
