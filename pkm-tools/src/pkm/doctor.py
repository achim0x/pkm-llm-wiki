"""``pkm doctor`` (Spezifikation 8): Umgebung prüfen.

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
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .cloudsync import cloud_service, conflict_copies, online_only_files
from .config import IMPORT_FOLDER
from .errors import PkmError
from .vaultinit import (
    PROPERTY_TYPES,
    TYPES_FILE,
    folder_ignored,
    property_type_conflicts,
    read_property_types,
    scratch_ignored,
)

if TYPE_CHECKING:
    from .service import Service

# Variables *******************************************************************

OBSIDIAN_EXPECTED = {
    "alwaysUpdateLinks": (True, "Interne Links automatisch aktualisieren: an"),
    "newLinkFormat": ("absolute", "Neues Link-Format: Absoluter Pfad im Vault"),
    "useMarkdownLinks": (False, "Wikilinks verwenden: an"),
    "attachmentFolderPath": ("documents/_attachments", "Anhang-Ordner: documents/_attachments"),
}

# Classes *********************************************************************

# Functions *******************************************************************


def _check(name: str, ok: bool, ok_message: str, bad_message: str, severity: str = "error") -> dict[str, Any]:
    """Prüfergebnis bilden.

    Args:
        name: Name der Prüfung.
        ok: Ergebnis.
        ok_message: Meldung bei Erfolg.
        bad_message: Meldung bei Fehlschlag.
        severity: Schweregrad bei Fehlschlag (``error`` oder ``warning``).

    Returns:
        ``check``, ``ok``, ``severity`` (``ok`` bei Erfolg) und ``message``.
    """
    return {"check": name, "ok": ok, "severity": "ok" if ok else severity, "message": ok_message if ok else bad_message}


def _git_checks(svc: Service) -> list[dict[str, Any]]:
    """Prüfungen rund um Git.

    Args:
        svc: Dienst.

    Returns:
        Prüfergebnisse.
    """
    cfg, git = svc.cfg, svc.git
    git_dir_problem = cfg.git_dir_problem()
    git_cloud = cloud_service(cfg.git_dir)
    repo = git.installed() and git.is_repo()
    checks = [
        _check("git_installed", git.installed(), "git gefunden.", "git nicht im PATH."),
        _check("git_dir_outside", git_dir_problem is None, "Git-Verzeichnis liegt außerhalb des Vaults.",
               git_dir_problem or ""),
        _check("git_dir_cloud", git_cloud is None, "Git-Verzeichnis liegt nicht in einem Cloud-Ordner.",
               f"Git-Verzeichnis {cfg.git_dir} liegt offenbar in einem Cloud-Ordner ({git_cloud}); "
               "Git-Dateien dürfen nicht synchronisiert werden."),
        _check("git_repo", repo, "Git-Repo erreichbar.", f"Kein Git-Repo unter {cfg.git_dir} (pkm init)."),
        _check("no_dotgit_in_vault", not (cfg.root / ".git").exists(), "Kein .git im Vault.",
               "Im Vault liegt ein .git (5.5)."),
    ]
    if repo:
        name, email = git.config_get("user.name"), git.config_get("user.email")
        signing = (git.config_get("commit.gpgsign") or "").lower() == "true"
        checks += [
            _check("git_identity", bool(name and email), f"Git-Identität: {name} <{email}>.",
                   "user.name/user.email fehlen."),
            _check("git_signing", not signing, "Commit-Signierung aus.",
                   "commit.gpgsign ist an: Commits schlagen fehl, wenn die Signatur in Claude Desktop nicht "
                   "verfügbar ist.", "warning"),
        ]
    return checks


def _conflicts(svc: Service) -> list[str]:
    """Konfliktkopien aller Cloud-Dienste im Vault (am Namen und als Kopie mit gleicher ID).

    Args:
        svc: Dienst.

    Returns:
        Sortierte Pfade.
    """
    rels = list(svc.vault.iter_files())
    ids: dict[str, str | None] = {}
    for rel in rels:
        if rel.startswith("documents/") and rel.lower().endswith(".md"):
            try:
                ids[rel] = svc.vault.load(rel).id
            except PkmError:
                ids[rel] = None
    return sorted(conflict_copies(rels, ids))


def _path_checks(svc: Service) -> list[dict[str, Any]]:
    """Prüfungen für Vault, Suchindex, Schreibrechte, Konfliktkopien und ``scratch/`` in ``.gitignore``.

    Args:
        svc: Dienst.

    Returns:
        Prüfergebnisse.
    """
    cfg = svc.cfg
    cache_problem = cfg.cache_dir_problem()
    cache_cloud = cloud_service(cfg.cache_dir)
    conflicts = _conflicts(svc)
    vault_cloud = cloud_service(cfg.root)
    online_only = online_only_files(cfg.root)
    checks = [
        _check("vault", cfg.root.is_dir(), f"Vault {cfg.root} vorhanden.", f"Vault fehlt: {cfg.root}"),
        _check("cache_dir_outside", cache_problem is None, "PKM_CACHE_DIR liegt außerhalb des Vaults.",
               cache_problem or ""),
        _check("cache_dir_cloud", cache_cloud is None, "PKM_CACHE_DIR liegt nicht in einem Cloud-Ordner.",
               f"PKM_CACHE_DIR {cfg.cache_dir} liegt offenbar in einem Cloud-Ordner ({cache_cloud}); "
               "SQLite darf nicht synchronisiert werden."),
        _check("vault_cloud", True, f"Vault liegt in: {vault_cloud or 'kein erkannter Cloud-Ordner'}.", ""),
        _check("vault_online_only", not online_only, "Alle Dateien des Vaults liegen lokal vor.",
               f"Dateien nur online (Platzhalter): {', '.join(online_only)}. Den Vault-Ordner im Cloud-Dienst "
               "immer lokal halten (OneDrive „Immer auf diesem Gerät behalten“, Google Drive „Spiegeln“, iCloud "
               "„Heruntergeladen behalten“, Nextcloud virtuelle Dateien aus).", "warning"),
    ]
    for label, path in (("vault_writable", cfg.root), ("cache_writable", cfg.cache_dir)):
        ok = path.is_dir() and os.access(path, os.W_OK)
        checks.append(_check(label, ok, f"{path} beschreibbar.", f"{path} fehlt oder ist nicht beschreibbar."))
    checks.append(_check("conflict_copies", not conflicts, "Keine Konfliktkopien des Cloud-Speichers.",
                         f"Konfliktkopien: {', '.join(conflicts)}"))
    import_problem = cfg.import_dir_problem()
    checks.append(_check("import_dir", import_problem is None, f"Importordner für Bilder: {cfg.images.import_dir}.",
                         import_problem or ""))
    gitignore = cfg.root / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    checks.append(_check("scratch_ignored", scratch_ignored(text), "scratch/ steht in .gitignore.",
                         "scratch/ fehlt in .gitignore (pkm init ergänzt es)."))
    if cfg.import_in_vault:
        checks.append(_check("import_ignored", folder_ignored(text, IMPORT_FOLDER),
                             f"{IMPORT_FOLDER}/ steht in .gitignore.",
                             f"{IMPORT_FOLDER}/ fehlt in .gitignore (pkm init ergänzt es)."))
    return checks


def _obsidian_checks(root: Path) -> list[dict[str, Any]]:
    """Obsidian-Einstellungen aus ``.obsidian/app.json`` prüfen (13).

    Args:
        root: Vault-Wurzel.

    Returns:
        Prüfergebnisse (Abweichungen als Warnung).
    """
    app = root / ".obsidian" / "app.json"
    data: dict[str, Any] | None = None
    if app.is_file():
        try:
            data = json.loads(app.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
    if not app.is_file():
        checks = [_check("obsidian_settings", True,
                         "Keine .obsidian/app.json gefunden (Obsidian-Einstellungen nicht geprüft).", "")]
    elif data is None:
        checks = [_check("obsidian_settings", False, "", ".obsidian/app.json nicht lesbar.", "warning")]
    else:
        checks = [
            _check(f"obsidian_{key}", data.get(key) == expected, f"{label}.",
                   f"Obsidian: {label} (aktuell {data.get(key)!r}).", "warning")
            for key, (expected, label) in OBSIDIAN_EXPECTED.items()
        ]
        ignored = any(str(f).strip("/") == ".pkm" for f in data.get("userIgnoreFilters") or [])
        checks.append(_check("obsidian_ignore_pkm", ignored, ".pkm/ ist in Obsidian ausgeschlossen.",
                             "Obsidian: .pkm/ unter „Ausgeschlossene Dateien“ eintragen.", "warning"))
    return checks


def _property_type_check(root: Path) -> dict[str, Any]:
    """Obsidian-Property-Typen aus ``.obsidian/types.json`` prüfen.

    Args:
        root: Vault-Wurzel.

    Returns:
        Prüfergebnis (fehlende oder abweichende Typen als Warnung).
    """
    data = read_property_types(root)
    if data is None:
        check = _check("obsidian_property_types", False, "", f"{TYPES_FILE} nicht lesbar.", "warning")
    else:
        types = data.get("types") or {}
        missing = [k for k in PROPERTY_TYPES if k not in types]
        conflicts = property_type_conflicts(types)
        problems = [f"{k} fehlt" for k in missing] + [
            f"{k}={v} (erwartet {PROPERTY_TYPES[k]})" for k, v in conflicts.items()]
        check = _check("obsidian_property_types", not problems, "Obsidian-Property-Typen passen zum Schema.",
                       "Obsidian-Property-Typen: " + ", ".join(problems)
                       + ". Fehlende ergänzt `pkm init` (Obsidian danach neu starten).", "warning")
    return check


def doctor(svc: Service, short: bool = False) -> dict[str, Any]:
    """``pkm doctor``: Umgebung prüfen.

    Args:
        svc: Dienst.
        short: Nur Fehler ausgeben.

    Returns:
        ``status`` (``error``, wenn es Fehler gibt), Anzahl Fehler und Warnungen und die Prüfungen.
    """
    checks = _path_checks(svc) + _git_checks(svc) + _obsidian_checks(svc.cfg.root)
    checks.append(_property_type_check(svc.cfg.root))
    errors = sum(1 for c in checks if c["severity"] == "error")
    warnings = sum(1 for c in checks if c["severity"] == "warning")
    shown = [c for c in checks if c["severity"] == "error"] if short else checks
    return {"status": "error" if errors else "ok", "errors": errors, "warnings": warnings, "checks": shown}

# Main ************************************************************************
