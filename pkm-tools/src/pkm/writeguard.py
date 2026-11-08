"""Protection checks before writing: size limit ``PKM_MAX_KB`` and shortening (7.1, 7.2).

Both protect against unintended results and can be overridden only after the user's confirmation:
``confirm_large`` for the size limit, ``confirm_shortening`` for a clear shortening.

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

# Imports *********************************************************************

from __future__ import annotations

from . import docimages
from .errors import PkmError
from .images import find_images, to_placeholders
from .normalize import normalize_text
from .parse import split_sections
from .vault import Doc

# Variables *******************************************************************

SHORTENING_RATIO = 0.6

# Classes *********************************************************************

# Functions *******************************************************************


def check_size(text: str, what: str, max_kb: int, confirmed: bool = False) -> None:
    """Check the size limit ``PKM_MAX_KB`` against the text without data URIs.

    The limit protects the context of the model, so it applies to the text as ``read`` returns it
    (embedded images replaced by placeholders), not to the size of the file. After the user's
    confirmation (``confirm_large``) a larger text is allowed.

    Args:
        text: Text to check.
        what: Label for the error message.
        max_kb: Limit in KB.
        confirmed: The user confirmed the larger text (``confirm_large``).

    Raises:
        PkmError: ``too_large`` if the text without embedded images is larger and not confirmed; the
            message names the text and the embedded images separately, asks for confirmation and
            suggests ``fix_images`` with ``extract`` for large embedded images.
    """
    text_bytes = len(to_placeholders(text).encode("utf-8"))
    if text_bytes > max_kb * 1024 and not confirmed:
        image_bytes = sum(len(r.link) for r in find_images(text) if r.inline)
        hint = (" Large embedded images can be moved to files with fix_images (extract: true)."
                if image_bytes else "")
        raise PkmError("too_large", f"{what} has {text_bytes // 1024} KB of text without embedded images "
                       f"(limit {max_kb} KB, PKM_MAX_KB) and {image_bytes // 1024} KB of embedded images. "
                       f"If the user confirms the size, call again with confirm_large=true.{hint}",
                       text_kb=text_bytes // 1024, embedded_images_kb=image_bytes // 1024, max_kb=max_kb)


def check_shortening(doc: Doc, new_body: str, confirmed: bool) -> None:
    """Shortening protection of ``rewrite_document`` (less than 60 % or missing sections).

    Args:
        doc: Document before the change.
        new_body: New, normalized body.
        confirmed: Shortening was confirmed by the user.

    Raises:
        PkmError: ``large_shortening`` with the missing sections.
    """
    assert doc.parsed is not None
    old_body = normalize_text(doc.parsed.body)
    new_keys = {s.key for s in split_sections(new_body)}
    missing = [k for k in doc.parsed.section_keys() if k not in new_keys]
    removed = docimages.removed_images(old_body, new_body)
    ratio = len(new_body) / len(old_body) if old_body else 1.0
    if not confirmed and (ratio < SHORTENING_RATIO or missing or removed):
        raise PkmError(
            "large_shortening",
            "The new content is clearly shorter or sections are missing. "
            "Please have the user confirm it and call again with confirm_shortening=true.",
            missing_sections=missing, removed_images=removed, old_chars=len(old_body), new_chars=len(new_body),
            ratio=round(ratio, 2), path=doc.rel,
        )

# Main ************************************************************************
