"""Git mit getrenntem Git-Verzeichnis (Spezifikation 5.4, 5.5, 7.5).

Alle Aufrufe laufen mit ``--git-dir``/``--work-tree``. Eingaben werden nie als Optionen
durchgereicht; Pfade stehen immer nach ``--``. Es gibt keine Operation, die Geschichte umschreibt.

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
# along with this program.  If not, see <https://gnu.org>.

# *****************************************************************************

# Imports *********************************************************************

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import PkmError
from .ids import is_valid_id

# Variables *******************************************************************

TRAILER_RE = re.compile(r"^(PKM-Id|PKM-Version|PKM-Source):[ \t]*(.*)$")
SOURCES = ("chat", "user", "agent")
SHA_RE = re.compile(r"[0-9a-f]{7,64}")

# Classes *********************************************************************


class GitError(PkmError):
    """Fehler eines Git-Aufrufs (Status ``git_error``)."""

    def __init__(self, message: str, **data: Any) -> None:
        """Fehler anlegen.

        Args:
            message: Erklärung inklusive Ausgabe von Git.
            **data: Zusätzliche Felder.
        """
        super().__init__("git_error", message, **data)


@dataclass
class Commit:  # pylint: disable=too-many-instance-attributes
    """Ein Commit mit den PKM-Zeilen aus der Commit-Nachricht.

    Attributes:
        sha: Voller Commit-Hash.
        date: Autorendatum (ISO 8601).
        author: Autorname.
        subject: Erste Zeile der Nachricht.
        note: Änderungsnotiz (Text zwischen Betreff und PKM-Zeilen).
        doc_id: ``PKM-Id``.
        version: ``PKM-Version``.
        source: ``PKM-Source`` (``chat``, ``user`` oder ``agent``).
        files: Geänderte Dateien als (Status, Pfad).
    """

    sha: str
    date: str
    author: str
    subject: str
    note: str
    doc_id: str | None
    version: int | None
    source: str | None
    files: list[tuple[str, str]] = field(default_factory=list)

    @property
    def path(self) -> str | None:
        """Pfad des Dokuments in diesem Commit.

        Returns:
            Den ersten nicht gelöschten Pfad oder ``None`` (z. B. bei einem Lösch-Commit).
        """
        return next((path for status, path in self.files if not status.startswith("D")), None)


class Git:
    """Git-Aufrufe für den Vault mit getrenntem Git-Verzeichnis."""

    def __init__(self, git_dir: Path, work_tree: Path, author: str | None = None) -> None:
        """Git-Zugang anlegen.

        Args:
            git_dir: Git-Verzeichnis außerhalb des Vaults.
            work_tree: Vault-Wurzel.
            author: Autor für Commits (``Name <mail>``); ``None`` nutzt die Git-Identität.
        """
        self.git_dir = git_dir
        self.work_tree = work_tree
        self.author = author

    # Grundlagen ***************************************************************

    def _cmd(self, args: list[str]) -> list[str]:
        """Vollständige Kommandozeile bilden.

        Args:
            args: Git-Unterbefehl und Argumente.

        Returns:
            Kommandozeile mit ``--git-dir``/``--work-tree`` und festen Optionen.
        """
        return [
            "git",
            f"--git-dir={self.git_dir}",
            f"--work-tree={self.work_tree}",
            "-c", "core.quotepath=false",
            "-c", "core.precomposeunicode=true",
            *args,
        ]

    def run(self, *args: str, stdin: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
        """Git ausführen.

        Args:
            *args: Git-Unterbefehl und Argumente.
            stdin: Eingabe für Git (z. B. die Commit-Nachricht).
            check: Bei Exit-Code ungleich 0 einen ``GitError`` auslösen.

        Returns:
            Das Ergebnis des Prozesses.

        Raises:
            GitError: Wenn Git fehlt oder (mit ``check``) der Aufruf fehlschlägt.
        """
        env = os.environ.copy()
        env.update({"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})
        env.pop("GIT_DIR", None)
        env.pop("GIT_WORK_TREE", None)
        try:
            proc = subprocess.run(
                self._cmd(list(args)), input=stdin, capture_output=True, env=env, cwd=self.work_tree, check=False
            )
        except FileNotFoundError as exc:
            raise GitError("git ist nicht installiert oder nicht im PATH.") from exc
        if check and proc.returncode != 0:
            raise GitError(f"git {args[0]} fehlgeschlagen: {proc.stderr.decode('utf-8', 'replace').strip()}")
        return proc

    def out(self, *args: str) -> str:
        """Git ausführen und die Ausgabe als Text liefern.

        Args:
            *args: Git-Unterbefehl und Argumente.

        Returns:
            Standardausgabe (UTF-8).
        """
        return self.run(*args).stdout.decode("utf-8", "replace")

    @staticmethod
    def installed() -> bool:
        """Prüfen, ob Git installiert ist.

        Returns:
            ``True``, wenn ``git`` im ``PATH`` liegt.
        """
        return shutil.which("git") is not None

    def is_repo(self) -> bool:
        """Prüfen, ob das Git-Verzeichnis ein Repo ist.

        Returns:
            ``True``, wenn das Verzeichnis existiert und Git es als Repo erkennt.
        """
        return self.git_dir.is_dir() and self.run("rev-parse", "--git-dir", check=False).returncode == 0

    def config_get(self, key: str) -> str | None:
        """Git-Konfigurationswert lesen.

        Args:
            key: Schlüssel, z. B. ``user.name``.

        Returns:
            Den Wert oder ``None``, wenn er nicht gesetzt ist.
        """
        value = self.run("config", "--get", key, check=False).stdout.decode("utf-8", "replace").strip()
        return value or None

    def problem(self) -> str | None:
        """Grund, warum nicht geschrieben werden kann.

        Returns:
            Fehlertext oder ``None``, wenn Git bereit ist.
        """
        problem = None
        if not self.installed():
            problem = "git ist nicht installiert oder nicht im PATH."
        elif not self.is_repo():
            problem = f"Kein Git-Repo unter {self.git_dir}. Bitte `pkm init` ausführen."
        elif not self.config_get("user.name") or not self.config_get("user.email"):
            problem = "Git-Identität fehlt: user.name und user.email setzen."
        return problem

    def require_ok(self) -> None:
        """Sicherstellen, dass Git zum Schreiben bereit ist.

        Raises:
            PkmError: ``git_unavailable`` mit dem Grund.
        """
        msg = self.problem()
        if msg:
            raise PkmError("git_unavailable", msg)

    def init(self) -> bool:
        """Repo im Git-Verzeichnis anlegen, ohne ``.git`` im Vault.

        Returns:
            ``True``, wenn das Repo neu angelegt wurde.
        """
        created = False
        if not self.is_repo():
            self.git_dir.parent.mkdir(parents=True, exist_ok=True)
            self.run("init", "--quiet")
            self.run("config", "core.bare", "false")
            self.run("config", "core.worktree", str(self.work_tree))
            created = True
        return created

    def has_head(self) -> bool:
        """Prüfen, ob es schon einen Commit gibt.

        Returns:
            ``True``, wenn ``HEAD`` existiert.
        """
        return self.run("rev-parse", "--verify", "--quiet", "HEAD", check=False).returncode == 0

    # Status *******************************************************************

    def is_dirty(self, path: str) -> bool:
        """Prüfen, ob eine Datei vom letzten Commit abweicht (inkl. nicht verfolgt oder gelöscht).

        Args:
            path: Relativer Pfad.

        Returns:
            ``True`` bei Abweichung.
        """
        return bool(self.run("status", "--porcelain=v1", "--untracked-files=all", "--", path).stdout.strip())

    def status_entries(self, *pathspecs: str) -> list[tuple[str, str]]:
        """Geänderte, gelöschte und nicht verfolgte Dateien, ohne Rename-Erkennung.

        Args:
            *pathspecs: Pfade oder Ordner.

        Returns:
            Liste von (XY-Status, Pfad).
        """
        out = self.run(
            "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames", "--", *pathspecs
        ).stdout.decode("utf-8", "replace")
        return [(rec[:2], rec[3:]) for rec in out.split("\0") if len(rec) > 3]

    def has_changes(self, *pathspecs: str) -> bool:
        """Prüfen, ob es unter den Pfaden offene Änderungen gibt.

        Args:
            *pathspecs: Pfade oder Ordner.

        Returns:
            ``True`` bei offenen Änderungen.
        """
        return bool(self.status_entries(*pathspecs))

    # Schreiben ****************************************************************

    def commit_paths(self, paths: list[str], message: str, author: str | None = None, as_user: bool = False) -> str:
        """Genau diese Pfade committen; andere offene Änderungen bleiben unberührt.

        Args:
            paths: Dateien oder Ordner, auch gelöschte Pfade.
            message: Commit-Nachricht.
            author: Abweichender Autor; ohne Angabe ``self.author``.
            as_user: Mit der Git-Identität des Nutzers statt ``PKM_GIT_AUTHOR`` committen.

        Returns:
            Den vollen Hash des neuen Commits.

        Raises:
            ValueError: Wenn keine Pfade angegeben sind.
            GitError: Wenn der Commit fehlschlägt (die Pfade werden dann wieder ausgetragen).
        """
        if not paths:
            raise ValueError("Keine Pfade")
        self.run("add", "-A", "--", *paths)
        args = ["commit", "--quiet", "--only", "-F", "-"]
        author = None if as_user else (author or self.author)
        if author:
            args.append(f"--author={author}")
        proc = self.run(*args, "--", *paths, stdin=message.encode("utf-8"), check=False)
        if proc.returncode != 0:
            self.unstage(paths)
            raise GitError("Commit fehlgeschlagen: " + proc.stderr.decode("utf-8", "replace").strip())
        return self.out("rev-parse", "HEAD").strip()

    def unstage(self, paths: list[str]) -> None:
        """Pfade aus dem Index nehmen, ohne die Arbeitskopie zu ändern.

        Args:
            paths: Pfade.
        """
        if self.has_head():
            self.run("restore", "--staged", "--", *paths, check=False)
        else:
            self.run("rm", "--cached", "--quiet", "--ignore-unmatch", "--", *paths, check=False)

    # Lesen ********************************************************************

    def show_file(self, sha: str, path: str) -> bytes:
        """Inhalt einer Datei in einem Commit lesen.

        Args:
            sha: Commit-Hash oder ``HEAD``.
            path: Relativer Pfad in diesem Commit.

        Returns:
            Die Bytes der Datei.

        Raises:
            ValueError: Bei ungültigem Commit-Bezeichner.
        """
        if sha != "HEAD" and not SHA_RE.fullmatch(sha):
            raise ValueError("Ungültiger Commit")
        return self.run("show", f"{sha}:{path}").stdout

    def commit_files(self, sha: str) -> list[tuple[str, str]]:
        """Geänderte Dateien eines Commits.

        Args:
            sha: Commit-Hash.

        Returns:
            Liste von (Status, Pfad), ohne Rename-Erkennung.
        """
        out = self.run("diff-tree", "--no-commit-id", "--name-status", "-r", "-z", "--root", "--no-renames", sha)
        parts = out.stdout.decode("utf-8", "replace").split("\0")
        pairs = zip(parts[0::2], parts[1::2], strict=False)
        return [(status, path) for status, path in pairs if status]

    def log_for_id(self, doc_id: str) -> list[Commit]:
        """Alle Commits mit ``PKM-Id: <id>``, unabhängig vom aktuellen Ort des Dokuments.

        Args:
            doc_id: Dokument-ID.

        Returns:
            Commits, älteste zuerst; leer, wenn es noch keinen Commit gibt.

        Raises:
            PkmError: ``invalid_id`` bei ungültiger ID.
        """
        if not is_valid_id(doc_id):
            raise PkmError("invalid_id", f"Ungültige ID: {doc_id}")
        commits: list[Commit] = []
        if self.has_head():
            out = self.out("log", "--format=%x1e%H%x1f%aI%x1f%an%x1f%B", f"--grep=^PKM-Id: {doc_id}$", "HEAD")
            for rec in out.split("\x1e"):
                commit = self._parse_log_record(rec, doc_id)
                if commit is not None:
                    commits.append(commit)
            commits.reverse()
        return commits

    def _parse_log_record(self, rec: str, doc_id: str) -> Commit | None:
        """Einen Datensatz aus ``git log`` in einen Commit umwandeln.

        Args:
            rec: Datensatz mit durch ``\\x1f`` getrennten Feldern.
            doc_id: Erwartete Dokument-ID.

        Returns:
            Den Commit oder ``None``, wenn der Datensatz leer ist oder zu einer anderen ID gehört.
        """
        commit = None
        if rec.strip():
            sha, date, author, body = rec.split("\x1f", 3)
            subject, note, tr = parse_message(body)
            if tr.get("PKM-Id") == doc_id:
                version = int(tr["PKM-Version"]) if tr.get("PKM-Version", "").isdigit() else None
                commit = Commit(sha, date, author, subject, note, doc_id, version, tr.get("PKM-Source"),
                                self.commit_files(sha))
        return commit

# Functions *******************************************************************


def build_message(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    title: str, version_label: str, note: str, doc_id: str, version: int, source: str
) -> str:
    """Commit-Nachricht im festen Format nach 5.4 bilden.

    Args:
        title: Dokumenttitel.
        version_label: Zusatz im Betreff, z. B. ``v3``, ``moved`` oder ``deleted``.
        note: Änderungsnotiz (eine Zeile).
        doc_id: Dokument-ID für ``PKM-Id``.
        version: Versionsnummer für ``PKM-Version``.
        source: ``chat``, ``user`` oder ``agent``.

    Returns:
        Die Nachricht mit Betreff, Notiz und PKM-Zeilen.

    Raises:
        ValueError: Bei unbekannter Quelle.
    """
    if source not in SOURCES:
        raise ValueError(f"Unbekannte Quelle: {source}")
    title = " ".join(title.split()) or doc_id
    note = " ".join(note.split())
    lines = [f"doc: {title} {version_label}", ""]
    if note:
        lines += [note, ""]
    lines += [f"PKM-Id: {doc_id}", f"PKM-Version: {version}", f"PKM-Source: {source}"]
    return "\n".join(lines) + "\n"


def parse_message(body: str) -> tuple[str, str, dict[str, str]]:
    """Commit-Nachricht in Betreff, Notiz und PKM-Zeilen zerlegen.

    Args:
        body: Vollständige Commit-Nachricht.

    Returns:
        Tupel aus (Betreff, Notiz, PKM-Zeilen als Wörterbuch).
    """
    lines = body.strip("\n").split("\n")
    subject = lines[0] if lines else ""
    trailers: dict[str, str] = {}
    note_lines: list[str] = []
    for line in lines[1:]:
        m = TRAILER_RE.match(line)
        if m:
            trailers[m.group(1)] = m.group(2).strip()
        else:
            note_lines.append(line)
    return subject, "\n".join(note_lines).strip(), trailers

# Main ************************************************************************
