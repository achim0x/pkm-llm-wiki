"""MCP server ``pkm-pflege-mcp`` for wiki maintenance from Claude Desktop or Cowork.

Runs locally on the PKM host like ``pkm-mcp``. Besides the reading tools it offers the maintenance tools
``begin_maintenance``, ``write_wiki_page``, ``set_document_metadata`` and ``finish_maintenance``. It writes
to ``wiki/`` and ``.pkm/state.json``; on documents it only sets ``id``/``version`` (like ``pkm ids``/
``pkm versions``) and, after the user's confirmation, ``title``, ``context``, ``tags``, ``kind``, ``short_citation``.
Enable only in maintenance conversations.

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

from . import maintrun
from .config import DEFAULT_LANGUAGE, DOC_LANGUAGES, WIKI_SECTIONS, configured_language
from .mcp_server import Server, call, register_read_tools

# Variables *******************************************************************

INSTRUCTIONS = (
    "Maintenance of the PKM wiki (skill pkm-wiki). Flow: begin_maintenance, read documents with read/history, "
    "write wiki pages with write_wiki_page, finally finish_maintenance. Documents in documents/ are "
    "never changed; index.md, _status.md, log.md and sources are generated."
)

# Classes *********************************************************************

# Functions *******************************************************************


def _register_maintenance_tools(server: Server) -> None:
    """Register the maintenance tools.

    Args:
        server: MCP server.
    """

    @server.tool()
    def begin_maintenance(with_lint: bool = False) -> dict:
        """Begin a maintenance run: checks the environment (doctor), commits manual changes as versions,
        assigns missing IDs, returns pending (new, changed, meta_changed, moved, deleted, problems) and
        fixes citations of moved documents. New documents contain missing_fields (missing title,
        context, tags, kind); known_tags lists existing tags with their frequency.
        status blocked: report the error and stop. status needs_decision: duplicate IDs, ask the user.
        with_lint additionally returns the lint report."""
        return call("begin_maintenance", maintrun.begin_maintenance, with_lint=with_lint)

    @server.tool()
    def write_wiki_page(path: str, content: str, expected_hash: str | None = None, fix_images: bool = False) -> dict:
        """Create or completely replace a wiki page below wiki/topics|entities|summaries|syntheses/
        (content with frontmatter). Read existing pages with read first and pass their hash as expected_hash;
        new pages without expected_hash. No commit, finish_maintenance does that. Leave image placeholders from
        read in place. nonconforming_image: have your own data URIs fixed with fix_images=true."""
        return call("write_wiki_page", maintrun.write_wiki_page, path=path, content=content,
                    expected_hash=expected_hash, fix_images=fix_images)

    @server.tool(name="fix_images")
    def fix_images_tool(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        target: str, expected_hash: str, images: list[str] | None = None, image_alt: dict | None = None,
        apply: bool = False, confirm_shortening: bool = False, note: str | None = None,
    ) -> dict:
        """Only after explicit confirmation by the user, never unattended: fix the notation of nonconforming
        image data URIs of a document in documents/ per 4.9 (image_issues from begin_maintenance).
        Without apply only a proposal with diff; apply=true writes a new version (PKM-Fix: images)."""
        return call("fix_images", maintrun.fix_document_images, target=target, expected_hash=expected_hash,
                    images_only=images, image_alt=image_alt, apply=apply, confirm_shortening=confirm_shortening,
                    note=note)

    @server.tool()
    def set_document_metadata(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        target: str,
        expected_hash: str,
        set: dict | None = None,  # pylint: disable=redefined-builtin
        add: dict | None = None,
        overwrite: bool = False,
        note: str | None = None,
    ) -> dict:
        """Only after explicit confirmation by the user: enter title, context, tags, kind, short_citation of a
        document in documents/ (new version, commit with PKM-Source agent). set sets fields, add
        appends to tags. Change existing values only with overwrite=true (otherwise field_exists). kind: note |
        standard | regulation | correction. Tags are normalized (lower case, umlauts spelled out,
        hyphens). expected_hash from read; on conflict read again."""
        return call("set_document_metadata", maintrun.set_document_metadata, target=target,
                    expected_hash=expected_hash, set=set, add=add, overwrite=overwrite, note=note)

    @server.tool()
    def finish_maintenance(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        log_entry: str,
        operation: str = "ingest",
        log_title: str | None = None,
        processed: list[str] | None = None,
        removed: list[str] | None = None,
        questions: list[str] | None = None,
        lint_report: bool = False,
    ) -> dict:
        """Finish a maintenance run: fix citations, generate sources, record processed documents (processed:
        IDs or paths) with the citing pages, remove removed (keys of deleted documents),
        append log_entry (Markdown list) with a timestamp to wiki/log.md, generate index.md and
        _status.md (with questions), run lint and create the agent commit.
        operation: ingest | lint | fix. If lint reports errors in your own pages: fix them and call again with
        operation=fix."""
        return call("finish_maintenance", maintrun.finish_maintenance, log_entry=log_entry, operation=operation,
                    log_title=log_title, processed=processed, removed=removed, questions=questions,
                    lint_report=lint_report)


def wiki_language_instructions(language: str) -> str:
    """Instruction for the language of the wiki (``PKM_LANGUAGE``).

    Args:
        language: ``en`` or ``de``.

    Returns:
        Sentence with the language, the section names of wiki pages and the summary label.
    """
    key = language if language in DOC_LANGUAGES else DEFAULT_LANGUAGE
    name = DOC_LANGUAGES[key][0]
    label, sections = WIKI_SECTIONS[key]
    headings = ", ".join(f"## {s}" for s in sections)
    return (f" Wiki language: {name}. Write new wiki pages and summaries, the log entry and the report in {name}: "
            f"first line '> **{label}:** …', sections {headings}. When updating an existing page keep its "
            "language and section names. Quotes in citations stay literal in the language of the document.")


def build_server(language: str | None = None) -> Server:
    """Build the maintenance server with the reading tools and the maintenance tools.

    Args:
        language: Wiki language ``en`` or ``de``; from the configuration if omitted.

    Returns:
        The server.
    """
    instructions = INSTRUCTIONS + wiki_language_instructions(language or configured_language())
    server = Server("pkm-pflege", instructions=instructions)
    register_read_tools(server)
    _register_maintenance_tools(server)
    return server


def main() -> None:
    """Entry point ``pkm-pflege-mcp``: start the server via stdio."""
    build_server().run()

# Main ************************************************************************


if __name__ == "__main__":
    main()
