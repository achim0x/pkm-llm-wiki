# PKM mit LLM-Wiki – Abnahmeprotokoll

**Bezug:** Spezifikation 0.26, Abschnitt 14 („Abnahme (manuell)“) · Umsetzungsplan Phase 7

Die Abnahme läuft auf dem **Mac** mit echtem Vault im Cloud-Speicher (z. B. Nextcloud, OneDrive,
Google Drive), Claude Desktop und Obsidian sowie für Schritt 9 auf dem **Windows-Rechner**. Die
Einrichtung selbst ist Teil der Abnahme (Schritt 0, nach [installation.de.md](installation.de.md)). Die
Schritte 1–12 setzen eingeschaltete Versionsverwaltung voraus (Git installiert); der Betrieb ohne Git
steht unter den Zusatzprüfungen.

Alle Inhalte, die das PKM erzeugt (Wiki-Seiten, Index, Status, Log, Commit-Notizen, Berichte), sind
englisch; die Eingaben in den Chats dürfen deutsch bleiben.

Ergebnis je Schritt eintragen: ✅ erfüllt · ⚠️ erfüllt mit Befund · ❌ nicht erfüllt.
Befunde unten unter „Befunde“ sammeln; sie werden danach behoben (Code oder Skill-Formulierung).

| Feld | Eintrag |
|---|---|
| Datum | |
| Mac / macOS-Version | |
| Claude Desktop Version | |
| Obsidian Version (Mac / Windows) | |
| Stand von `pkm-tools` | Datum des Installer-Laufs bzw. Commit des installierten Branches |
| Cloud-Speicher | |
| Git-Version | `git --version` |

---

## 0. Installation und Vorbereitung

**Aktion:** Auf dem Mac den Installer ausführen (Einrichtung, Abschnitt 2) und die Fragen von
`pkm setup` beantworten. Eine vorhandene Konfiguration von Claude Desktop vorher nicht löschen.

**Erwartet**
- [ ] Der Installer meldet „Git found: version control will be on.“ und installiert `pkm`,
      `pkm-mcp` und `pkm-pflege-mcp` nach `~/.local/bin`.
- [ ] `pkm setup` erkennt den Cloud-Dienst des Vault-Ordners und meldet keine Dateien „nur online“.
- [ ] `pkm setup` fragt nach der Dokumentsprache für im Chat erzeugte Dokumente (`en` oder `de`).
- [ ] `~/Library/Application Support/pkm/config.toml` enthält `PKM_ROOT`, `PKM_VAULT_NAME`,
      `PKM_VERSIONING = true`, `PKM_GIT` und `PKM_LANGUAGE` mit der gewählten Sprache.
- [ ] `pkm setup` meldet, ob die Server in Claude Desktop schon eingetragen sind; fehlen sie oder
      weichen sie ab, zeigt es die Änderung und fragt, ob es `claude_desktop_config.json` ändern darf.
- [ ] Bei „ja“: `pkm` und `pkm-pflege` nur mit `command`, andere Server unverändert, Sicherungskopie
      `claude_desktop_config.json.<datum>.bak` daneben.
- [ ] Probe mit „nein“ (z. B. beim zweiten Lauf nach Entfernen eines Eintrags): die Datei bleibt
      unverändert, der Assistent zeigt den JSON-Text zum Selbst-Eintragen.
- [ ] `~/Library/Application Support/pkm/skills/` enthält `pkm-access.zip` und `pkm-wiki.zip`;
      beide sind in Claude Desktop hochgeladen.
- [ ] `.obsidian/app.json` enthält die Einstellungen aus Spezifikation 13; Obsidian zeigt sie nach
      einem Neustart.
- [ ] Ein zweiter Lauf von `pkm setup` ändert nichts (keine neue Sicherungskopie).
- [ ] Nach dem Neustart von Claude Desktop erscheinen die 15 `pkm`-Tools und der Server
      `pkm-pflege`.

Für die Prüfbefehle im Terminal (den Vault kennt `pkm` aus `config.toml`):

```bash
alias pkmgit='git --git-dir="$HOME/Library/Application Support/pkm/git" --work-tree="<VAULT>"'
```

