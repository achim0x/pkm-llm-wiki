# pkm-tools

MCP-Server `pkm-mcp` und CLI `pkm` für das PKM mit LLM-Wiki.
Grundlage: [Spezifikation](../docs/spezifikation.md), [Umsetzungsplan](../docs/umsetzungsplan.md).

## Entwicklung

```bash
cd pkm-tools
pip install -e ".[dev]"
pytest
ruff check .
```

Die Tests laufen auch unter Linux. Alle Pfade werden über Umgebungsvariablen gesetzt
(`PKM_ROOT`, `PKM_GIT_DIR`, `PKM_CACHE_DIR`, …), siehe Spezifikation 7.1.
