"""Configuration via environment variables (specification 7.1).

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
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import PkmError

# Variables *******************************************************************

DEFAULT_AUTHOR = "pkm-mcp <pkm@localhost>"
DEFAULT_MAX_KB = 200
DEFAULT_TZ = "Europe/Berlin"
IMPORT_FOLDER = "pkm_img_import"
CONFIG_FILE = "config.toml"
FALSE_VALUES = ("0", "false", "no", "off", "nein", "aus")
GIT_CANDIDATES = (
    "/opt/homebrew/bin/git", "/usr/local/bin/git", "/usr/bin/git",
    r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files (x86)\Git\cmd\git.exe",
)
DEFAULT_LANGUAGE = "en"
DOC_LANGUAGES = {
    "en": ("English", ("Result", "Decisions", "Open points", "Context / rationale")),
    "de": ("German", ("Ergebnis", "Entscheidungen", "Offene Punkte", "Kontext / Begründung")),
}
CONFIG_KEYS = (
    "PKM_ROOT", "PKM_VAULT_NAME", "PKM_LANGUAGE", "PKM_VERSIONING", "PKM_GIT", "PKM_GIT_DIR", "PKM_CACHE_DIR",
    "PKM_TZ", "PKM_MAX_KB", "PKM_GIT_AUTHOR", "PKM_IMPORT_DIR", "PKM_INLINE_MAX_KB", "PKM_SVG_MAX_KB",
    "PKM_IMAGE_MAX_MB", "PKM_IMAGE_PARAM_MAX_KB", "PKM_SVG_RASTER", "PKM_LINK_STYLE",
)
WIKI_SECTIONS = {
    "en": ("Summary", ("Content", "Contradictions / open questions", "See also", "Citations")),
    "de": ("Kurzfassung", ("Inhalt", "Widersprüche / offene Fragen", "Siehe auch", "Belege")),
}
LANGUAGE_ALIASES = {"en": "en", "english": "en", "englisch": "en", "de": "de", "german": "de", "deutsch": "de"}
IMAGE_DIR_SUFFIX = "_img"
LINK_STYLES = ("absolute", "relative")  # PKM_LINK_STYLE: links to image files
IMAGE_DEFAULTS = {"PKM_INLINE_MAX_KB": 24, "PKM_SVG_MAX_KB": 200, "PKM_IMAGE_MAX_MB": 5,
                  "PKM_IMAGE_PARAM_MAX_KB": 512}

# Classes *********************************************************************


@dataclass(frozen=True)
class ImageConfig:  # pylint: disable=too-many-instance-attributes
    """Limits and folders for images (specification 4.9, 7.1).

    Attributes:
        inline_max_kb: Limit for embedded images, encoded size (``PKM_INLINE_MAX_KB``).
        svg_max_kb: Complexity limit for SVG after sanitizing (``PKM_SVG_MAX_KB``).
        image_max_mb: Upper limit per image (``PKM_IMAGE_MAX_MB``).
        param_max_kb: Upper limit for ``png_base64`` in one call (``PKM_IMAGE_PARAM_MAX_KB``).
        import_dir: The only folder image files are imported from (``PKM_IMPORT_DIR``).
        svg_raster: Rasterize SVG for ``read_image`` (``PKM_SVG_RASTER``).
        link_style: Links to new image files (``PKM_LINK_STYLE``): ``relative`` to the document (default)
            or ``absolute`` (path from the vault root).
    """

    inline_max_kb: int = 24
    svg_max_kb: int = 200
    image_max_mb: int = 5
    param_max_kb: int = 512
    import_dir: Path | None = None
    svg_raster: bool = False
    link_style: str = "relative"

    def folder_for(self, doc_rel: str) -> str:
        """Folder for the image files of a document: always ``<folder of the document>/<document name>_img`` (4.9).

        ``documents/_attachments/`` is no longer a target (existing files there stay readable).

        Args:
            doc_rel: Path of the document in the vault.

        Returns:
            E.g. ``documents/haus/zisterne_img`` for ``documents/haus/zisterne.md``.
        """
        return image_folder(doc_rel)

    @classmethod
    def from_env(cls, env: Mapping[str, str], root: Path) -> ImageConfig:
        """Read the image settings from the environment.

        Args:
            env: Environment variables.
            root: Vault root (default import folder ``<Vault>/pkm_img_import``).

        Returns:
            The settings.

        Raises:
            PkmError: ``config_error`` for invalid numbers.
        """
        values: dict[str, int] = {}
        for key, default in IMAGE_DEFAULTS.items():
            try:
                values[key] = int(env.get(key) or default)
            except ValueError as exc:
                raise PkmError("config_error", f"{key} must be an integer.") from exc
        import_dir = Path(env.get("PKM_IMPORT_DIR") or root / IMPORT_FOLDER)
        link_style = (env.get("PKM_LINK_STYLE") or "relative").strip().lower()
        if link_style not in LINK_STYLES:
            raise PkmError("config_error",
                           f"PKM_LINK_STYLE must be one of {', '.join(LINK_STYLES)}, not {link_style!r}.")
        return cls(
            inline_max_kb=values["PKM_INLINE_MAX_KB"],
            svg_max_kb=values["PKM_SVG_MAX_KB"],
            image_max_mb=values["PKM_IMAGE_MAX_MB"],
            param_max_kb=values["PKM_IMAGE_PARAM_MAX_KB"],
            import_dir=import_dir.expanduser().resolve(),
            svg_raster=(env.get("PKM_SVG_RASTER") or "").strip().lower() in ("1", "true", "yes", "ja"),
            link_style=link_style,
        )


@dataclass(frozen=True)
class Config:  # pylint: disable=too-many-instance-attributes
    """Runtime configuration of server and CLI.

    Attributes:
        root: Absolute path to the vault (``PKM_ROOT``).
        git_dir: Git directory outside the vault (``PKM_GIT_DIR``).
        cache_dir: Folder for the search index (``PKM_CACHE_DIR``).
        tz: Time zone for timestamps and IDs (``PKM_TZ``).
        max_kb: Size limit for documents and change texts (``PKM_MAX_KB``).
        vault_name: Name of the Obsidian vault for ``obsidian://`` links (``PKM_VAULT_NAME``).
        git_author: Author of the MCP commits (``PKM_GIT_AUTHOR``).
        images: Image settings (4.9).
        versioning: Version control with Git (``PKM_VERSIONING``; off if Git is not installed, 5.4).
        git_exe: Git program (``PKM_GIT``, otherwise found in ``PATH`` or the usual locations).
        language: Main language of documents created in chat and of the wiki, ``en`` or ``de``
            (``PKM_LANGUAGE``).
        config_file: Configuration file that was read, or ``None``.
    """

    root: Path
    git_dir: Path
    cache_dir: Path
    tz: ZoneInfo
    max_kb: int = DEFAULT_MAX_KB
    vault_name: str | None = None
    git_author: str = DEFAULT_AUTHOR
    images: ImageConfig = field(default_factory=ImageConfig)
    versioning: bool = True
    git_exe: str = "git"
    language: str = DEFAULT_LANGUAGE
    config_file: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, search_from: Path | None = None) -> Config:
        """Read the configuration from the environment.

        Values come from the environment, otherwise from the configuration file ``config.toml``
        (``PKM_CONFIG`` or the default folder, written by ``pkm setup``). If ``PKM_ROOT`` is missing in both
        and ``search_from`` is set (CLI), the vault is searched upwards from that folder: it is the first
        folder that contains ``.pkm/state.json``.

        Args:
            env: Environment variables; ``os.environ`` if omitted.
            search_from: Start folder for the vault search when ``PKM_ROOT`` is missing.

        Returns:
            The finished configuration with resolved paths.

        Raises:
            PkmError: ``config_error`` for missing or invalid settings.
        """
        env = os.environ if env is None else env
        home = Path(env["HOME"]) if env.get("HOME") else None
        app = default_app_dir(home)
        config_path = Path(env.get("PKM_CONFIG") or app / CONFIG_FILE).expanduser()
        file_values = read_config_file(config_path)
        env = {**file_values, **env}
        root = _root_from_env(env, search_from)
        git_dir = Path(env.get("PKM_GIT_DIR") or app / "git").expanduser()
        cache_dir = Path(env.get("PKM_CACHE_DIR") or app).expanduser()
        try:
            tz = ZoneInfo(env.get("PKM_TZ") or DEFAULT_TZ)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise PkmError("config_error", f"Invalid time zone PKM_TZ: {exc}") from exc
        try:
            max_kb = int(env.get("PKM_MAX_KB") or DEFAULT_MAX_KB)
        except ValueError as exc:
            raise PkmError("config_error", "PKM_MAX_KB must be an integer.") from exc
        return cls(
            root=root.resolve(),
            git_dir=git_dir.resolve(),
            cache_dir=cache_dir.resolve(),
            tz=tz,
            max_kb=max_kb,
            vault_name=env.get("PKM_VAULT_NAME") or None,
            git_author=env.get("PKM_GIT_AUTHOR") or DEFAULT_AUTHOR,
            images=ImageConfig.from_env(env, root.resolve()),
            versioning=(env.get("PKM_VERSIONING") or "on").strip().lower() not in FALSE_VALUES,
            git_exe=env.get("PKM_GIT") or find_git() or "git",
            language=parse_language(env.get("PKM_LANGUAGE")),
            config_file=config_path if file_values else None,
        )

    # Derived paths ************************************************************

    @property
    def index_path(self) -> Path:
        """Path of the SQLite file of the search index.

        Returns:
            ``PKM_CACHE_DIR/index.db``.
        """
        return self.cache_dir / "index.db"

    @property
    def log_path(self) -> Path:
        """Path of the MCP log.

        Returns:
            ``<Vault>/.pkm/mcp.log``.
        """
        return self.root / ".pkm" / "mcp.log"

    @property
    def state_path(self) -> Path:
        """Path of the processing state.

        Returns:
            ``<Vault>/.pkm/state.json``.
        """
        return self.root / ".pkm" / "state.json"

    @property
    def max_bytes(self) -> int:
        """Size limit in bytes.

        Returns:
            ``max_kb`` mal 1024.
        """
        return self.max_kb * 1024

    # Checks (5.5, 7.1) ********************************************************

    def cache_dir_problem(self) -> str | None:
        """Check whether the search index would lie in the vault.

        Returns:
            Error text if ``PKM_CACHE_DIR`` lies in the vault, otherwise ``None``.
        """
        problem = None
        if _is_within(self.cache_dir, self.root):
            problem = (
                f"PKM_CACHE_DIR ({self.cache_dir}) lies in the vault. The search index must not lie in the "
                "cloud folder (Nextcloud, OneDrive, Google Drive …); please choose a folder outside."
            )
        return problem

    @property
    def import_in_vault(self) -> bool:
        """Whether the import folder is the default folder ``<Vault>/pkm_img_import``.

        Returns:
            ``True`` for the folder in the vault.
        """
        return self.images.import_dir == self.root / IMPORT_FOLDER

    def import_dir_problem(self) -> str | None:
        """Check whether the image import folder is allowed (4.9).

        Allowed are ``<Vault>/pkm_img_import`` and folders outside the vault.

        Returns:
            Error text for another folder in the vault, otherwise ``None``.
        """
        problem = None
        imp = self.images.import_dir
        if imp is not None and _is_within(imp, self.root) and not self.import_in_vault:
            problem = (f"PKM_IMPORT_DIR ({imp}) lies in the vault but not in {IMPORT_FOLDER}/; in the vault only "
                       f"{IMPORT_FOLDER}/ is allowed (4.9).")
        return problem

    def git_dir_problem(self) -> str | None:
        """Check whether the Git directory would lie in the vault.

        Returns:
            Error text if ``PKM_GIT_DIR`` lies in the vault, otherwise ``None``.
        """
        problem = None
        if _is_within(self.git_dir, self.root):
            problem = (
                f"PKM_GIT_DIR ({self.git_dir}) lies in the vault. The Git directory must lie outside "
                "the cloud folder (5.5)."
            )
        return problem

# Functions *******************************************************************


def image_folder(doc_rel: str) -> str:
    """Folder for the image files of a document (4.9): ``<folder of the document>/<document name>_img``.

    Args:
        doc_rel: Path of the document in the vault.

    Returns:
        The folder, e.g. ``documents/haus/zisterne_img``.
    """
    rel = PurePosixPath(doc_rel)
    stem = rel.name[:-3] if rel.name.lower().endswith(".md") else rel.stem
    return str(rel.parent / f"{stem}{IMAGE_DIR_SUFFIX}")


def default_app_dir(home: Path | None = None) -> Path:
    """Default folder for Git directory and search index, depending on the operating system.

    Args:
        home: Home directory; ``Path.home()`` if omitted.

    Returns:
        macOS: ``~/Library/Application Support/pkm``; Windows: ``%APPDATA%/pkm``;
        otherwise ``$XDG_DATA_HOME/pkm`` or ``~/.local/share/pkm``.
    """
    home = home or Path.home()
    if sys.platform == "darwin":
        app = home / "Library" / "Application Support" / "pkm"
    elif sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        app = Path(base) / "pkm" if base else home / "AppData" / "Roaming" / "pkm"
    else:
        base = os.environ.get("XDG_DATA_HOME")
        app = Path(base) / "pkm" if base else home / ".local" / "share" / "pkm"
    return app


def parse_language(value: str | None) -> str:
    """Normalize the document language (``PKM_LANGUAGE``).

    Args:
        value: ``en``/``de`` or the name of the language (English/German, also German names); empty
            means the default.

    Returns:
        ``en`` or ``de``.

    Raises:
        PkmError: ``config_error`` for an unknown language.
    """
    text = (value or "").strip().lower()
    if text and text not in LANGUAGE_ALIASES:
        raise PkmError("config_error", f"PKM_LANGUAGE must be en (English) or de (German), not {value!r}.")
    return LANGUAGE_ALIASES.get(text, DEFAULT_LANGUAGE)


def configured_language(env: Mapping[str, str] | None = None) -> str:
    """Document language from the environment or the configuration file, without a complete configuration.

    Used by the MCP server for its instructions; an unreadable or invalid setting gives the default.

    Args:
        env: Environment variables; ``os.environ`` if omitted.

    Returns:
        ``en`` or ``de``.
    """
    env = os.environ if env is None else env
    home = Path(env["HOME"]) if env.get("HOME") else None
    path = Path(env.get("PKM_CONFIG") or default_app_dir(home) / CONFIG_FILE).expanduser()
    try:
        language = parse_language(env.get("PKM_LANGUAGE") or read_config_file(path).get("PKM_LANGUAGE"))
    except PkmError:
        language = DEFAULT_LANGUAGE
    return language


def read_config_file(path: Path) -> dict[str, str]:
    """Read the configuration file (``config.toml``, flat keys like the environment variables).

    Args:
        path: Path of the file.

    Returns:
        Keys and values as strings (booleans as ``true``/``false``); empty if the file is missing.

    Raises:
        PkmError: ``config_error`` if the file is not valid TOML.
    """
    values: dict[str, str] = {}
    if path.is_file():
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise PkmError("config_error", f"Configuration file {path} cannot be read: {exc}") from exc
        values = {str(k): (str(v).lower() if isinstance(v, bool) else str(v)) for k, v in data.items()
                  if isinstance(v, (str, int, bool))}
    return values


def write_config_file(path: Path, values: dict[str, str | bool]) -> None:
    """Write the configuration file (flat TOML, keys sorted).

    Args:
        path: Path of the file.
        values: Keys and values.
    """
    lines = ["# PKM configuration, written by `pkm setup`. Environment variables take precedence.", ""]
    for key in sorted(values):
        value = values[key]
        text = ("true" if value else "false") if isinstance(value, bool) else '"' + str(value).replace(
            "\\", "\\\\").replace('"', '\\"') + '"'
        lines.append(f"{key} = {text}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def find_git() -> str | None:
    """Find the Git program in ``PATH`` or at the usual locations.

    Returns:
        Absolute path of a working Git or ``None`` if Git is not installed.
    """
    candidates = [c for c in (shutil.which("git"), *GIT_CANDIDATES) if c and Path(c).is_file()]
    found = next((c for c in dict.fromkeys(candidates) if git_works(c)), None)
    return str(Path(found).absolute()) if found else None


def git_works(exe: str) -> bool:
    """Check whether a Git program runs (on macOS ``/usr/bin/git`` is only a stub without the developer tools).

    Args:
        exe: Path of the program.

    Returns:
        ``True`` if ``git --version`` succeeds.
    """
    try:
        ok = subprocess.run([exe, "--version"], capture_output=True, timeout=20, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    return ok


def find_vault(start: Path) -> Path | None:
    """Search the vault upwards from a folder.

    Args:
        start: Folder where the search starts.

    Returns:
        The first folder that contains ``.pkm/state.json``, otherwise ``None``.
    """
    start = start.resolve()
    return next((p for p in [start, *start.parents] if (p / ".pkm" / "state.json").is_file()), None)


def _root_from_env(env: Mapping[str, str], search_from: Path | None) -> Path:
    """Determine the vault path from ``PKM_ROOT`` or by searching.

    Args:
        env: Environment variables.
        search_from: Start folder for the search when ``PKM_ROOT`` is missing.

    Returns:
        Absolute, not yet resolved vault path.

    Raises:
        PkmError: ``config_error`` if there is no valid vault path.
    """
    root_s = env.get("PKM_ROOT")
    if not root_s and search_from is not None:
        found = find_vault(search_from)
        root_s = str(found) if found else None
    if not root_s:
        raise PkmError(
            "config_error",
            "PKM_ROOT is not set (absolute path to the vault) and there is no vault with .pkm/state.json "
            "in the current folder or above.",
        )
    root = Path(root_s).expanduser()
    if not root.is_absolute():
        raise PkmError("config_error", f"PKM_ROOT must be an absolute path: {root_s}")
    return root


def _is_within(child: Path, parent: Path) -> bool:
    """Check whether a path lies inside another one.

    Args:
        child: Path to check.
        parent: Possible parent path.

    Returns:
        ``True`` if ``child`` equals ``parent`` or lies below it.
    """
    return child == parent or parent in child.parents

# Main ************************************************************************