```bash
pkm doctor
```

Erwartet: `"status": "ok"`. Warnungen (z. B. Obsidian-Einstellungen) vor dem Start beheben.

**Ergebnis:** ☐  **Notiz:**

Testthema für die Schritte: der Überlaufsensor einer Zisterne. Jedes andere Thema geht genauso;
dann die Eingaben sinngemäß anpassen.

---

## Schritt 1 – Ablegen aus einem Chat

**Eingabe** (neuer, normaler Chat, nicht im Pflegeprojekt):

> Wir planen den Überlaufsensor für die Zisterne. Ergebnis: Der Überlauf wird per
> Ultraschallsensor erkannt. Entscheidung: Ultraschallsensor am Deckel. Offen: Kabelweg und
> Montageort. Die Dachfläche ist laut Plan 92 m². Leg das Ergebnis ins PKM.

**Erwartet**
- [ ] Der Chat prüft per `search`, ob es schon ein Dokument gibt.
- [ ] Der Chat zeigt **erst einen Entwurf** (Titel, Themen, Abschnitte) und schreibt erst nach
      Bestätigung.
- [ ] Titel, Text und Abschnitte sind in der gewählten Dokumentsprache (Deutsch: Ergebnis,
      Entscheidungen, Offene Punkte, Kontext / Begründung; Englisch: Result, Decisions, Open points,
      Context / rationale).
- [ ] Danach nennt er ID, Pfad und `version: 1`.
- [ ] Datei liegt in `documents/_inbox/<slug>_YYYY-MM-DD.md` mit `id` und `version: 1`.
- [ ] Es gibt genau einen Commit:

```bash
pkmgit log -1 --format='%s%n%b' --name-only
```

Erwartet: `doc: <Titel> v1`, Zeilen `PKM-Id`, `PKM-Version: 1`, `PKM-Source: chat`, nur diese
eine Datei.

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 2 – Erster Pflegelauf

**Eingabe** (Projekt „PKM-Pflege“, Vault-Ordner verbunden): „Verarbeite neue Dokumente.“

**Erwartet**
- [ ] Der Agent beginnt mit `begin_maintenance` (doctor, versions, ids, pending) und schreibt
      Seiten mit `write_wiki_page`.
- [ ] `wiki/summaries/<name>.md` mit `> **Summary:**`, Abschnitt „Content“ und Belegen (`v:1`).
- [ ] Mindestens eine Themen- oder Entitätsseite mit Belegen und „See also“.
- [ ] `wiki/index.md` und `wiki/_status.md` aktualisiert, Eintrag in `wiki/log.md`.
- [ ] Agenten-Commit mit nur `wiki/` und `.pkm/state.json`:

```bash
pkmgit log -1 --format='%s%n%b' --name-only
```

```bash
pkm lint
```

Erwartet: `pkm: ingest … documents`, `PKM-Source: agent`; Lint ohne Fehler.

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 3 – Einsortieren in Obsidian

**Aktion:** Das Dokument in Obsidian von `documents/_inbox/` in einen Ordner wie
`documents/haus/` verschieben (Drag & Drop im Dateibaum).

**Erwartet**
- [ ] In den Wiki-Seiten zeigen die Belege (`[^b…]: [[documents/haus/…]]`) und `sources`
      sofort auf den neuen Ort (Obsidian aktualisiert die Links).
- [ ] `pkm lint` meldet kein `citation_moved`.

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 4 – Fortsetzung in einem neuen Chat

**Eingabe** (neuer normaler Chat):

> Führ die Diskussion zum Überlaufsensor weiter: Wir nehmen doch einen Schwimmerschalter statt
> Ultraschall, weil der Deckel oft beschlagen ist. Der Montageort ist geklärt: am Überlaufrohr.

**Erwartet**
- [ ] Der Chat findet das Dokument über `search` (am neuen Ort) und bestätigt kurz.
- [ ] Er zeigt **Vorher/Nachher je Abschnitt** und eine einzeilige Änderungsnotiz.
- [ ] Nach Bestätigung: **ein** `rewrite_document`, Rückgabe `version: 2` mit Diff.
- [ ] Das Dokument enthält **keinen** Abschnitt „Continuation …“; „Decisions“ zeigt nur
      noch den Schwimmerschalter, „Open points“ nicht mehr den Montageort.

```bash
pkmgit log -2 --format='%s | %(trailers:key=PKM-Source,valueonly)'
```

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 5 – Verlauf

**Eingabe** (gleicher Chat): „Was hat sich geändert?“

**Erwartet**
- [ ] Der Chat ruft `history` auf und nennt v1 → v2 mit der Änderungsnotiz.
- [ ] Auf Nachfrage zeigt er den Diff (`diff_from: 1`).

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 6 – Zweiter Pflegelauf

**Eingabe** (Pflegeprojekt): „Verarbeite neue Dokumente.“

**Erwartet**
- [ ] `pkm pending` meldet das Dokument unter `changed` mit `processed_version: 1`,
      `version: 2` und genau den geänderten Abschnitten.
- [ ] Der Agent liest den Diff (`history` mit `diff_from: 1`) und verarbeitet nur diese Abschnitte.
- [ ] Das Wiki zeigt den Schwimmerschalter mit Beleg auf `v:2`.
- [ ] Zusätzlich steht „Up to version 1: … ultrasonic sensor …“ mit Beleg auf `v:1`.
- [ ] Belege auf unveränderte Abschnitte (z. B. Dachfläche) sind auf `v:2` angehoben.
- [ ] `wiki/log.md` vermerkt „outdated: … (v1 → v2)“; Agenten-Commit.

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 7 – Quellen

**Eingabe** (normaler Chat): „Was weiß mein Wiki über den Überlaufsensor?“ und danach „Woher
stammt die Angabe zur Dachfläche?“

**Erwartet**
- [ ] Antwort mit Verweis auf die Wiki-Seiten.
- [ ] Auf die Quellenfrage: `show_citations` mit der Aussage; Original (aktueller Pfad),
      der passende Abschnitt, Zitat, belegte und aktuelle Version,
      Status `ok`, ggf. `obsidian://`-Link (öffnet das Dokument in Obsidian).

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 8 – Fortsetzung als datierter Abschnitt

**Eingabe** (normaler Chat): „Dokumentiere das als Fortsetzung: Der Schwimmerschalter wird mit
5 m Kabel bestellt.“

**Erwartet**
- [ ] Erst jetzt entsteht per `append_to_document` ein Abschnitt `## Continuation YYYY-MM-DD`
      (context, result, decisions, open points), nach Entwurf und Bestätigung.
