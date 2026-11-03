---
name: pkm-access
description: Das persönliche Wissensmanagement (PKM) aus normalen Chats nutzen – über die MCP-Tools des Servers „pkm“. Verwenden bei „leg das ins PKM“, „speicher das Ergebnis“, „führ das im Dokument zu … weiter“, „aktualisier mein Dokument …“, „was weiß mein Wiki über …“, „woher stammt das?“, „was hat sich geändert?“, „mach das rückgängig“, „korrigier im Wiki …“, „notier mir kurz …“, „setz das auf meine Todo-Liste“, „hak … ab“, „was steht auf meiner Liste?“.
---

# PKM aus Chats nutzen

Das PKM besteht aus `documents/` (Dokumente des Nutzers) und `wiki/` (vom Pflege-Agenten
kompiliertes Wiki mit Belegen). Aus Chats ist das Wiki **nur lesbar**. Dokumente werden über
die Tools des MCP-Servers `pkm` angelegt und geändert; jede Änderung ergibt eine neue Version
mit Git-Commit.

## Grundregel – ohne Ausnahme

**Jeder schreibende Aufruf** (`create_document`, `rewrite_document`, `append_to_document`,
`edit_document`, `update_frontmatter`, `add_image`, `restore_document`) erfolgt erst, **nachdem ein Entwurf
gezeigt und vom Nutzer bestätigt wurde**. Das gilt auch, wenn der Nutzer „direkt“, „einfach
speichern“ o. Ä. sagt: Dann den Entwurf knapp zeigen und kurz bestätigen lassen.

Ziele (`target`) können ein Pfad, ein Wikilink, `id:d-…` oder eine Kurzbezeichnung aus
`short_citation` (z. B. `EN 61000-4-6:2014`) sein. Nach dem ersten Kontakt
mit einem Dokument immer die **ID** verwenden – der Ablageort kann sich ändern.

## Neu ablegen

1. Ergebnis verdichten in die Abschnitte:
   `## Ergebnis`, `## Entscheidungen`, `## Offene Punkte`, `## Kontext / Begründung`.
   Nur Belastbares aufnehmen, Hypothesen als solche kennzeichnen.
2. Titel, `tags` (Kleinbuchstaben, Bindestriche) und ggf. `related` vorschlagen. Beim Anlegen
   `toolchain` mit dem eigenen Modellnamen und `pkm-mcp` übergeben, z. B.
   `"Claude Opus 5.5 (pkm-mcp)"`. Bei Normen oder Gesetzen `kind` (`standard`/`regulation`) und,
   falls bekannt, `short_citation` und `date_document` mitgeben.
3. Vorher prüfen, ob es schon ein Dokument gibt: `search` mit `scope: "documents"`.
   Gibt es eines zur selben Fragestellung, fragen, ob es aktualisiert werden soll (siehe unten).
4. **Entwurf zeigen**, nach Bestätigung `create_document` (`content` ohne Frontmatter,
   `context` z. B. „Chat: <Thema>“).
5. Dem Nutzer ID, Pfad und Version nennen. Die ID im Chatverlauf behalten.

## Fortgeführte Diskussion (Standard: Dokument aktualisieren)

1. Dokument finden: ID aus diesem Chat verwenden, sonst `search` (`scope: "documents"`).
   Ein Treffer → kurz bestätigen lassen; mehrere → nachfragen. Unklar, ob Fortsetzung oder
   neues Thema → nachfragen. Faustregel: gleiche Fragestellung = aktualisieren, neues
   Teilthema = neues Dokument mit `related` auf das alte.
2. `read(id:…)` – liefert Inhalt, `version` und `hash`.
   Großes Dokument (`content_omitted`, oder vorab mit `content: false` an `content_length`
   erkannt): Abschnitte einzeln mit `section` lesen und nur mit `edit_document` bzw.
   `append_to_document` ändern, **nie** `rewrite_document` mit einem Teil des Inhalts.
3. Neue Fassung erstellen, die den **aktuellen Gesamtstand** zeigt:
   - „Ergebnis“ neu formulieren.
   - „Entscheidungen“: geänderte ersetzen, neue ergänzen. Kein „überholt“ stehen lassen.
   - „Offene Punkte“: erledigte entfernen, neue ergänzen.
   - „Kontext / Begründung“: Begründung für Änderungen ergänzen, soweit nötig.
4. **Vorher/Nachher je Abschnitt** zeigen plus eine einzeilige Änderungsnotiz
   (z. B. „Sensor: Schwimmerschalter statt Ultraschall“). Bestätigen lassen.
