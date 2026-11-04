"""Konfiguration über Umgebungsvariablen (Spezifikation 7.1).

    Author: Achim0x
"""

# *****************************************************************************
# Copyright (c) Achim0x - https://github.com/achim0x/
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# *****************************************************************************

# Imports *********************************************************************

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import PkmError

# Variables *******************************************************************

DEFAULT_AUTHOR = "pkm-mcp <pkm@localhost>"
DEFAULT_MAX_KB = 200
DEFAULT_TZ = "Europe/Berlin"
IMPORT_FOLDER = "pkm_img_import"
IMAGE_DEFAULTS = {"PKM_INLINE_MAX_KB": 24, "PKM_SVG_MAX_KB": 200, "PKM_IMAGE_MAX_MB": 5,
                  "PKM_IMAGE_PARAM_MAX_KB": 512}

# Classes *********************************************************************


@dataclass(frozen=True)
class ImageConfig:
    """Grenzen und Ordner für Bilder (Spezifikation 4.9, 7.1).

    Attributes:
        inline_max_kb: Grenze für eingebettete Bilder, kodierte Größe (``PKM_INLINE_MAX_KB``).
        svg_max_kb: Komplexitätsgrenze für SVG nach der Bereinigung (``PKM_SVG_MAX_KB``).
        image_max_mb: Obergrenze je Bild (``PKM_IMAGE_MAX_MB``).
        param_max_kb: Obergrenze für ``png_base64`` in einem Aufruf (``PKM_IMAGE_PARAM_MAX_KB``).
        import_dir: Einziger Ordner, aus dem Bilddateien übernommen werden (``PKM_IMPORT_DIR``).
        svg_raster: SVG für ``read_image`` rastern (``PKM_SVG_RASTER``).
    """

    inline_max_kb: int = 24
    svg_max_kb: int = 200
    image_max_mb: int = 5
    param_max_kb: int = 512
    import_dir: Path | None = None
    svg_raster: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str], root: Path) -> ImageConfig:
        """Bild-Einstellungen aus der Umgebung lesen.

        Args:
            env: Umgebungsvariablen.
            root: Vault-Wurzel (Standard-Importordner ``<Vault>/pkm_img_import``).

        Returns:
            Die Einstellungen.

        Raises:
            PkmError: ``config_error`` bei ungültigen Zahlen.
        """
        values: dict[str, int] = {}
        for key, default in IMAGE_DEFAULTS.items():
            try:
                values[key] = int(env.get(key) or default)
            except ValueError as exc:
                raise PkmError("config_error", f"{key} muss eine ganze Zahl sein.") from exc
        import_dir = Path(env.get("PKM_IMPORT_DIR") or root / IMPORT_FOLDER)
        return cls(
            inline_max_kb=values["PKM_INLINE_MAX_KB"],
            svg_max_kb=values["PKM_SVG_MAX_KB"],
            image_max_mb=values["PKM_IMAGE_MAX_MB"],
            param_max_kb=values["PKM_IMAGE_PARAM_MAX_KB"],
            import_dir=import_dir.expanduser().resolve(),
            svg_raster=(env.get("PKM_SVG_RASTER") or "").strip().lower() in ("1", "true", "yes", "ja"),
        )


