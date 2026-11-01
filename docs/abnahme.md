# PKM mit LLM-Wiki – Abnahmeprotokoll

**Bezug:** Spezifikation 0.18, Abschnitt 14 („Abnahme (manuell)“) · Umsetzungsplan Phase 7

Die Abnahme läuft auf dem **Mac** mit echtem Nextcloud-Vault, Claude Desktop und Obsidian sowie
für Schritt 9 auf dem **Windows-Rechner**. Voraussetzung ist die Einrichtung nach
[einrichtung.md](einrichtung.md) (Abschnitte 1–9).

Ergebnis je Schritt eintragen: ✅ erfüllt · ⚠️ erfüllt mit Befund · ❌ nicht erfüllt.
Befunde unten unter „Befunde“ sammeln; sie werden danach behoben (Code oder Skill-Formulierung).

| Feld | Eintrag |
|---|---|
| Datum | |
| Mac / macOS-Version | |
| Claude Desktop Version | |
| Obsidian Version (Mac / Windows) | |
| Commit von `pkm-tools` | `git -C <REPO> rev-parse --short HEAD` |

---

## 0. Vorbereitung

Im Terminal auf dem Mac (für die Prüfbefehle):

```bash
export PKM_ROOT="$HOME/Nextcloud/<VAULT>"
```

```bash
alias pkmgit='git --git-dir="$HOME/Library/Application Support/pkm/git" --work-tree="$PKM_ROOT"'
```

```bash
pkm doctor
```

Erwartet: `"status": "ok"`. Warnungen (z. B. Obsidian-Einstellungen) vor dem Start beheben.

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
- [ ] Danach nennt er ID, Pfad und `version: 1`.
- [ ] Datei liegt in `documents/_inbox/YYYY-MM-DD_<slug>.md` mit `id` und `version: 1`.
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
- [ ] Der Agent ruft nacheinander `pkm doctor --short`, `pkm versions`, `pkm ids`,
      `pkm pending` auf.
- [ ] `wiki/summaries/<name>.md` mit Kurzfassung und Belegen (`v:1`).
- [ ] Mindestens eine Themen- oder Entitätsseite mit Belegen und „Siehe auch“.
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
- [ ] Das Dokument enthält **keinen** Abschnitt „Fortsetzung …“; „Entscheidungen“ zeigt nur
      noch den Schwimmerschalter, „Offene Punkte“ nicht mehr den Montageort.

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
- [ ] Der Agent liest den Diff (`pkm history … --diff 1`) und verarbeitet nur diese Abschnitte.
- [ ] Das Wiki zeigt den Schwimmerschalter mit Beleg auf `v:2`.
- [ ] Zusätzlich steht „Bis Version 1: … Ultraschallsensor …“ mit Beleg auf `v:1`.
- [ ] Belege auf unveränderte Abschnitte (z. B. Dachfläche) sind auf `v:2` angehoben.
- [ ] `wiki/log.md` vermerkt „überholt: … (v1 → v2)“; Agenten-Commit.

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 7 – Quellen

**Eingabe** (normaler Chat): „Was weiß mein Wiki über den Überlaufsensor?“ und danach „Woher
stammt die Angabe zur Dachfläche?“

**Erwartet**
- [ ] Antwort mit Verweis auf die Wiki-Seiten.
- [ ] Auf die Quellenfrage: `show_citations` mit der Aussage; Original (aktueller Pfad),
      Abschnitt „Dach“ bzw. der passende Abschnitt, Zitat, belegte und aktuelle Version,
      Status `ok`, ggf. `obsidian://`-Link (öffnet das Dokument in Obsidian).

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 8 – Fortsetzung als datierter Abschnitt

**Eingabe** (normaler Chat): „Dokumentiere das als Fortsetzung: Der Schwimmerschalter wird mit
5 m Kabel bestellt.“

**Erwartet**
- [ ] Erst jetzt entsteht per `append_to_document` ein Abschnitt `## Fortsetzung YYYY-MM-DD`
      (Kontext, Ergebnis, Entscheidungen, Offene Punkte), nach Entwurf und Bestätigung.
- [ ] Revidierte Entscheidungen im Original werden ggf. per `edit_document` mit
      „— *überholt am …, siehe [[#Fortsetzung …]]*“ markiert.
- [ ] Neue Version mit Commit.

**Ergebnis:** ☐  **Notiz:**

---

## Schritt 9 – Änderung auf dem Windows-Rechner

**Aktion:** Auf dem Windows-Rechner in Obsidian im Dokument einen offenen Punkt ergänzen, Sync
abwarten (Nextcloud-Symbol grün auf beiden Rechnern). Dann im Pflegeprojekt „Verarbeite neue
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

## Schritt 11 – Doctor und Lint

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
| Rückgängig | „Mach die letzte Änderung rückgängig“ | `restore_document` nach Bestätigung, neue Version, Notiz „wiederhergestellt aus v…“ | ☐ |
| Konfliktkopie | Nextcloud-Konfliktkopie erzeugen (gleichzeitige Änderung) | `pkm doctor --short` meldet sie, Pflegelauf bricht ab | ☐ |
| Kein `.git` im Vault | `ls -a "$PKM_ROOT"` | kein `.git` | ☐ |
| Umgewandelte Norm | Norm mit unquotiertem `: ` im Titel und `short citation` nach `documents/` legen, `pkm lint`, dann `pkm fix-frontmatter` (erst ohne, dann mit Ziel) | Lint: `invalid_frontmatter` mit Hinweis; ohne Ziel nur Liste; mit Ziel nur Titelzeile und Feldname geändert. Nächster Pflegelauf hängt nur `id`/`version` an | ☐ |
| Kurzbezeichnung | Im Chat „Was steht in EN 61000-4-6:2014 zum Anwendungsbereich?“ | Das Dokument wird über `short_citation` gefunden | ☐ |
| Obsidian-Typen | Eigenschaften eines neuen Chat-Dokuments in Obsidian ansehen | `date_markdown`/`date_updated` als Datum & Uhrzeit, `tags` als Tags | ☐ |

---

## Befunde

| # | Schritt | Beobachtung | Art (Code / Skill / Doku) | Erledigt in |
|---|---|---|---|---|
| 1 | | | | |

## Freigabe

☐ Alle Schritte ✅ oder Befunde behoben · Datum: · Name:
