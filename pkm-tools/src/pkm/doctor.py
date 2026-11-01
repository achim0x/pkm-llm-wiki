"""`pkm doctor` (Spezifikation 8): Umgebung prüfen."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .paths import is_conflict_copy

if TYPE_CHECKING:
    from .service import Service

OBSIDIAN_EXPECTED = {
    "alwaysUpdateLinks": (True, "Interne Links automatisch aktualisieren: an"),
    "newLinkFormat": ("absolute", "Neues Link-Format: Absoluter Pfad im Vault"),
    "useMarkdownLinks": (False, "Wikilinks verwenden: an"),
    "attachmentFolderPath": ("documents/_attachments", "Anhang-Ordner: documents/_attachments"),
}


def looks_like_nextcloud(path: Path) -> bool:
    for p in [path, *path.parents]:
        if "nextcloud" in p.name.casefold():
            return True
        try:
            if (p / ".owncloudsync.log").exists() or any(p.glob(".sync_*.db")):
                return True
        except OSError:
            continue
    return False


def doctor(svc: Service, short: bool = False) -> dict[str, Any]:
    cfg = svc.cfg
    git = svc.git
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, message: str, severity: str = "error") -> None:
        checks.append({"check": name, "ok": ok, "severity": "ok" if ok else severity, "message": message})

    add("vault", cfg.root.is_dir(), f"Vault {cfg.root} vorhanden." if cfg.root.is_dir() else f"Vault fehlt: {cfg.root}")
    add("git_installed", git.installed(), "git gefunden." if git.installed() else "git nicht im PATH.")
    gd = cfg.git_dir_problem()
    add("git_dir_outside", gd is None, gd or "Git-Verzeichnis liegt außerhalb des Vaults.")
    add("git_dir_nextcloud", not looks_like_nextcloud(cfg.git_dir),
        "Git-Verzeichnis liegt nicht in einem Nextcloud-Ordner." if not looks_like_nextcloud(cfg.git_dir)
        else f"Git-Verzeichnis {cfg.git_dir} liegt offenbar in einem Nextcloud-Ordner.")
    repo = git.installed() and git.is_repo()
    add("git_repo", repo, "Git-Repo erreichbar." if repo else f"Kein Git-Repo unter {cfg.git_dir} (pkm init).")
    dotgit = (cfg.root / ".git").exists()
    add("no_dotgit_in_vault", not dotgit, "Kein .git im Vault." if not dotgit else "Im Vault liegt ein .git (5.5).")
    if repo:
        name, email = git.config_get("user.name"), git.config_get("user.email")
        add("git_identity", bool(name and email),
            f"Git-Identität: {name} <{email}>." if name and email else "user.name/user.email fehlen.")
        signing = (git.config_get("commit.gpgsign") or "").lower() == "true"
        add("git_signing", not signing,
            "Commit-Signierung aus." if not signing else
            "commit.gpgsign ist an: Commits schlagen fehl, wenn die Signatur in Claude Desktop nicht verfügbar ist.",
            "warning")
    cd = cfg.cache_dir_problem()
    add("cache_dir_outside", cd is None, cd or "PKM_CACHE_DIR liegt außerhalb des Vaults.")
    nc = looks_like_nextcloud(cfg.cache_dir)
    add("cache_dir_nextcloud", not nc, "PKM_CACHE_DIR liegt nicht in einem Nextcloud-Ordner." if not nc
        else f"PKM_CACHE_DIR {cfg.cache_dir} liegt offenbar in einem Nextcloud-Ordner (SQLite darf nicht synchronisiert werden).")
    for label, path in (("vault_writable", cfg.root), ("cache_writable", cfg.cache_dir)):
        ok = path.is_dir() and os.access(path, os.W_OK)
        add(label, ok, f"{path} beschreibbar." if ok else f"{path} fehlt oder ist nicht beschreibbar.")
    conflicts = [rel for rel in svc.vault.iter_files() if is_conflict_copy(Path(rel).name)]
    add("conflict_copies", not conflicts,
        "Keine Nextcloud-Konfliktkopien." if not conflicts else f"Konfliktkopien: {', '.join(conflicts)}")
    app = cfg.root / ".obsidian" / "app.json"
    if app.is_file():
        try:
            data = json.loads(app.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
            add("obsidian_settings", False, ".obsidian/app.json nicht lesbar.", "warning")
        if data is not None:
            for key, (expected, label) in OBSIDIAN_EXPECTED.items():
                actual = data.get(key)
                add(f"obsidian_{key}", actual == expected, f"{label}." if actual == expected
                    else f"Obsidian: {label} (aktuell {actual!r}).", "warning")
            filters = data.get("userIgnoreFilters") or []
            ok = any(str(f).strip("/") == ".pkm" for f in filters)
            add("obsidian_ignore_pkm", ok, ".pkm/ ist in Obsidian ausgeschlossen." if ok
                else "Obsidian: .pkm/ unter „Ausgeschlossene Dateien“ eintragen.", "warning")
    else:
        add("obsidian_settings", True, "Keine .obsidian/app.json gefunden (Obsidian-Einstellungen nicht geprüft).")
    errors = sum(1 for c in checks if c["severity"] == "error")
    warnings = sum(1 for c in checks if c["severity"] == "warning")
    shown = [c for c in checks if c["severity"] == "error"] if short else checks
    return {"status": "error" if errors else "ok", "errors": errors, "warnings": warnings, "checks": shown}
