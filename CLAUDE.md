# Arbeitsregeln für dieses Repository

- Spezifikation: `docs/spezifikation.md`, Umsetzungsplan: `docs/umsetzungsplan.md`.
- Code liegt in `pkm-tools/`. Alle Python-Befehle laufen in `pkm-tools/.venv`. Vor jedem Commit dort
  `ruff check .`, `pylint --rcfile=.pylintrc src tests` (ohne Meldungen) und `pytest -q` ausführen.
- Python-Code folgt dem Coding-Standard in `pkm-tools/README.md` (Lizenzkopf, Abschnitte,
  Docstrings mit Args/Returns, ein `return` je Funktion, pylint sauber).
- **Nach jedem Push den CI-Lauf (GitHub Actions, Workflow `pkm-tools`) prüfen und erst
  weiterarbeiten, wenn er grün ist.** Schlägt er fehl: Logs lesen, Ursache beheben, erneut prüfen.
  Der Workflow läuft nur bei Änderungen unter `pkm-tools/` oder an der Workflow-Datei.
- **Dokumentation zweisprachig pflegen:** `README.md` enthält zuerst die englische, dann die
  deutsche Fassung – beide Hälften werden bei jeder Änderung gemeinsam angepasst.
  `docs/installation.md` (englisch) und `docs/einrichtung.md` (deutsch) sind inhaltlich gleich
  (gleiche Kapitelnummern) und werden immer zusammen aktualisiert. Gibt es ein Dokument in beiden
  Sprachen, nie nur eine Fassung ändern.
- Mindestens ein Commit je Umsetzungsphase.
- Tests müssen auf Linux und macOS laufen (macOS-Dateisystem unterscheidet Groß-/Kleinschreibung nicht).