5. Mehrere Abschnitte betroffen → **ein** `rewrite_document` mit `expected_hash` und `note`.
   Kleine, gezielte Änderung → `edit_document` bzw. `append_to_document`.
6. Neue Version und Diff kurz nennen.

**Datierter Fortsetzungsabschnitt** (`## Fortsetzung YYYY-MM-DD`) nur, wenn der Nutzer das
**ausdrücklich** verlangt („als Fortsetzung dokumentieren“, „mit Verlauf im Dokument“). Nie
von sich aus vorschlagen. Dann: `append_to_document` mit dem Abschnitt (Kontext, Ergebnis,
Entscheidungen, Offene Punkte; am selben Tag Zusatz „(2)“), revidierte Entscheidungen im
Original per `edit_document` markieren:
` — *überholt am YYYY-MM-DD, siehe [[#Fortsetzung YYYY-MM-DD]]*`.

## Kleine Änderungen

`read` → `edit_document` / `append_to_document` / `update_frontmatter` → Vorher/Nachher zeigen
→ bestätigen lassen → ausführen → Version und Diff nennen.

- `append_to_document` mit `section`: Abschnittsschlüssel, z. B. `"Offene Punkte"`,
  `"_preamble"` (Text vor der ersten Überschrift) oder bei doppelten Überschriften `"Notizen#2"`.
- `edit_document`: `old` muss genau einmal vorkommen; ausreichend Kontext mitgeben.
- `update_frontmatter`: `id`, `version`, `date_markdown`, `date_updated` und `status_markdown`
  sind geschützt. Achtung:
  Kommentare im Frontmatter gehen dabei verloren – bei Dokumenten mit Kommentaren vorher erwähnen.

## Rückmeldungen der Tools

| `status` | Vorgehen |
|---|---|
| `created` / `changed` | Version (und ggf. ID, Pfad) nennen |
| `unchanged` | Es gab nichts zu ändern; so mitteilen |
| `conflict` | Datei wurde inzwischen geändert (z. B. in Obsidian). **Neu lesen**, Fassung auf dem aktuellen Stand neu aufbauen, erneut Entwurf zeigen. Nie blind wiederholen |
| `large_shortening` | Die genannten `missing_sections` bzw. die Kürzung dem Nutzer nennen und **ausdrücklich** bestätigen lassen, dann erneut mit `confirm_shortening: true` |
| `ambiguous` | Kandidaten nennen und nachfragen (bei Abschnitten: Schlüssel mit Suffix verwenden) |
| `not_found` | Ziel oder Textstelle prüfen, ggf. `search` |
| `forbidden` | Ziel ist nicht änderbar (z. B. `wiki/`); bei Wiki-Fehlern Korrektur-Dokument anlegen |
| `not_versioned` | Datei liegt in `scratch/`: es gibt keinen Verlauf und nichts wiederherzustellen |
| `git_unavailable`, `commit_failed`, `invalid_frontmatter`, `invalid_encoding` | Dem Nutzer melden; nicht umgehen |

## Verlauf

- „Was hat sich geändert?“ → `history` mit dem Dokument als `target`, bei Bedarf mit `diff_from` (und `diff_to`).
- „Wie war das vorher?“ → `read(target, version: n)`.
- „Mach das rückgängig“ → vorherige Version bestimmen, Entwurf (welche Version wird
  zurückgeholt) zeigen, nach Bestätigung `restore_document`. Die Geschichte bleibt erhalten.

## Abfragen

1. Breite Frage → `read_index`; sonst `search` (Standard-`scope` ist `wiki`).
2. Die besten Treffer mit `read` öffnen und mit Verweis auf die Wiki-Seiten antworten
   (`[[wiki/…]]`).
3. Dokumente zum Thema mit `processed: false` (über `search` mit `scope: "documents"` oder
   `list_unprocessed`) als „noch nicht im Wiki“ erwähnen.
4. **Auf Nachfrage nach Quellen** („woher stammt das?“): `show_citations` mit der Wiki-Seite
   und der Aussage als `statement`, bei Bedarf `with_excerpt: true`. Je Aussage nennen:
   Original, Abschnitt/Seite, Zitat, belegte und aktuelle Version, Status, Obsidian-Link.
   Bei `newer_version` den aktuellen Wortlaut dazu zeigen; bei `missing` sagen, dass das
   Original nicht mehr da ist (Wortlaut stammt aus dem Verlauf).
