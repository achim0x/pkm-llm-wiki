---
name: pkm-wiki
description: Pflege des PKM-Wikis im Projekt „PKM-Pflege“ – neue und geänderte Dokumente verarbeiten (Ingest), Lint, Wiki-Fragen im Pflegeprojekt, Schema anpassen. Verwenden bei „verarbeite neue Dokumente“, „Ingest“, „Lint“, „prüf das Wiki“, „was steht im Wiki zu …“ im Pflegeprojekt.
---

# PKM-Wiki pflegen

Du arbeitest direkt im Vault-Ordner (Dateizugriff und Shell auf dem Mac). Hilfsbefehle liefert
die CLI `pkm` (Ausgabe JSON). Sie findet den Vault selbst, wenn du im Vault-Ordner bist;
sonst `PKM_ROOT` setzen. Sprache aller Inhalte: **Deutsch**.

## Feste Regeln

- `wiki/` gehört dir. `documents/` gehört dem Nutzer: dort **nichts** ändern, verschieben oder
  löschen. Einzige Ausnahme: `id`/`version` – und zwar nur über `pkm ids` und `pkm versions`.
- Im Wiki **nichts löschen**. Aussagen und Belege ergänzen, aktualisieren oder als überholt
  kennzeichnen.
- **Keine Aussage ohne Beleg** auf ein Dokument in `documents/`. Wiki-Seiten sind keine Belege.
  Zitate **wörtlich** aus der genannten Version kopieren. Nichts erfinden; Lücken als offene
  Frage markieren.
- Eigene Schlussfolgerungen kennzeichnen: „(abgeleitet aus [^b1] und [^b4])“.
- `CLAUDE.md` nur nach Zustimmung des Nutzers ändern.
- `wiki/index.md`, `wiki/_status.md` und `sources` im Frontmatter nie von Hand pflegen –
  dafür gibt es `pkm index`, `pkm status`, `pkm sync-citations`.

## Formate

**Wiki-Seite** (`wiki/topics/`, `wiki/entities/`, `wiki/summaries/`, `wiki/syntheses/`;
Dateiname klein, Bindestriche, Umlaute ausgeschrieben: `regenwasser-ertrag.md`):

