"""Platform-independent file operations: locking and atomic replacement (macOS, Linux, Windows).

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

import contextlib
import os
import time
from collections.abc import Iterator
from pathlib import Path

try:  # macOS, Linux
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

try:  # Windows
    import msvcrt
except ImportError:  # pragma: no cover - macOS, Linux
    msvcrt = None  # type: ignore[assignment]

# Variables *******************************************************************

REPLACE_ATTEMPTS = 20
RETRY_DELAY = 0.1

# Classes *********************************************************************

# Functions *******************************************************************


def _lock_windows(fd: int) -> None:
    """Lock the first byte of the lock file on Windows; waits until the lock is free.

    Args:
        fd: File descriptor of the lock file.
    """
    locked = False
    while not locked:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            locked = True
        except OSError:
            time.sleep(RETRY_DELAY)


@contextlib.contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Exclusive lock via a lock file (``fcntl`` or ``msvcrt``).

    Args:
        path: Path of the lock file (created if needed).

    Yields:
        Nothing; the lock holds inside the ``with`` block.
    """
    with open(path, "a+b") as fh:
        if fcntl is not None:
            fcntl.flock(fh, fcntl.LOCK_EX)
        elif msvcrt is not None:
            _lock_windows(fh.fileno())
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(fh, fcntl.LOCK_UN)
            elif msvcrt is not None:
                os.lseek(fh.fileno(), 0, os.SEEK_SET)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)


def replace_file(src: Path, dst: Path, attempts: int = REPLACE_ATTEMPTS) -> None:
    """Replace a file atomically; on Windows retry while the target is briefly locked.

    Obsidian, a sync client or a virus scanner may keep a file open on Windows for a moment;
    ``os.replace`` then fails with ``PermissionError``.

    Args:
        src: Temporary file.
        dst: Target.
        attempts: Number of attempts.

    Raises:
        PermissionError: If the target is still locked after all attempts.
    """
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            break
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(RETRY_DELAY)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Write bytes atomically (temporary file in the same folder, then replace).

    Args:
        path: Target.
        data: Content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".pkm-tmp-{os.getpid()}-{path.name}")
    try:
        tmp.write_bytes(data)
        replace_file(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()

# Main ************************************************************************
