"""``pkm init``: Struktur anlegen und Git-Verzeichnis außerhalb des Vaults initialisieren.

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

import json
from importlib import resources
from pathlib import Path
from typing import Any

from .config import IMPORT_FOLDER, Config
from .errors import PkmError
from .fsutil import write_bytes_atomic
from .gitlayer import Git
from .state import FORMAT as STATE_FORMAT

# Variables *******************************************************************

DIRS = [
    "documents/_inbox",
    "documents/_attachments",
    "wiki/topics",
    "wiki/entities",
    "wiki/summaries",
    "wiki/syntheses",
    "wiki/_lint",
    "scratch",
    IMPORT_FOLDER,
    ".pkm",
]
SCRATCH_IGNORE = "scratch/"
IGNORED_FOLDERS = ("scratch", IMPORT_FOLDER)
TYPES_FILE = ".obsidian/types.json"
# Obsidian-Property-Typen (vault-weit je Feldname); Werte wie in Obsidians types.json.
PROPERTY_TYPES = {
    "title": "text",
    "short_citation": "text",
    "date_document": "text",
    "status_markdown": "text",
    "date_markdown": "datetime",
    "toolchain_markdown": "text",
    "id": "text",
    "version": "number",
    "date_updated": "datetime",
    "context": "text",
    "related": "multitext",
    "kind": "text",
    "type": "text",
    "sources": "multitext",
    "confidence": "text",
}

# Classes *********************************************************************

# Functions *******************************************************************


def _template(name: str) -> str:
    """Vorlage aus dem Paket lesen.

    Args:
        name: Dateiname unter ``pkm/templates``.

    Returns:
        Inhalt der Vorlage.
    """
    return resources.files("pkm").joinpath("templates", name).read_text(encoding="utf-8")


def initial_files() -> dict[str, str]:
    """Dateien, die ``pkm init`` anlegt.

    Returns:
        Relativer Pfad → Inhalt.
    """
    return {
        "CLAUDE.md": _template("CLAUDE.md"),
        ".gitignore": _template("gitignore"),
        "wiki/index.md": "# Wiki-Index\n\n_Noch keine Seiten._\n",
        "wiki/log.md": "# Pflege-Log\n",
        "wiki/_status.md": "# Status\n\n## Noch nicht verarbeitet (0)\n",
        ".pkm/state.json": json.dumps({"version": STATE_FORMAT, "documents": {}}, indent=2) + "\n",
    }


def _create_structure(cfg: Config) -> tuple[list[str], list[str]]:
    """Fehlende Ordner und Dateien anlegen; vorhandene bleiben unverändert.

    Args:
        cfg: Konfiguration.

    Returns:
        Tupel aus (angelegte Ordner, angelegte Dateien).
    """
    cfg.root.mkdir(parents=True, exist_ok=True)
    created_dirs = [d for d in DIRS if not (cfg.root / d).is_dir()]
    for d in created_dirs:
        (cfg.root / d).mkdir(parents=True)
    created_files = [rel for rel in initial_files() if not (cfg.root / rel).exists()]
    for rel in created_files:
        (cfg.root / rel).write_bytes(initial_files()[rel].encode("utf-8"))
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    return created_dirs, created_files


def ensure_scratch_ignored(cfg: Config) -> bool:
    """``scratch/`` und ``pkm_img_import/`` in eine bestehende ``.gitignore`` aufnehmen, falls sie fehlen.

    Args:
        cfg: Konfiguration.

    Returns:
        ``True``, wenn die Datei ergänzt wurde.
    """
    p = cfg.root / ".gitignore"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    missing = [f"{name}/" for name in IGNORED_FOLDERS if not folder_ignored(text, name)]
    if missing:
        new = text + ("" if not text or text.endswith("\n") else "\n") + "".join(f"{m}\n" for m in missing)
        p.write_bytes(new.encode("utf-8"))
    return bool(missing)


def folder_ignored(gitignore_text: str, name: str) -> bool:
    """Prüfen, ob eine ``.gitignore`` einen Ordner auf oberster Ebene ausschließt.

    Args:
        gitignore_text: Inhalt der ``.gitignore``.
        name: Ordnername ohne Schrägstrich.

    Returns:
        ``True`` bei einer Zeile ``name``, ``name/``, ``/name`` oder ``/name/``.
    """
    return any(line.strip().strip("/") == name for line in gitignore_text.splitlines())


def scratch_ignored(gitignore_text: str) -> bool:
    """Prüfen, ob eine ``.gitignore`` den Bereich ``scratch/`` ausschließt.

    Args:
        gitignore_text: Inhalt der ``.gitignore``.

    Returns:
        ``True``, wenn eine Zeile ``scratch/``, ``/scratch/``, ``scratch`` oder ``/scratch`` lautet.
    """
    return any(line.strip().strip("/") == "scratch" for line in gitignore_text.splitlines())


def read_property_types(root: Path) -> dict[str, Any] | None:
    """Obsidians ``.obsidian/types.json`` lesen.

    Args:
        root: Vault-Wurzel.

    Returns:
        Inhalt als Dictionary; ``{}``, wenn die Datei fehlt; ``None``, wenn sie nicht lesbar ist.
    """
    p = root / TYPES_FILE
    data: dict[str, Any] | None = {}
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict) or not isinstance(data.get("types", {}), dict):
            data = None
    return data


def property_type_conflicts(types: dict[str, Any]) -> dict[str, str]:
    """Felder, deren Typ in Obsidian vom PKM-Schema abweicht.

    Args:
        types: Abschnitt ``types`` aus ``.obsidian/types.json``.

    Returns:
        Feldname → eingestellter Typ (nur abweichende, vorhandene Einträge).
    """
    return {k: str(v) for k, v in types.items() if k in PROPERTY_TYPES and v != PROPERTY_TYPES[k]}


def ensure_property_types(root: Path) -> dict[str, Any]:
    """Fehlende Property-Typen in ``.obsidian/types.json`` ergänzen.

    Vorhandene Einträge (auch abweichende) bleiben unverändert; Abweichungen werden gemeldet.
    Ist Obsidian geöffnet, liest es die Datei erst nach einem Neustart.

    Args:
        root: Vault-Wurzel.

    Returns:
        ``created`` (Datei neu), ``added`` (ergänzte Felder), ``conflicts`` (abweichende Typen)
        und ``warning`` (Text oder ``None``).
    """
    existed = (root / TYPES_FILE).is_file()
    data = read_property_types(root)
    result: dict[str, Any] = {"created": False, "added": [], "conflicts": {}, "warning": None}
    if data is None:
        result["warning"] = f"{TYPES_FILE} nicht lesbar; Property-Typen nicht ergänzt."
    else:
        types = dict(data.get("types") or {})
        added = [k for k in PROPERTY_TYPES if k not in types]
        conflicts = property_type_conflicts(types)
        if added:
            types.update({k: PROPERTY_TYPES[k] for k in added})
            data["types"] = types
            write_bytes_atomic(root / TYPES_FILE, (json.dumps(data, indent=2) + "\n").encode("utf-8"))
        if conflicts:
            result["warning"] = "Obsidian-Property-Typen weichen ab: " + ", ".join(
                f"{k}={v} (erwartet {PROPERTY_TYPES[k]})" for k, v in conflicts.items())
        result.update(created=bool(added) and not existed, added=added, conflicts=conflicts)
    return result


def init_vault(cfg: Config) -> dict[str, Any]:
    """``pkm init`` (idempotent).

    Args:
        cfg: Konfiguration.

    Returns:
        Was angelegt bzw. ergänzt wurde, ob das Repo neu ist, der Initial-Commit und Warnungen.

    Raises:
        PkmError: ``config_error``, wenn Git-Verzeichnis oder Suchindex im Vault liegen würden
            oder im Vault schon ein ``.git`` liegt.
    """
    for problem in (cfg.git_dir_problem(), cfg.cache_dir_problem()):
        if problem:
            raise PkmError("config_error", problem)
    if (cfg.root / ".git").exists():
        raise PkmError("config_error", "Im Vault liegt ein `.git`. Git muss außerhalb liegen (5.5).")
    created_dirs, created_files = _create_structure(cfg)
    updated_files = [".gitignore"] if ".gitignore" not in created_files and ensure_scratch_ignored(cfg) else []
    types = ensure_property_types(cfg.root)
    if types["created"]:
        created_files.append(TYPES_FILE)
    elif types["added"]:
        updated_files.append(TYPES_FILE)
    git = Git(cfg.git_dir, cfg.root)
    repo_created = git.init()
    git.run("config", "core.autocrlf", "false")  # Git für Windows: Zeilenenden nie umwandeln
    commit = None
    warnings: list[str] = [types["warning"]] if types["warning"] else []
    if not git.has_head():
        if git.config_get("user.name") and git.config_get("user.email"):
            paths = [rel for rel in [*initial_files(), TYPES_FILE] if (cfg.root / rel).exists()]
            commit = git.commit_paths(paths, "pkm: init\n")
        else:
            warnings.append("Git-Identität fehlt (user.name/user.email); Initial-Commit übersprungen.")
    return {
        "status": "ok",
        "root": str(cfg.root),
        "git_dir": str(cfg.git_dir),
        "created_dirs": created_dirs,
        "created_files": created_files,
        "updated_files": updated_files,
        "repo_created": repo_created,
        "commit": commit,
        "warnings": warnings,
    }

# Main ************************************************************************