```markdown
---
type: topic            # topic | entity | summary | synthesis
title: Regenwasser-Ertrag
aliases: [Regenertrag]
tags: [zisterne, wasser]
sources: []            # erzeugt pkm sync-citations
updated: 2026-11-02
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

**Beleg-Zeile:** `[^b<n>]: [[<pfad>#<anker>]] · „<zitat>“ · id:<id> · v:<version> · sha:<6 zeichen>`
- Pfad vollständig ab Vault-Wurzel, Markdown ohne `.md`, PDF/Bild mit Endung. Nur `documents/`.
- Anker = Abschnittsschlüssel **ohne** Duplikat-Suffix; bei doppelten Überschriften zusätzlich
  `§:<schlüssel>` direkt nach dem Link. Text vor der ersten Überschrift: kein Anker.
  PDF: `#page=<n>`.
- Zitat ≤ 200 Zeichen, wörtlich aus genau dieser Version.
- `id`, `v`, `sha` holst du mit **`pkm sha <dokument> --section "<schlüssel>"`**
  (liefert `id`, `version`, `sha`). Für PDF/Bild: `pkm sha <datei>` (`file_hash`).
- Jede Sachaussage in „Inhalt“ und „Widersprüche / offene Fragen“ endet mit mindestens einer
  Fußnote (ein Absatz aus derselben Stelle: eine Fußnote am Absatzende genügt).
- Überholte Aussagen behalten ihren Beleg auf die **alte** Version.
- `confidence: low`, wenn Quellen sich widersprechen oder nur eine unsichere Quelle vorliegt.

**Zusammenfassung** (`wiki/summaries/<dateiname-des-dokuments>.md`, `type: summary`): fasst genau
ein Dokument in seiner aktuellen Version zusammen, mit Belegen wie oben.

**Log** (`wiki/log.md`, nur anhängen):

```markdown
## [2026-11-02 21:10] ingest | 1 neu, 1 geändert
- neu: wiki/summaries/bewaesserung-zeitplan
- aktualisiert: wiki/topics/regenwasser-ertrag, wiki/entities/tank-1
- überholt: „Ultraschallsensor“ → „Schwimmerschalter“ (zisterne-ueberlaufsensor v2 → v3)
```

## Ablauf „Ingest“ („Verarbeite neue Dokumente“)

1. `pkm doctor --short` – bei Fehlern (z. B. Konfliktkopien) **abbrechen** und melden.
   Dann `pkm versions` (Änderungen von Hand, auch vom Windows-Rechner, werden Versionen).
2. `pkm ids` – fehlende IDs eintragen. Gemeldete `duplicates` nicht selbst auflösen, sondern
   nachfragen (die jüngere Kopie bekäme nach Rückfrage eine neue ID).
3. `pkm pending` – JSON mit `new`, `changed`, `meta_changed`, `moved`, `deleted`, `problems`.
   Mehr als 10 Dokumente → in Etappen (je höchstens 10) verarbeiten.
4. `moved` vorhanden → `pkm fix-citations` (passt Links, Anker umbenannter Abschnitte und
   `sources` an).
5. **`new`**: Dokument vollständig lesen.
   1. `wiki/summaries/<name>.md` anlegen, mit Belegen.
   2. Über `wiki/index.md` (und bei Bedarf Suche/`grep`) betroffene Seiten bestimmen. Höchstens
      10–15 Themen-, Entitäts- und Syntheseseiten aktualisieren oder anlegen. Jede neue oder
      geänderte Aussage bekommt eine Fußnote.
   3. Querverweise in beide Richtungen setzen („Siehe auch“).
6. **`changed`**: Nur die gemeldeten Abschnitte verarbeiten. Diff lesen:
   `pkm history id:<id> --diff <processed_version>`.
   - `changed`/`added`: betroffene Aussagen auf den neuen Stand bringen, Belege auf die **neue
     Version**.
   - Geänderte Entscheidung oder Tatsache: früheren Stand als „Bis Version n: …“ mit Beleg auf
     die **alte** Version behalten, wenn er für die Nachvollziehbarkeit wichtig ist; sonst nur
     im Log vermerken.
   - `removed`: betroffene Aussagen prüfen (überholt kennzeichnen statt löschen).
   - `renamed`: nur Anker anpassen (`pkm fix-citations` erledigt das).
   - Leere Abschnittsliste (nur Reihenfolge geändert): nichts inhaltlich tun.
   - Belege auf unveränderte Abschnitte auf die neue Version anheben (nur `v:` und `sha:`).
   - Zusammenfassungsseite des Dokuments aktualisieren.
7. **`meta_changed`**: nur Zusammenfassungsseite (Titel, Themen, Verweise) anpassen.
8. **`deleted`**: betroffene Aussagen (siehe `wiki_pages`) **nicht löschen**, sondern unter
   „Widersprüche / offene Fragen“ vermerken: „Original nicht mehr vorhanden (letzter Stand in
   Git, v<n>)“, `confidence: low`, Rückfrage im Bericht. Danach `pkm mark <key> --remove`.
9. **Korrekturen** (`kind: correction` im Frontmatter): Die Korrektur des Nutzers hat Vorrang vor
   älteren Quellen und gilt selbst als Beleg. Betroffene Seite (siehe `related`) anpassen, die
   alte Aussage im Log als ersetzt vermerken. Widerspricht die Korrektur einer **neueren** Quelle
   → nachfragen.
10. Abschließen:
    ```
    pkm sync-citations
    pkm mark <id>… --pages <wiki-seite>…   # je Dokument die Seiten, die es belegt
    pkm index
    pkm status
    ```
    Eintrag in `wiki/log.md` anhängen. Dann `pkm lint` und gemeldete Beleg-Fehler in deinen
    Seiten beheben.
11. `pkm commit-wiki -m "pkm: ingest <n> documents"`.
12. Kurzer Bericht im Chat: neue/geänderte Seiten, überholte Aussagen, Beleg-Probleme,
    Einsortier-Vorschläge (aus `wiki/_status.md`), Rückfragen.

Nextcloud-Konfliktkopien werden nie verarbeitet; der Nutzer führt sie in Obsidian zusammen.

## Ablauf „Lint“

1. `pkm lint`.
2. **Selbst beheben:** verschobene Belege (`pkm fix-citations`), kaputte Links mit eindeutigem
   Ziel, fehlende Kurzfassungen, `sources` (`pkm sync-citations`), Index (`pkm index`).
3. **Vorschlagen statt ausführen:** inhaltliche Widersprüche, Zusammenlegen von Seiten, neue
   Seiten, doppelte IDs, Belege mit `newer_version`, die nicht automatisch angehoben werden
   konnten, Hinweise zu Dokumenten (`documents/` fasst du nicht an).
4. `pkm lint --report` (Bericht nach `wiki/_lint/YYYY-MM-DD.md`), Eintrag im Log,
   `pkm commit-wiki -m "pkm: lint"`.

## Ablauf „Abfrage“ (im Projekt)

Erst `wiki/index.md`, dann die relevanten Seiten, dann die Antwort mit Verweisen auf die
Wiki-Seiten. Auf Nachfrage die Belege nennen (Fußnoten auflösen; Wortlaut alter Versionen mit
`pkm show id:<id> --version <n> --section "<schlüssel>"`). Gute Antworten als Seite unter
`wiki/syntheses/` anbieten (mit Belegen auf Dokumente, nicht auf Wiki-Seiten).

## Ablauf „Schema anpassen“

Änderungen an `CLAUDE.md` vorschlagen (als Diff) und erst nach Zustimmung schreiben.

## Unbeaufsichtigter Lauf (geplante Aufgabe)

Nicht auf Antworten warten. Konservativ entscheiden: Bei unklarer Einordnung, Duplikaten,
Widersprüchen zu neueren Quellen oder gelöschten Originalen **nichts Riskantes tun**, sondern
die Frage mit `pkm status --question "<frage>"` in `wiki/_status.md` aufnehmen und im Log
vermerken. Den Lauf trotzdem mit `pkm commit-wiki` abschließen.
