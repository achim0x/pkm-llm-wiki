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

from .paths import is_conflict_copy

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


def looks_like_nextcloud(path: Path) -> bool:
    """Prüfen, ob ein Pfad in einem Nextcloud-Ordner liegt.

    Args:
        path: Zu prüfender Pfad.

    Returns:
        ``True``, wenn ein Ordnername „nextcloud“ enthält oder ein übergeordneter Ordner
        Nextcloud-Sync-Dateien (``.owncloudsync.log``, ``.sync_*.db``) enthält.
    """
    found = False
    for p in [path, *path.parents]:
        try:
            found = (
                "nextcloud" in p.name.casefold()
                or (p / ".owncloudsync.log").exists()
                or any(p.glob(".sync_*.db"))
            )
        except OSError:
            found = False
        if found:
            break
    return found


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
    in_nextcloud = looks_like_nextcloud(cfg.git_dir)
    repo = git.installed() and git.is_repo()
    checks = [
        _check("git_installed", git.installed(), "git gefunden.", "git nicht im PATH."),
        _check("git_dir_outside", git_dir_problem is None, "Git-Verzeichnis liegt außerhalb des Vaults.",
               git_dir_problem or ""),
        _check("git_dir_nextcloud", not in_nextcloud, "Git-Verzeichnis liegt nicht in einem Nextcloud-Ordner.",
               f"Git-Verzeichnis {cfg.git_dir} liegt offenbar in einem Nextcloud-Ordner."),
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


def _path_checks(svc: Service) -> list[dict[str, Any]]:
    """Prüfungen für Vault, Suchindex, Schreibrechte und Konfliktkopien.

    Args:
        svc: Dienst.

    Returns:
        Prüfergebnisse.
    """
    cfg = svc.cfg
    cache_problem = cfg.cache_dir_problem()
    in_nextcloud = looks_like_nextcloud(cfg.cache_dir)
    conflicts = [rel for rel in svc.vault.iter_files() if is_conflict_copy(Path(rel).name)]
    checks = [
        _check("vault", cfg.root.is_dir(), f"Vault {cfg.root} vorhanden.", f"Vault fehlt: {cfg.root}"),
        _check("cache_dir_outside", cache_problem is None, "PKM_CACHE_DIR liegt außerhalb des Vaults.",
               cache_problem or ""),
        _check("cache_dir_nextcloud", not in_nextcloud, "PKM_CACHE_DIR liegt nicht in einem Nextcloud-Ordner.",
               f"PKM_CACHE_DIR {cfg.cache_dir} liegt offenbar in einem Nextcloud-Ordner "
               "(SQLite darf nicht synchronisiert werden)."),
    ]
    for label, path in (("vault_writable", cfg.root), ("cache_writable", cfg.cache_dir)):
        ok = path.is_dir() and os.access(path, os.W_OK)
        checks.append(_check(label, ok, f"{path} beschreibbar.", f"{path} fehlt oder ist nicht beschreibbar."))
    checks.append(_check("conflict_copies", not conflicts, "Keine Nextcloud-Konfliktkopien.",
                         f"Konfliktkopien: {', '.join(conflicts)}"))
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


def doctor(svc: Service, short: bool = False) -> dict[str, Any]:
    """``pkm doctor``: Umgebung prüfen.

    Args:
        svc: Dienst.
        short: Nur Fehler ausgeben.

    Returns:
        ``status`` (``error``, wenn es Fehler gibt), Anzahl Fehler und Warnungen und die Prüfungen.
    """
    checks = _path_checks(svc) + _git_checks(svc) + _obsidian_checks(svc.cfg.root)
    errors = sum(1 for c in checks if c["severity"] == "error")
    warnings = sum(1 for c in checks if c["severity"] == "warning")
    shown = [c for c in checks if c["severity"] == "error"] if short else checks
    return {"status": "error" if errors else "ok", "errors": errors, "warnings": warnings, "checks": shown}

# Main ************************************************************************