- [ ] Revidierte Entscheidungen im Original werden ggf. per `edit_document` mit
      „— *outdated on …, see [[#Continuation …]]*“ markiert.
- [ ] Neue Version mit Commit.

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 9 – Änderung auf dem Windows-Rechner

**Aktion:** Auf dem Windows-Rechner in Obsidian im Dokument einen offenen Punkt ergänzen, Sync
abwarten (Sync-Symbol des Cloud-Clients auf beiden Rechnern grün bzw. „aktuell“). Dann im Pflegeprojekt „Verarbeite neue
Dokumente.“

**Erwartet**
- [ ] `pkm versions` committet die Änderung als neue Version mit `PKM-Source: user`:

```bash
pkmgit log -3 --format='%s | %(trailers:key=PKM-Source,valueonly)'
```

- [ ] Das Wiki ist aktualisiert (neuer offener Punkt in der Zusammenfassung).
- [ ] Die Datei hat danach LF-Zeilenenden; der Inhalt gilt nicht wegen CRLF als geändert.

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 10 – Todo-Liste in `scratch/`

**Eingabe** (normaler Chat): „Setz ‚Filter der Zisternenpumpe reinigen‘ auf meine Todo-Liste.“

**Erwartet**
- [ ] Der Chat zeigt einen Entwurf und legt nach Bestätigung eine Notiz in `scratch/` an
      (`create_document` mit `area: "scratch"`), ohne Version und ohne Commit.
- [ ] Er weist darauf hin, dass `scratch/` nicht ins Wiki übernommen wird.
- [ ] „Hak den Filter ab“ → Vorher/Nachher, dann `- [x]` in der Datei; wieder ohne Commit.
- [ ] Nach einem Pflegelauf taucht der Eintrag nicht im Wiki auf:

```bash
pkmgit log -3 --format='%s'
```

```bash
grep -ri "zisternenpumpe" "$PKM_ROOT/wiki" || echo "nicht im Wiki"
```

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 11 – Abweichende Data-URI korrigieren

**Aktion:** In Obsidian in ein Dokument unter `documents/` ein SVG im Referenzstil mit `;utf8` und nicht
kodierten Zeichen einfügen, z. B.:

```markdown
Der Aufbau: ![Plan][plan] siehe oben.

[plan]: <data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='20'><rect fill='#f00' width='40' height='20'/></svg>>
```

Dann im Pflegeprojekt „Verarbeite neue Dokumente.“

**Erwartet**
- [ ] Der Bericht nennt das Bild mit Fundstelle und Befunden (`reference_style`, `svg_parameters`,
      `unencoded_chars`, `not_own_line`, `missing_name`), zeigt den Vorschlag und fragt nach.
- [ ] Ohne Bestätigung ändert sich nichts am Dokument.
- [ ] Nach Bestätigung (`fix_images` mit `apply: true`) gibt es eine neue Version, der Commit trägt
      `PKM-Fix: images`; das Bild steht in einer eigenen Zeile, die Definition ist entfernt.
- [ ] Obsidian zeigt das Bild an.
- [ ] Nächster Pflegelauf: das Dokument hat `image_notation_only: true`; Belege mit `[img:plan]`
      bleiben `ok` (auf die neue Version angehoben).

```bash
pkmgit log -1 --format='%B' | grep PKM-Fix
```

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 12 – Doctor und Lint

```bash
pkm doctor
```

```bash
pkm lint --report
```

**Erwartet**
- [ ] `doctor`: `"status": "ok"`, `"errors": 0` (auch `scratch_ignored`).
- [ ] `lint`: `"summary": {"error": 0, …}`; Bericht unter `wiki/_lint/YYYY-MM-DD.md`.
- [ ] Hinweise (`info`) und Warnungen sind erklärbar und im Befund notiert.

**Ergebnis:** ☐  **Notiz:**

---

## Zusatzprüfungen (empfohlen)

| Prüfung | Vorgehen | Erwartet | Ergebnis |
|---|---|---|---|
| Konflikt | Dokument per Chat lesen lassen, dann in Obsidian ändern, dann Änderung im Chat bestätigen | `conflict`, Chat liest neu und baut neu auf | ☐ |
| Kürzungsschutz | Im Chat „kürze das Dokument auf das Ergebnis“ | `large_shortening`, ausdrückliche Rückfrage | ☐ |
| Wiki-Korrektur | Im Chat „korrigier im Wiki: die Dachfläche ist 95 m²“ | Dokument mit `kind: correction` in `_inbox/`, Wiki unverändert; nächster Pflegelauf arbeitet es ein | ☐ |
| Rückgängig | „Mach die letzte Änderung rückgängig“ | `restore_document` nach Bestätigung, neue Version, Notiz „restored from v…“ | ☐ |
| Konfliktkopie | Konfliktkopie des Cloud-Speichers erzeugen (gleichzeitige Änderung auf zwei Rechnern) | `pkm doctor --short` meldet sie, Pflegelauf bricht ab | ☐ |
| Kein `.git` im Vault | `ls -a "<VAULT>"` | kein `.git` | ☐ |
| Umgewandelte Norm | Norm mit unquotiertem `: ` im Titel und `short citation` nach `documents/` legen, `pkm lint`, dann `pkm fix-frontmatter` (erst ohne, dann mit Ziel) | Lint: `invalid_frontmatter` mit Hinweis; ohne Ziel nur Liste; mit Ziel nur Titelzeile und Feldname geändert. Nächster Pflegelauf hängt nur `id`/`version` an | ☐ |
| Kurzbezeichnung | Im Chat „Was steht in EN 61000-4-6:2014 zum Anwendungsbereich?“ | Das Dokument wird über `short_citation` gefunden | ☐ |
| Obsidian-Typen | Eigenschaften eines neuen Chat-Dokuments in Obsidian ansehen | `date_markdown`/`date_updated` als Datum & Uhrzeit, `tags` als Tags | ☐ |
| SVG-Diagramm | Im Chat „Zeichne den Aufbau als Diagramm in das Dokument“ | Entwurf mit Bild, nach Bestätigung eingebettetes SVG (`pkm:<name>`), in Obsidian im Lese- und Live-Vorschau-Modus sichtbar (auch mit `|400`) | ☐ |
| Foto aus dem Importordner | Foto (JPEG vom Smartphone) über den Cloud-Speicher nach `pkm_img_import/` legen, im Chat „nimm foto.png mit ins Dokument“ | über 24 KB: Datei in `documents/_attachments/`, im selben Commit wie das Dokument; in Obsidian sichtbar und richtig gedreht; keine GPS-Daten in der Datei | ☐ |
| Bild im Pflegelauf | Nächster Pflegelauf nach den beiden Bildern | `read_image` wird genutzt, Inhalt in Worten mit Beleg `[img:<name>]`, Bilddatei nicht als eigenes Dokument | ☐ |
| Bild ändern | Die Bilddatei in `_attachments/` ersetzen, Pflegelauf | Dokument bekommt eine neue Version mit `PKM-Source: user`, `pending` meldet den Abschnitt mit dem Bild | ☐ |


**Dokumentsprache:**

| Prüfung | Vorgehen | Erwartet | Ergebnis |
|---|---|---|---|
| Sprache wechseln | `pkm setup --language en` (bzw. `de`), Claude Desktop neu starten, in einem deutschsprachigen Chat etwas ablegen | Neues Dokument in der anderen Sprache mit deren Abschnittsnamen; ein bestehendes Dokument behält beim Fortschreiben seine Sprache | ☐ |
| Ausdrücklicher Wunsch | „Leg das auf Englisch ab“ bei Dokumentsprache Deutsch (bzw. umgekehrt) | Der Wunsch des Nutzers gilt | ☐ |

**Betrieb ohne Git** (mit einem Testvault, damit der echte Vault seine Versionsverwaltung behält):

| Prüfung | Vorgehen | Erwartet | Ergebnis |
|---|---|---|---|
| Einrichtung ohne Git | Auf einem Rechner ohne Git (oder in einer Testumgebung, in der `git` nicht gefunden wird) den Installer bzw. `pkm setup --vault <TESTVAULT>` ausführen | Hinweis, dass Git fehlt und das PKM ohne Versionsverwaltung läuft; `config.toml` mit `PKM_VERSIONING = false`; kein Git-Verzeichnis; `pkm doctor` ohne Fehler mit dem Hinweis `versioning` | ☐ |
| Schreiben ohne Git | Im Chat ein Dokument anlegen und fortschreiben | `version: 1`, dann `version: 2`, jeweils `commit: null` | ☐ |
| Verlauf ohne Git | „Was hat sich geändert?“ bzw. „Mach das rückgängig“ | `not_versioned`; der Chat erklärt, dass es keinen Verlauf gibt und wie man ihn einschaltet | ☐ |
| Pflege ohne Git | Dokument in Obsidian ändern, Pflegelauf | `pending` meldet das Dokument als `changed`; Lint ohne Fehler; `finish_maintenance` ohne Commit | ☐ |
| Git nachrüsten | Git installieren, `pkm setup` erneut ausführen, danach ein Pflegelauf | `PKM_VERSIONING = true`, Repo mit Commit `pkm: init`; der Pflegelauf committet jedes Dokument mit seiner aktuellen Version (`first version by hand`); `history` funktioniert ab da | ☐ |

---

## Befunde

| # | Schritt | Beobachtung | Art (Code / Skill / Doku) | Erledigt in |
|---|---|---|---|---|
| 1 | | | | |

## Freigabe

☐ Alle Schritte ✅ oder Befunde behoben · Datum: · Name:
