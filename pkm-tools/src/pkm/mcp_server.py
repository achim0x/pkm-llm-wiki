"""MCP server ``pkm-mcp`` (specification 7). Thin wrapper around ``Service``.

Transport stdio. No network access, no LLM calls, no background processes.

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
from collections.abc import Callable
from datetime import datetime
from typing import Any

from mcp.types import TextContent

from .config import DEFAULT_LANGUAGE, DOC_LANGUAGES, Config, configured_language
from .errors import PkmError
from .service import Service

try:  # mcp >= 2
    from mcp.server.mcpserver import Image
    from mcp.server.mcpserver import MCPServer as Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as Server  # type: ignore[no-redef]
    from mcp.server.fastmcp import Image  # type: ignore[no-redef]

# Variables *******************************************************************

IMAGES_DOC = (
    "images: list of images {name, alt, svg | png_base64 | import_path, mode auto|inline|file}; the text contains "
    "{{image:<name>}} at the position. Diagrams as SVG, photos/screenshots as PNG/JPEG (file in the vault folder "
    "pkm_img_import/, import_path). Up to 24 KB embedded, otherwise a file; in scratch/ always embedded. Never "
    "write data URIs into texts by hand. nonconforming_image: show the findings (image_issues) and the proposal, "
    "after confirmation repeat with fix_images=true and image_alt {name: text}. image_warnings: nonconforming images "
    "in the existing text, offer a fix with fix_images."
)

INSTRUCTIONS = (
    "Access to the personal knowledge management (PKM). The wiki is read-only. "
    "Documents are created or changed only after a draft has been shown and confirmed. "
    "Every change needs `expected_hash` from `read` and results in a new version (with a Git commit if version "
    "control is on; without it history/restore return not_versioned). "
    + IMAGES_DOC
)

_SERVICE: dict[str, Service] = {}

# Classes *********************************************************************

# Functions *******************************************************************


def get_service() -> Service:
    """Create the service from the environment on the first call.

    Returns:
        The service.

    Raises:
        PkmError: ``config_error`` for a missing or invalid configuration.
    """
    if "svc" not in _SERVICE:
        _SERVICE["svc"] = Service(Config.from_env())
    return _SERVICE["svc"]


def reset_service() -> None:
    """Discard the service (e.g. in tests after a changed environment)."""
    _SERVICE.clear()


def _log(tool: str, args: dict[str, Any], result: dict[str, Any]) -> None:
    """Log a call in ``.pkm/mcp.log``; errors while logging are ignored.

    Args:
        tool: Tool name.
        args: Call parameters.
        result: Return value of the tool.
    """
    svc = _SERVICE.get("svc")
    if svc is not None:
        entry = {
            "ts": datetime.now(svc.cfg.tz).isoformat(timespec="seconds"),
            "tool": tool,
            "target": args.get("target") or args.get("path") or args.get("title") or args.get("query"),
            "status": result.get("status"),
            "version": result.get("version"),
            "commit": result.get("commit"),
        }
        try:
            svc.cfg.log_path.parent.mkdir(parents=True, exist_ok=True)
            with svc.cfg.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # The log must never get in the way.


def call(tool: str, fn: Callable[..., dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Run a tool; domain errors are returned as a status.

    Args:
        tool: Tool name (for the log).
        fn: Function that receives the service as first argument (e.g. ``Service.read``).
        **kwargs: Parameters of the tool.

    Returns:
        Return value of the tool or ``{status, message, …}`` for domain errors.
    """
    try:
        result = fn(get_service(), **kwargs)
    except PkmError as exc:
        result = exc.to_dict()
    _log(tool, kwargs, result)
    return result


def image_content(result: dict[str, Any]) -> list[TextContent | Image]:
    """Convert the return value of ``read_image`` into MCP content.

    Args:
        result: Result of ``Service.read_image`` or an error.

    Returns:
        Metadata as JSON text, for raster images additionally the image.
    """
    data = result.pop("data", None)
    content: list[TextContent | Image] = [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    if data:
        content.append(Image(data=data, format={"jpg": "jpeg"}.get(result.get("format", "png"), result.get("format"))))
    return content


def register_read_tools(server: Server) -> None:
    """Register the reading tools (7.3).

    Args:
        server: MCP server.
    """

    @server.tool()
    def search(query: str, scope: str = "wiki", max_results: int = 8) -> dict:
        """Full-text search (prefix search, umlaut-tolerant). scope: wiki (default) | documents | scratch | all
        (all = wiki + documents; scratch only when given explicitly).
        max_results at most 25. Hits with id, version, path, title, type, summary, snippet,
        score, updated and for documents processed (whether incorporated into the wiki)."""
        return call("search", Service.search, query=query, scope=scope, max_results=max_results)

    @server.tool()
    def read(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        target: str,
        version: int | None = None,
        section: str | None = None,
        offset: int = 0,
        max_chars: int | None = None,
        content: bool = True,
    ) -> dict:
        """Read a document or wiki page. target: path, wikilink, id:d-… or short citation (short_citation).
        With version an earlier version from Git (read-only). Returns hash for expected_hash and sections
        (key, sha). Large documents: content=false (metadata, sections, content_length only), then section
        (one section) or offset/max_chars (page by page, next_offset). Above 40000 characters without these
        parameters content is left out (content_omitted)."""
        return call("read", Service.read, target=target, version=version, section=section, offset=offset,
                    max_chars=max_chars, content=content)

    @server.tool(name="read_image")
    def read_image_tool(target: str, image: str | None = None, as_: str = "auto") -> list[TextContent | Image]:
        """View an image: image = image name in document target (from read: images), without image the image file
        target itself. PNG comes as an image, SVG as text (as_ = svg_text, image only with PKM_SVG_RASTER). Never
        copy Base64 into texts."""
        return image_content(call("read_image", Service.read_image, target=target, image=image, as_=as_))

    @server.tool()
    def history(target: str, diff_from: int | None = None, diff_to: int | None = None) -> dict:
        """Version history of a document (version, date, source, note, commit).
        With diff_from additionally a unified diff up to diff_to (default: current version)."""
        return call("history", Service.history, target=target, diff_from=diff_from, diff_to=diff_to)

    @server.tool()
    def show_citations(target: str, statement: str | None = None, with_excerpt: bool = False) -> dict:
        """Citations of a wiki page: original (current path), section/page, quote, cited and
        current version, status (ok | moved | newer_version | missing) and Obsidian link.
        statement narrows to paragraphs containing this text. with_excerpt loads the section from the
        cited and, if different, the current version."""
        return call("show_citations", Service.show_citations, target=target, statement=statement,
                    with_excerpt=with_excerpt)

    @server.tool()
    def read_index() -> dict:
        """Returns wiki/index.md (catalog of all wiki pages with summary)."""
        return call("read_index", Service.read_index)

    @server.tool()
    def list_unprocessed() -> dict:
        """Documents whose current state is not yet incorporated into the wiki."""
        return call("list_unprocessed", Service.list_unprocessed)


def _register_write_tools(server: Server) -> None:
    """Register the writing tools (7.2).

    New documents only in ``documents/_inbox/`` or ``scratch/``, changes only to ``documents/**/*.md``
    and ``scratch/**/*.md``. Every change in ``documents/`` results in a new version (with Git a commit),
    in ``scratch/`` without version and commit. There is no deleting or moving.

    Args:
        server: MCP server.
    """

    @server.tool()
    def create_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        title: str,
        content: str,
        tags: list[str] | None = None,
        short_citation: str | None = None,
        date_document: str | None = None,
        context: str | None = None,
        related: list[str] | None = None,
        kind: str | None = None,
        toolchain: str | None = None,
        note: str | None = None,
        area: str = "documents",
        folder: str | None = None,
        images: list[dict] | None = None,
        fix_images: bool = False,
        image_alt: dict | None = None,
    ) -> dict:
        """Create a new document in documents/_inbox/ (version 1, commit) or with area="scratch"
        a short-lived note/todo list in scratch/[folder/] (without version and commit, never in the wiki).
        Only after a draft has been shown and confirmed. content without frontmatter. tags: lower case with
        hyphens. kind: note | standard | regulation | correction. toolchain: own model name plus
        "(pkm-mcp)", becomes toolchain_markdown. Images see images."""
        return call("create_document", Service.create_document, title=title, content=content, tags=tags,
                    short_citation=short_citation, date_document=date_document, context=context, related=related,
                    kind=kind, toolchain=toolchain, note=note, area=area, folder=folder, images=images,
                    fix_images=fix_images, image_alt=image_alt)

    @server.tool()
    def rewrite_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        target: str, content: str, expected_hash: str, note: str | None = None, confirm_shortening: bool = False,
        images: list[dict] | None = None, fix_images: bool = False, image_alt: dict | None = None,
    ) -> dict:
        """Replace the entire content below the frontmatter (the normal case for continuations).
        On a clear shortening or missing sections status large_shortening: have the user confirm the
        shortening and call again with confirm_shortening=true. Leave image placeholders from read
        (pkm-image:…) unchanged; missing images count as removed (large_shortening)."""
        return call("rewrite_document", Service.rewrite_document, target=target, content=content,
                    expected_hash=expected_hash, note=note, confirm_shortening=confirm_shortening, images=images,
                    fix_images=fix_images, image_alt=image_alt)

    @server.tool()
    def append_to_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        target: str, text: str, expected_hash: str, section: str | None = None, note: str | None = None,
        images: list[dict] | None = None, fix_images: bool = False, image_alt: dict | None = None,
    ) -> dict:
        """Append text: at the end of section section (key, e.g. "Open points",
        "Notes#2" or "_preamble"), a new section if it does not exist, without section at the end of the file."""
        return call("append_to_document", Service.append_to_document, target=target, text=text,
                    expected_hash=expected_hash, section=section, note=note, images=images, fix_images=fix_images,
                    image_alt=image_alt)

    @server.tool()
    def edit_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        target: str, old: str, new: str, expected_hash: str, note: str | None = None,
        images: list[dict] | None = None, confirm_shortening: bool = False, fix_images: bool = False,
        image_alt: dict | None = None,
    ) -> dict:
        """Replace the passage old (must occur exactly once, in the text with image placeholders from read) by new.
        new may be empty. If the change removes an image: large_shortening, after confirmation confirm_shortening."""
        return call("edit_document", Service.edit_document, target=target, old=old, new=new,
                    expected_hash=expected_hash, note=note, images=images, confirm_shortening=confirm_shortening,
                    fix_images=fix_images, image_alt=image_alt)

    @server.tool()
    def add_image(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        target: str, expected_hash: str, image: dict, section: str | None = None, caption: str | None = None,
        note: str | None = None,
    ) -> dict:
        """Insert an image into an existing document, at the end of section (otherwise at the end of the file),
        optionally with a caption. image like an entry of images. Only after a draft has been shown and confirmed."""
        return call("add_image", Service.add_image, target=target, expected_hash=expected_hash, image=image,
                    section=section, caption=caption, note=note)

    @server.tool(name="fix_images")
    def fix_images_tool(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        target: str, expected_hash: str, images: list[str] | None = None, image_alt: dict | None = None,
        apply: bool = False, confirm_shortening: bool = False, note: str | None = None,
    ) -> dict:
        """Fix the notation of nonconforming image data URIs of a document in documents/ or scratch/ per 4.9.
        Without apply only a proposal (status proposal, image_issues, diff); only after explicit
        confirmation with apply=true (new version, PKM-Fix: images). images: only these image names. image_alt:
        alt texts per name. confirm_shortening: confirm removing unused definitions."""
        return call("fix_images", Service.fix_images, target=target, expected_hash=expected_hash,
                    images_only=images, image_alt=image_alt, apply=apply, confirm_shortening=confirm_shortening,
                    note=note, source="chat")

    @server.tool()
    def update_frontmatter(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        target: str,
        expected_hash: str,
        set: dict | None = None,  # pylint: disable=redefined-builtin
        add: dict | None = None,
        remove: list[str] | None = None,
        note: str | None = None,
    ) -> dict:
        """Change frontmatter: set (set), add (append to lists), remove (remove fields).
        Protected: id, version, date_markdown, date_updated, status_markdown. Comments in the frontmatter are
        lost in the process."""
        return call("update_frontmatter", Service.update_frontmatter, target=target, expected_hash=expected_hash,
                    set=set, add=add, remove=remove, note=note)

    @server.tool()
    def restore_document(target: str, version: int, expected_hash: str) -> dict:
        """Restore the content of an earlier version as a new version (history is kept).
        For files in scratch/ the result is not_versioned."""
        return call("restore_document", Service.restore_document, target=target, version=version,
                    expected_hash=expected_hash)


def language_instructions(language: str) -> str:
    """Instruction for the language of documents created in chat (``PKM_LANGUAGE``).

    Args:
        language: ``en`` or ``de``.

    Returns:
        Sentence with the language and the section names of new documents.
    """
    name, sections = DOC_LANGUAGES.get(language, DOC_LANGUAGES[DEFAULT_LANGUAGE])
    headings = ", ".join(f"## {s}" for s in sections)
    return (f" Document language: {name}. Write new documents created in chat in {name} with the sections "
            f"{headings}, unless the user asks for another language. When continuing a document keep its "
            "language and section names.")


def build_server(language: str | None = None) -> Server:
    """Build the MCP server with all tools (reading incl. ``read_image``, writing incl. ``add_image``).

    Args:
        language: Document language ``en`` or ``de``; from the configuration if omitted.

    Returns:
        The server.
    """
    server = Server("pkm", instructions=INSTRUCTIONS + language_instructions(language or configured_language()))
    register_read_tools(server)
    _register_write_tools(server)
    return server


def main() -> None:
    """Entry point ``pkm-mcp``: start the server via stdio."""
    build_server().run()

# Main ************************************************************************


if __name__ == "__main__":
    main()