@dataclass(frozen=True)
class Config:  # pylint: disable=too-many-instance-attributes
    """Laufzeitkonfiguration von Server und CLI.

    Attributes:
        root: Absoluter Pfad zum Vault (``PKM_ROOT``).
        git_dir: Git-Verzeichnis außerhalb des Vaults (``PKM_GIT_DIR``).
        cache_dir: Ordner für den Suchindex (``PKM_CACHE_DIR``).
        tz: Zeitzone für Zeitstempel und IDs (``PKM_TZ``).
        max_kb: Größengrenze für Dokumente und Änderungstexte (``PKM_MAX_KB``).
        vault_name: Name des Obsidian-Vaults für ``obsidian://``-Links (``PKM_VAULT_NAME``).
        git_author: Autor der MCP-Commits (``PKM_GIT_AUTHOR``).
        images: Einstellungen für Bilder (4.9).
    """

    root: Path
    git_dir: Path
    cache_dir: Path
    tz: ZoneInfo
    max_kb: int = DEFAULT_MAX_KB
    vault_name: str | None = None
    git_author: str = DEFAULT_AUTHOR
    images: ImageConfig = field(default_factory=ImageConfig)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, search_from: Path | None = None) -> Config:
        """Konfiguration aus der Umgebung lesen.

        Fehlt ``PKM_ROOT`` und ist ``search_from`` gesetzt (CLI), wird der Vault vom Ordner aus
        aufwärts gesucht: Er ist der erste Ordner, der ``.pkm/state.json`` enthält.

        Args:
            env: Umgebungsvariablen; ohne Angabe ``os.environ``.
            search_from: Startordner für die Vault-Suche, wenn ``PKM_ROOT`` fehlt.

        Returns:
            Die fertige Konfiguration mit aufgelösten Pfaden.

        Raises:
            PkmError: ``config_error`` bei fehlenden oder ungültigen Angaben.
        """
        env = os.environ if env is None else env
        root = _root_from_env(env, search_from)
        home = Path(env["HOME"]) if env.get("HOME") else None
        app = default_app_dir(home)
        git_dir = Path(env.get("PKM_GIT_DIR") or app / "git").expanduser()
        cache_dir = Path(env.get("PKM_CACHE_DIR") or app).expanduser()
        try:
            tz = ZoneInfo(env.get("PKM_TZ") or DEFAULT_TZ)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise PkmError("config_error", f"Ungültige Zeitzone PKM_TZ: {exc}") from exc
        try:
            max_kb = int(env.get("PKM_MAX_KB") or DEFAULT_MAX_KB)
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
            images=ImageConfig.from_env(env, root.resolve()),
        )

    # Abgeleitete Pfade ********************************************************

    @property
    def index_path(self) -> Path:
        """Pfad der SQLite-Datei des Suchindex.

        Returns:
            ``PKM_CACHE_DIR/index.db``.
        """
        return self.cache_dir / "index.db"

    @property
    def log_path(self) -> Path:
        """Pfad des MCP-Protokolls.

        Returns:
            ``<Vault>/.pkm/mcp.log``.
        """
        return self.root / ".pkm" / "mcp.log"

    @property
    def state_path(self) -> Path:
        """Pfad des Verarbeitungsstands.

        Returns:
            ``<Vault>/.pkm/state.json``.
        """
        return self.root / ".pkm" / "state.json"

    @property
    def max_bytes(self) -> int:
        """Größengrenze in Bytes.

        Returns:
            ``max_kb`` mal 1024.
        """
        return self.max_kb * 1024

    # Prüfungen (5.5, 7.1) *****************************************************

    def cache_dir_problem(self) -> str | None:
        """Prüfen, ob der Suchindex im Vault liegen würde.

        Returns:
            Fehlertext, wenn ``PKM_CACHE_DIR`` im Vault liegt, sonst ``None``.
        """
        problem = None
        if _is_within(self.cache_dir, self.root):
            problem = (
                f"PKM_CACHE_DIR ({self.cache_dir}) liegt im Vault. Der Suchindex darf nicht im "
                "Cloud-Ordner (Nextcloud, OneDrive, Google Drive …) liegen; bitte einen Ordner außerhalb wählen."
            )
        return problem

    @property
    def import_in_vault(self) -> bool:
        """Ob der Importordner der Standardordner ``<Vault>/pkm_img_import`` ist.

        Returns:
            ``True`` beim Ordner im Vault.
        """
        return self.images.import_dir == self.root / IMPORT_FOLDER

    def import_dir_problem(self) -> str | None:
        """Prüfen, ob der Importordner für Bilder zulässig ist (4.9).

        Zulässig sind ``<Vault>/pkm_img_import`` und Ordner außerhalb des Vaults.

        Returns:
            Fehlertext bei einem anderen Ordner im Vault, sonst ``None``.
        """
        problem = None
        imp = self.images.import_dir
        if imp is not None and _is_within(imp, self.root) and not self.import_in_vault:
            problem = (f"PKM_IMPORT_DIR ({imp}) liegt im Vault, aber nicht in {IMPORT_FOLDER}/; im Vault ist nur "
                       f"{IMPORT_FOLDER}/ erlaubt (4.9).")
        return problem

    def git_dir_problem(self) -> str | None:
        """Prüfen, ob das Git-Verzeichnis im Vault liegen würde.

        Returns:
            Fehlertext, wenn ``PKM_GIT_DIR`` im Vault liegt, sonst ``None``.
        """
        problem = None
        if _is_within(self.git_dir, self.root):
            problem = (
                f"PKM_GIT_DIR ({self.git_dir}) liegt im Vault. Das Git-Verzeichnis muss außerhalb "
                "des Cloud-Ordners liegen (5.5)."
            )
        return problem

# Functions *******************************************************************


def default_app_dir(home: Path | None = None) -> Path:
    """Standardordner für Git-Verzeichnis und Suchindex, abhängig vom Betriebssystem.

    Args:
        home: Home-Verzeichnis; ohne Angabe ``Path.home()``.

    Returns:
        macOS: ``~/Library/Application Support/pkm``; Windows: ``%APPDATA%/pkm``;
        sonst ``$XDG_DATA_HOME/pkm`` bzw. ``~/.local/share/pkm``.
    """
    home = home or Path.home()
    if sys.platform == "darwin":
        app = home / "Library" / "Application Support" / "pkm"
    elif sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        app = Path(base) / "pkm" if base else home / "AppData" / "Roaming" / "pkm"
    else:
        base = os.environ.get("XDG_DATA_HOME")
        app = Path(base) / "pkm" if base else home / ".local" / "share" / "pkm"
    return app


def find_vault(start: Path) -> Path | None:
    """Vault ab einem Ordner aufwärts suchen.

    Args:
        start: Ordner, in dem die Suche beginnt.

    Returns:
        Den ersten Ordner, der ``.pkm/state.json`` enthält, sonst ``None``.
    """
    start = start.resolve()
    return next((p for p in [start, *start.parents] if (p / ".pkm" / "state.json").is_file()), None)


def _root_from_env(env: Mapping[str, str], search_from: Path | None) -> Path:
    """Vault-Pfad aus ``PKM_ROOT`` oder per Suche bestimmen.

    Args:
        env: Umgebungsvariablen.
        search_from: Startordner für die Suche, wenn ``PKM_ROOT`` fehlt.

    Returns:
        Absoluter, noch nicht aufgelöster Vault-Pfad.

    Raises:
        PkmError: ``config_error``, wenn kein gültiger Vault-Pfad vorliegt.
    """
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
    return root


def _is_within(child: Path, parent: Path) -> bool:
    """Prüfen, ob ein Pfad innerhalb eines anderen liegt.

    Args:
        child: Zu prüfender Pfad.
        parent: Möglicher übergeordneter Pfad.

    Returns:
        ``True``, wenn ``child`` gleich ``parent`` ist oder darunter liegt.
    """
    return child == parent or parent in child.parents

# Main ************************************************************************
