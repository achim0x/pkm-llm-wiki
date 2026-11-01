# Arbeitsregeln für dieses Repository

- Spezifikation: `docs/spezifikation.md`, Umsetzungsplan: `docs/umsetzungsplan.md`.
- Code liegt in `pkm-tools/`. Vor jedem Commit dort `ruff check .` und `pytest -q` ausführen.
- **Nach jedem Push den CI-Lauf (GitHub Actions, Workflow `pkm-tools`) prüfen und erst
  weiterarbeiten, wenn er grün ist.** Schlägt er fehl: Logs lesen, Ursache beheben, erneut prüfen.
  Der Workflow läuft nur bei Änderungen unter `pkm-tools/` oder an der Workflow-Datei.
- Mindestens ein Commit je Umsetzungsphase.
- Tests müssen auf Linux und macOS laufen (macOS-Dateisystem unterscheidet Groß-/Kleinschreibung nicht).
