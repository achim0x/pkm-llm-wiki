#!/bin/sh
# PKM with LLM wiki – installer for macOS (also works on Linux).
#
# Installs uv (if missing) and the package pkm-tools, then starts `pkm setup`.
# Git is optional: without Git the PKM runs without version control.
#
#   curl -LsSf https://github.com/achim0x/pkm-llm-wiki/releases/latest/download/install.sh | sh
#
# Installs the wheel of a GitHub release and checks its SHA-256 before installing; the dependencies are
# pinned to the versions tested for that release (constraints.txt). The copy of this script attached to
# a release knows its version and the checksum of its wheel; the copy in the repository fetches the
# latest release and takes the checksum from its SHA256SUMS.
#
# Run it again to update. Arguments are passed on to `pkm setup` (e.g. --vault <folder>).
# PKM_VERSION installs a certain release (e.g. v0.3.3).
# PKM_ARCHIVE installs from a ZIP of the repository instead (development, another branch) – without check.
# PKM_RELEASE_URL takes the release files from another place (folder or URL; tests), needs PKM_VERSION.
# uv is taken from PATH; otherwise the installer of the pinned uv version PKM_UV_VERSION is used.

set -eu

REPO="achim0x/pkm-llm-wiki"
STAMPED_VERSION="__PKM_VERSION__"      # set by the release workflow
STAMPED_SHA256="__PKM_WHEEL_SHA256__"  # SHA-256 of the wheel of that release
BIN="$HOME/.local/bin"

say() { printf '%s\n' "$*"; }

if command -v uv >/dev/null 2>&1; then
  UV=$(command -v uv)
elif [ -x "$BIN/uv" ]; then
  UV="$BIN/uv"
else
  UV_VERSION="${PKM_UV_VERSION:-0.11.32}"
  say "Installing uv $UV_VERSION (manages Python for the PKM) ..."
  say "  (Alternative: install uv yourself, e.g. 'brew install uv', and run this installer again.)"
  curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" | sh
  UV="$BIN/uv"
fi

if git --version >/dev/null 2>&1; then
  say "Git found: version control will be on."
else
  say "Note: Git is not installed. The PKM will run without version control."
  say "      To turn it on later: install Git (https://git-scm.com/install/, on macOS also"
  say "      'xcode-select --install') and run this installer or 'pkm setup' again."
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fetch() {  # fetch <URL or path> <target>
  case "$1" in
    http://*|https://*|file://*) curl -LsSf "$1" -o "$2" ;;
    *) cp "$1" "$2" ;;
  esac
}

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

if [ -n "${PKM_ARCHIVE:-}" ]; then
  say "Downloading pkm-tools from $PKM_ARCHIVE (PKM_ARCHIVE: no checksum check) ..."
  fetch "$PKM_ARCHIVE" "$TMP/pkm.zip"
  unzip -q "$TMP/pkm.zip" -d "$TMP/src"
  PKG=$(find "$TMP/src" -maxdepth 2 -type d -name pkm-tools | head -n 1)
  if [ -z "$PKG" ]; then
    say "Error: pkm-tools not found in the download."
    exit 1
  fi
  "$UV" tool install --force --reinstall "$PKG"
else
  VERSION="${PKM_VERSION:-}"
  EXPECTED=""
  case "$STAMPED_VERSION" in __*) ;; *)
    if [ -z "$VERSION" ] || [ "$VERSION" = "$STAMPED_VERSION" ]; then
      VERSION="$STAMPED_VERSION"; EXPECTED="$STAMPED_SHA256"
    fi ;;
  esac
  if [ -z "$VERSION" ]; then
    VERSION=$(curl -LsSf "https://api.github.com/repos/$REPO/releases/latest" \
      | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1)
    [ -n "$VERSION" ] || { say "Error: could not find the latest release."; exit 1; }
  fi
  BASE="${PKM_RELEASE_URL:-https://github.com/$REPO/releases/download/$VERSION}"
  WHEEL="pkm_tools-${VERSION#v}-py3-none-any.whl"
  say "Downloading pkm-tools $VERSION ..."
  fetch "$BASE/$WHEEL" "$TMP/$WHEEL"
  fetch "$BASE/constraints.txt" "$TMP/constraints.txt"
  fetch "$BASE/SHA256SUMS" "$TMP/SHA256SUMS"
  if [ -z "$EXPECTED" ]; then
    EXPECTED=$(awk -v f="$WHEEL" '$2 == f || $2 == "*" f {print $1}' "$TMP/SHA256SUMS")
  fi
  EXPECTED_C=$(awk '$2 == "constraints.txt" || $2 == "*constraints.txt" {print $1}' "$TMP/SHA256SUMS")
  if [ -z "$EXPECTED" ] || [ "$(sha256 "$TMP/$WHEEL")" != "$EXPECTED" ]; then
    say "Error: checksum of $WHEEL does not match ($VERSION). Nothing was installed."
    exit 1
  fi
  if [ -z "$EXPECTED_C" ] || [ "$(sha256 "$TMP/constraints.txt")" != "$EXPECTED_C" ]; then
    say "Error: checksum of constraints.txt does not match ($VERSION). Nothing was installed."
    exit 1
  fi
  say "Checksum OK ($VERSION)."
  "$UV" tool install --force --reinstall --constraints "$TMP/constraints.txt" "$TMP/$WHEEL"
fi

say ""
say "Starting the setup ..."
if [ ! -t 0 ] && (exec </dev/tty) 2>/dev/null; then
  "$BIN/pkm" setup "$@" </dev/tty   # started via "curl … | sh": read the answers from the terminal
else
  "$BIN/pkm" setup "$@"
fi
say ""
say "If the command 'pkm' is not found in a new terminal, run: $UV tool update-shell"