5. Ohne Nachfrage genügen die Wiki-Seiten. Die Originale anbieten, wenn die Antwort für eine
   Entscheidung gebraucht wird.

## Bilder

- **Format:** Diagramme, Skizzen, Ablauf- und Schaltpläne, Messwert-Diagramme und eigene Grafiken
  zeichnest du als **SVG**. Fotos, Screenshots und Scans bleiben **PNG**. Fotos nie vektorisieren.
- **Ablegen:** beim Anlegen oder Ändern über den Parameter `images` (`create_document`,
  `rewrite_document`, `append_to_document`, `edit_document`), in ein bestehendes Dokument auch mit
  `add_image`. Im Text steht an der Stelle `{{image:<name>}}`. Je Bild: `name` (klein,
  Bindestriche, eindeutig), `alt` (Alternativtext, eine Zeile, **immer**) und genau eine Quelle:
  `svg` (Text), `png_base64` oder `import_path`. `mode` meist weglassen (`auto`: bis 24 KB
  eingebettet, sonst Datei in `_attachments/`; in `scratch/` immer eingebettet).
- **Erst Entwurf, dann schreiben:** Im Entwurf das Bild mit zeigen (SVG direkt darstellen).
- **Im Chat hochgeladene Fotos oder Screenshots** kannst du nicht byte-genau weitergeben. Bitte den
  Nutzer, die Datei in den Importordner zu legen (`PKM_IMPORT_DIR`, Standard
  `Downloads/pkm-import`), und übernimm sie mit `import_path` (Dateiname genügt). Bei einfachen
  Grafiken alternativ eine SVG-Nachzeichnung anbieten, im Alternativtext als „nachgezeichnet“
  gekennzeichnet.
- **Lesen:** `read` zeigt eingebettete Bilder als Platzhalter `![…](pkm-image:<name> "…")` und
  listet sie unter `images`. Ansehen mit `read_image` (`target`, `image`). Base64 oder SVG-Inhalt
  nie in einen Text übernehmen.
- **Ändern:** Platzhalter in `rewrite_document`/`edit_document` unverändert stehen lassen, der
  Server setzt die Originale wieder ein. Fehlt ein Bild in der neuen Fassung, kommt
  `large_shortening` mit `removed_images` – nur nach Bestätigung mit `confirm_shortening`
  entfernen. `unknown_image`: Platzhaltername stimmt nicht.
- Bestehende eingebettete PNG bleiben unverändert. Fehler: `svg_too_complex` (dann PNG),
  `too_large_for_inline` (dann `mode: auto`), `invalid_image`, `forbidden` (`import_path`
  außerhalb des Importordners).

## Notizen und Todo-Listen (`scratch/`)

Für Kurzlebiges gibt es den Bereich `scratch/`: Er wird **nie ins Wiki übernommen** und **nicht
versioniert** (kein Commit, kein Verlauf).

- Auslöser: „notier mir kurz …“, „setz das auf meine Todo-Liste“, „hak … ab“, „was steht auf
  meiner Liste?“.
- **Neue Notiz:** `create_document` mit `area: "scratch"` (optional `folder`, z. B. `"todo"`).
- **Bestehende Liste ändern:** `append_to_document` bzw. `edit_document`, z. B. beim Abhaken
  `- [ ]` → `- [x]`. Ist unklar, welche Liste gemeint ist: `search` mit `scope: "scratch"`, bei
  mehreren Treffern nachfragen.
- **Auch hier gilt die Grundregel:** erst Entwurf bzw. Vorher/Nachher zeigen, dann nach
  Bestätigung schreiben.
- Darauf hinweisen, dass Inhalte in `scratch/` nicht ins Wiki kommen. Soll etwas dauerhaft
  festgehalten werden, stattdessen ein Dokument in `documents/` vorschlagen (oder die Notiz in
  Obsidian nach `documents/` verschieben lassen).
- Für Dateien in `scratch/` **keine Version und keinen Commit nennen**. `history` und
  `restore_document` liefern dort `not_versioned`.
- `search` durchsucht `scratch/` nur mit `scope: "scratch"`.

## Korrekturen am Wiki

Nie direkt. Immer als Dokument: Entwurf mit falscher Aussage, richtiger Aussage und
Begründung zeigen, nach Bestätigung `create_document` mit `kind: "correction"` und
`related: ["[[wiki/…]]"]` (betroffene Wiki-Seite). Der Pflege-Agent arbeitet sie ein.
