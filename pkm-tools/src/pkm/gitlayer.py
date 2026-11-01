"""Git mit getrenntem Git-Verzeichnis (Spezifikation 5.4, 5.5, 7.5).

Alle Aufrufe laufen mit `--git-dir`/`--work-tree`. Eingaben werden nie als Optionen
durchgereicht; Pfade stehen immer nach `--`. Es gibt keine Operation, die Geschichte umschreibt.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .errors import PkmError
from .ids import is_valid_id

TRAILER_RE = re.compile(r"^(PKM-Id|PKM-Version|PKM-Source):[ \t]*(.*)$")
SOURCES = ("chat", "user", "agent")


class GitError(PkmError):
    def __init__(self, message: str, **data) -> None:
        super().__init__("git_error", message, **data)


@dataclass
class Commit:
    sha: str
    date: str
    author: str
    subject: str
    note: str
    doc_id: str | None
    version: int | None
    source: str | None
    files: list[tuple[str, str]] = field(default_factory=list)  # (status, path)

    @property
    def path(self) -> str | None:
        """Pfad des Dokuments in diesem Commit (nicht gelöscht)."""
        for status, path in self.files:
            if not status.startswith("D"):
                return path
        return None


def build_message(title: str, version_label: str, note: str, doc_id: str, version: int, source: str) -> str:
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
    note = "\n".join(note_lines).strip()
    return subject, note, trailers


class Git:
    def __init__(self, git_dir: Path, work_tree: Path, author: str | None = None) -> None:
        self.git_dir = git_dir
        self.work_tree = work_tree
        self.author = author

    # --- Grundlagen ---
    def _cmd(self, args: list[str]) -> list[str]:
        return [
            "git",
            f"--git-dir={self.git_dir}",
            f"--work-tree={self.work_tree}",
            "-c", "core.quotepath=false",
            "-c", "core.precomposeunicode=true",
            *args,
        ]

    def run(self, *args: str, input: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
        env = os.environ.copy()
        env.update({"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})
        env.pop("GIT_DIR", None)
        env.pop("GIT_WORK_TREE", None)
        try:
            proc = subprocess.run(
                self._cmd(list(args)), input=input, capture_output=True, env=env, cwd=self.work_tree
            )
        except FileNotFoundError as exc:
            raise GitError("git ist nicht installiert oder nicht im PATH.") from exc
        if check and proc.returncode != 0:
            raise GitError(
                f"git {args[0]} fehlgeschlagen: {proc.stderr.decode('utf-8', 'replace').strip()}",
            )
        return proc

    def out(self, *args: str) -> str:
        return self.run(*args).stdout.decode("utf-8", "replace")

    @staticmethod
    def installed() -> bool:
        return shutil.which("git") is not None

    def is_repo(self) -> bool:
        if not self.git_dir.is_dir():
            return False
        return self.run("rev-parse", "--git-dir", check=False).returncode == 0

    def config_get(self, key: str) -> str | None:
        proc = self.run("config", "--get", key, check=False)
        value = proc.stdout.decode("utf-8", "replace").strip()
        return value or None

    def problem(self) -> str | None:
        """Grund, warum nicht geschrieben werden kann, sonst None."""
        if not self.installed():
            return "git ist nicht installiert oder nicht im PATH."
        if not self.is_repo():
            return f"Kein Git-Repo unter {self.git_dir}. Bitte `pkm init` ausführen."
        if not self.config_get("user.name") or not self.config_get("user.email"):
            return "Git-Identität fehlt: user.name und user.email setzen."
        return None

    def require_ok(self) -> None:
        msg = self.problem()
        if msg:
            raise PkmError("git_unavailable", msg)

    def init(self) -> bool:
        """Repo im Git-Verzeichnis anlegen (ohne `.git` im Vault). True, wenn neu angelegt."""
        if self.is_repo():
            return False
        self.git_dir.parent.mkdir(parents=True, exist_ok=True)
        self.run("init", "--quiet")
        self.run("config", "core.bare", "false")
        self.run("config", "core.worktree", str(self.work_tree))
        return True

    def has_head(self) -> bool:
        return self.run("rev-parse", "--verify", "--quiet", "HEAD", check=False).returncode == 0

    # --- Status ---
    def is_tracked(self, path: str) -> bool:
        return self.run("ls-files", "--error-unmatch", "--", path, check=False).returncode == 0

    def is_dirty(self, path: str) -> bool:
        """Weicht die Datei vom letzten Commit ab (inkl. nicht verfolgt oder gelöscht)?"""
        out = self.run("status", "--porcelain=v1", "--untracked-files=all", "--", path).stdout
        return bool(out.strip())

    # --- Schreiben ---
    def commit_paths(self, paths: list[str], message: str, author: str | None = None) -> str:
        """Genau diese Pfade committen; andere offene Änderungen bleiben unberührt."""
        if not paths:
            raise ValueError("Keine Pfade")
        self.run("add", "-A", "--", *paths)
        args = ["commit", "--quiet", "--only", "-F", "-"]
        author = author or self.author
        if author:
            args.append(f"--author={author}")
        args += ["--", *paths]
        proc = self.run(*args, input=message.encode("utf-8"), check=False)
        if proc.returncode != 0:
            self.unstage(paths)
            raise GitError(
                "Commit fehlgeschlagen: " + proc.stderr.decode("utf-8", "replace").strip(),
            )
        return self.out("rev-parse", "HEAD").strip()

    def unstage(self, paths: list[str]) -> None:
        if self.has_head():
            self.run("restore", "--staged", "--", *paths, check=False)
        else:
            self.run("rm", "--cached", "--quiet", "--ignore-unmatch", "--", *paths, check=False)

    # --- Lesen ---
    def show_file(self, sha: str, path: str) -> bytes:
        if not re.fullmatch(r"[0-9a-f]{7,64}", sha):
            raise ValueError("Ungültiger Commit")
        return self.run("show", f"{sha}:{path}").stdout

    def commit_files(self, sha: str) -> list[tuple[str, str]]:
        out = self.run("diff-tree", "--no-commit-id", "--name-status", "-r", "-z", "--root", "--no-renames", sha).stdout
        parts = out.decode("utf-8", "replace").split("\0")
        files: list[tuple[str, str]] = []
        i = 0
        while i + 1 < len(parts):
            status, path = parts[i], parts[i + 1]
            if not status:
                break
            files.append((status, path))
            i += 2
        return files

    def log_for_id(self, doc_id: str) -> list[Commit]:
        """Alle Commits mit `PKM-Id: <id>`, älteste zuerst. Unabhängig vom aktuellen Ort."""
        if not is_valid_id(doc_id):
            raise PkmError("invalid_id", f"Ungültige ID: {doc_id}")
        if not self.has_head():
            return []
        out = self.out(
            "log", "--format=%x1e%H%x1f%aI%x1f%an%x1f%B", f"--grep=^PKM-Id: {doc_id}$", "HEAD"
        )
        commits: list[Commit] = []
        for rec in out.split("\x1e"):
            if not rec.strip():
                continue
            sha, date, author, body = rec.split("\x1f", 3)
            subject, note, tr = parse_message(body)
            if tr.get("PKM-Id") != doc_id:
                continue
            version = int(tr["PKM-Version"]) if tr.get("PKM-Version", "").isdigit() else None
            commits.append(
                Commit(sha, date, author, subject, note, doc_id, version, tr.get("PKM-Source"), self.commit_files(sha))
            )
        commits.reverse()
        return commits
