"""Git with a separate Git directory (specification 5.4, 5.5, 7.5).

All calls run with ``--git-dir``/``--work-tree``. Inputs are never passed on as options;
paths always come after ``--``. There is no operation that rewrites history.

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
    """Error of a Git call (status ``git_error``)."""

    def __init__(self, message: str, **data: Any) -> None:
        """Create the error.

        Args:
            message: Explanation including the output of Git.
            **data: Additional fields.
        """
        super().__init__("git_error", message, **data)


@dataclass
class Commit:  # pylint: disable=too-many-instance-attributes
    """A commit with the PKM lines from the commit message.

    Attributes:
        sha: Full commit hash.
        date: Author date (ISO 8601).
        author: Author name.
        subject: First line of the message.
        note: Change note (text between subject and PKM lines).
        doc_id: ``PKM-Id``.
        version: ``PKM-Version``.
        source: ``PKM-Source`` (``chat``, ``user`` or ``agent``).
        files: Changed files as (status, path).
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
        """Path of the document in this commit.

        Returns:
            The first path that is not deleted or ``None`` (e.g. for a delete commit).
        """
        return next((path for status, path in self.files if not status.startswith("D")), None)


class Git:
    """Git calls for the vault with a separate Git directory."""

    def __init__(self, git_dir: Path, work_tree: Path, author: str | None = None, exe: str = "git") -> None:
        """Create the Git access.

        Args:
            git_dir: Git directory outside the vault.
            work_tree: Vault root.
            author: Author for commits (``Name <mail>``); ``None`` uses the Git identity.
            exe: Git program (name in ``PATH`` or absolute path).
        """
        self.git_dir = git_dir
        self.work_tree = work_tree
        self.author = author
        self.exe = exe

    # Basics *******************************************************************

    def _cmd(self, args: list[str]) -> list[str]:
        """Build the complete command line.

        Args:
            args: Git subcommand and arguments.

        Returns:
            Command line with ``--git-dir``/``--work-tree`` and fixed options.
        """
        return [
            self.exe,
            f"--git-dir={self.git_dir}",
            f"--work-tree={self.work_tree}",
            "-c", "core.quotepath=false",
            "-c", "core.precomposeunicode=true",
            *args,
        ]

    def run(self, *args: str, stdin: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
        """Run Git.

        Args:
            *args: Git subcommand and arguments.
            stdin: Input for Git (e.g. the commit message).
            check: Raise a ``GitError`` for an exit code other than 0.

        Returns:
            The result of the process.

        Raises:
            GitError: If Git is missing or (with ``check``) the call fails.
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
            raise GitError("git is not installed or not in PATH.") from exc
        if check and proc.returncode != 0:
            raise GitError(f"git {args[0]} failed: {proc.stderr.decode('utf-8', 'replace').strip()}")
        return proc

    def out(self, *args: str) -> str:
        """Run Git and return the output as text.

        Args:
            *args: Git subcommand and arguments.

        Returns:
            Standard output (UTF-8).
        """
        return self.run(*args).stdout.decode("utf-8", "replace")

    def installed(self) -> bool:
        """Check whether Git is installed.

        Returns:
            ``True`` if the Git program exists (absolute path or found in ``PATH``).
        """
        return Path(self.exe).is_file() or shutil.which(self.exe) is not None

    def is_repo(self) -> bool:
        """Check whether the Git directory is a repo.

        Returns:
            ``True`` if the directory exists and Git recognizes it as a repo.
        """
        return self.git_dir.is_dir() and self.run("rev-parse", "--git-dir", check=False).returncode == 0

    def config_get(self, key: str) -> str | None:
        """Read a Git configuration value.

        Args:
            key: Key, e.g. ``user.name``.

        Returns:
            The value or ``None`` if it is not set.
        """
        value = self.run("config", "--get", key, check=False).stdout.decode("utf-8", "replace").strip()
        return value or None

    def problem(self) -> str | None:
        """Reason why writing is not possible.

        Returns:
            Error text or ``None`` if Git is ready.
        """
        problem = None
        if not self.installed():
            problem = "git is not installed or not in PATH."
        elif not self.is_repo():
            problem = f"No Git repo at {self.git_dir}. Please run `pkm init`."
        elif not self.config_get("user.name") or not self.config_get("user.email"):
            problem = "Git identity missing: set user.name and user.email."
        return problem

    def require_ok(self) -> None:
        """Make sure Git is ready for writing.

        Raises:
            PkmError: ``git_unavailable`` with the reason.
        """
        msg = self.problem()
        if msg:
            raise PkmError("git_unavailable", msg)

    def init(self) -> bool:
        """Create the repo in the Git directory, without ``.git`` in the vault.

        Returns:
            ``True`` if the repo was newly created.
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
        """Check whether there is already a commit.

        Returns:
            ``True`` if ``HEAD`` exists.
        """
        return self.run("rev-parse", "--verify", "--quiet", "HEAD", check=False).returncode == 0

    # Status *******************************************************************

    def is_dirty(self, path: str) -> bool:
        """Check whether a file differs from the last commit (incl. untracked or deleted).

        Args:
            path: Relative path.

        Returns:
            ``True`` if it differs.
        """
        return bool(self.run("status", "--porcelain=v1", "--untracked-files=all", "--", path).stdout.strip())

    def status_entries(self, *pathspecs: str) -> list[tuple[str, str]]:
        """Changed, deleted and untracked files, without rename detection.

        Args:
            *pathspecs: Paths or folders.

        Returns:
            List of (XY status, path).
        """
        out = self.run(
            "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames", "--", *pathspecs
        ).stdout.decode("utf-8", "replace")
        return [(rec[:2], rec[3:]) for rec in out.split("\0") if len(rec) > 3]

    def has_changes(self, *pathspecs: str) -> bool:
        """Check whether there are uncommitted changes below the paths.

        Args:
            *pathspecs: Paths or folders.

        Returns:
            ``True`` for uncommitted changes.
        """
        return bool(self.status_entries(*pathspecs))

    # Writing ******************************************************************

    def commit_paths(self, paths: list[str], message: str, author: str | None = None, as_user: bool = False) -> str:
        """Commit exactly these paths; other uncommitted changes stay untouched.

        Args:
            paths: Files or folders, also deleted paths.
            message: Commit message.
            author: Different author; ``self.author`` if omitted.
            as_user: Commit with the user's Git identity instead of ``PKM_GIT_AUTHOR``.

        Returns:
            The full hash of the new commit.

        Raises:
            ValueError: If no paths are given.
            GitError: If the commit fails (the paths are then unstaged again).
        """
        if not paths:
            raise ValueError("No paths")
        self.run("add", "-A", "--", *paths)
        args = ["commit", "--quiet", "--only", "-F", "-"]
        author = None if as_user else (author or self.author)
        if author:
            args.append(f"--author={author}")
        proc = self.run(*args, "--", *paths, stdin=message.encode("utf-8"), check=False)
        if proc.returncode != 0:
            self.unstage(paths)
            raise GitError("Commit failed: " + proc.stderr.decode("utf-8", "replace").strip())
        return self.out("rev-parse", "HEAD").strip()

    def unstage(self, paths: list[str]) -> None:
        """Remove paths from the index without changing the working copy.

        Args:
            paths: Paths.
        """
        if self.has_head():
            self.run("restore", "--staged", "--", *paths, check=False)
        else:
            self.run("rm", "--cached", "--quiet", "--ignore-unmatch", "--", *paths, check=False)

    # Reading ******************************************************************

    def show_file(self, sha: str, path: str) -> bytes:
        """Read the content of a file in a commit.

        Args:
            sha: Commit hash or ``HEAD``.
            path: Relative path in this commit.

        Returns:
            The bytes of the file.

        Raises:
            ValueError: For an invalid commit identifier.
        """
        if sha != "HEAD" and not SHA_RE.fullmatch(sha):
            raise ValueError("Invalid commit")
        return self.run("show", f"{sha}:{path}").stdout

    def commit_files(self, sha: str) -> list[tuple[str, str]]:
        """Changed files of a commit.

        Args:
            sha: Commit hash.

        Returns:
            List of (status, path), without rename detection.
        """
        out = self.run("diff-tree", "--no-commit-id", "--name-status", "-r", "-z", "--root", "--no-renames", sha)
        parts = out.stdout.decode("utf-8", "replace").split("\0")
        pairs = zip(parts[0::2], parts[1::2], strict=False)
        return [(status, path) for status, path in pairs if status]

    def log_for_id(self, doc_id: str) -> list[Commit]:
        """All commits with ``PKM-Id: <id>``, regardless of the current location of the document.

        Args:
            doc_id: Document ID.

        Returns:
            Commits, oldest first; empty if there is no commit yet.

        Raises:
            PkmError: ``invalid_id`` for an invalid ID.
        """
        if not is_valid_id(doc_id):
            raise PkmError("invalid_id", f"Invalid ID: {doc_id}")
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
        """Convert a record from ``git log`` into a commit.

        Args:
            rec: Record with fields separated by ``\\x1f``.
            doc_id: Expected document ID.

        Returns:
            The commit or ``None`` if the record is empty or belongs to another ID.
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
    """Build the commit message in the fixed format of 5.4.

    Args:
        title: Document title.
        version_label: Suffix in the subject, e.g. ``v3``, ``moved`` or ``deleted``.
        note: Change note (one line).
        doc_id: Document ID for ``PKM-Id``.
        version: Version number for ``PKM-Version``.
        source: ``chat``, ``user`` or ``agent``.

    Returns:
        The message with subject, note and PKM lines.

    Raises:
        ValueError: For an unknown source.
    """
    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source}")
    title = " ".join(title.split()) or doc_id
    note = " ".join(note.split())
    lines = [f"doc: {title} {version_label}", ""]
    if note:
        lines += [note, ""]
    lines += [f"PKM-Id: {doc_id}", f"PKM-Version: {version}", f"PKM-Source: {source}"]
    return "\n".join(lines) + "\n"


def parse_message(body: str) -> tuple[str, str, dict[str, str]]:
    """Split a commit message into subject, note and PKM lines.

    Args:
        body: Complete commit message.

    Returns:
        Tuple of (subject, note, PKM lines as a dictionary).
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
