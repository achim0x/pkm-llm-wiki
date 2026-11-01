"""Konfiguration über Umgebungsvariablen (Spezifikation 7.1)."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from .errors import PkmError

DEFAULT_AUTHOR = "pkm-mcp <pkm@localhost>"


def default_app_dir(home: Path | None = None) -> Path:
    """Standardordner für Git-Verzeichnis und Suchindex, abhängig vom Betriebssystem."""
    home = home or Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "pkm"
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        return Path(base) / "pkm" if base else home / "AppData" / "Roaming" / "pkm"
    base = os.environ.get("XDG_DATA_HOME")
    return Path(base) / "pkm" if base else home / ".local" / "share" / "pkm"


def find_vault(start: Path) -> Path | None:
    """Ersten Ordner ab `start` aufwärts, der `.pkm/state.json` enthält."""
    start = start.resolve()
    for p in [start, *start.parents]:
        if (p / ".pkm" / "state.json").is_file():
            return p
    return None


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class Config:
    root: Path
    git_dir: Path
    cache_dir: Path
    tz: ZoneInfo
    max_kb: int = 200
    vault_name: str | None = None
    git_author: str = DEFAULT_AUTHOR

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, search_from: Path | None = None) -> Config:
        """Konfiguration aus der Umgebung.

        Fehlt PKM_ROOT und ist `search_from` gesetzt (CLI), wird der Vault vom Ordner aus
        aufwärts gesucht: Er ist der erste Ordner, der `.pkm/state.json` enthält.
        """
        env = os.environ if env is None else env
        root_s = env.get("PKM_ROOT")
        if not root_s and search_from is not None:
            found = find_vault(search_from)
            root_s = str(found) if found else None
        if not root_s:
            raise PkmError(
                "config_error",
                "PKM_ROOT ist nicht gesetzt (absoluter Pfad zum Vault) und im aktuellen Ordner "
                "bzw. darüber liegt kein Vault mit .pkm/state.json.",
            )
        root = Path(root_s).expanduser()
        if not root.is_absolute():
            raise PkmError("config_error", f"PKM_ROOT muss ein absoluter Pfad sein: {root_s}")
        home = Path(env["HOME"]) if env.get("HOME") else None
        app = default_app_dir(home)
        git_dir = Path(env.get("PKM_GIT_DIR") or app / "git").expanduser()
        cache_dir = Path(env.get("PKM_CACHE_DIR") or app).expanduser()
        try:
            tz = ZoneInfo(env.get("PKM_TZ") or "Europe/Berlin")
        except Exception as exc:  # noqa: BLE001
            raise PkmError("config_error", f"Ungültige Zeitzone PKM_TZ: {exc}") from exc
        try:
            max_kb = int(env.get("PKM_MAX_KB") or 200)
        except ValueError as exc:
            raise PkmError("config_error", "PKM_MAX_KB muss eine ganze Zahl sein.") from exc
        return cls(
            root=root.resolve(),
            git_dir=git_dir.resolve(),
            cache_dir=cache_dir.resolve(),
            tz=tz,
            max_kb=max_kb,
            vault_name=env.get("PKM_VAULT_NAME") or None,
            git_author=env.get("PKM_GIT_AUTHOR") or DEFAULT_AUTHOR,
        )

    # --- abgeleitete Pfade ---
    @property
    def index_path(self) -> Path:
        return self.cache_dir / "index.db"

    @property
    def log_path(self) -> Path:
        return self.root / ".pkm" / "mcp.log"

    @property
    def state_path(self) -> Path:
        return self.root / ".pkm" / "state.json"

    @property
    def max_bytes(self) -> int:
        return self.max_kb * 1024

    # --- Prüfungen (5.5, 7.1) ---
    def cache_dir_problem(self) -> str | None:
        """Fehlertext, wenn PKM_CACHE_DIR im Vault liegt (SQLite darf nicht synchronisiert werden)."""
        if _is_within(self.cache_dir, self.root):
            return (
                f"PKM_CACHE_DIR ({self.cache_dir}) liegt im Vault. Der Suchindex darf nicht im "
                "Nextcloud-Ordner liegen; bitte einen Ordner außerhalb wählen."
            )
        return None

    def git_dir_problem(self) -> str | None:
        if _is_within(self.git_dir, self.root):
            return (
                f"PKM_GIT_DIR ({self.git_dir}) liegt im Vault. Das Git-Verzeichnis muss außerhalb "
                "des Nextcloud-Ordners liegen (5.5)."
            )
        return None
