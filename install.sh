#!/bin/sh
# PKM with LLM wiki – installer for macOS (also works on Linux).
#
# Installs uv (if missing) and the package pkm-tools, then starts `pkm setup`.
# Git is optional: without Git the PKM runs without version control.
#
#   curl -LsSf https://raw.githubusercontent.com/achim0x/pkm-llm-wiki/main/install.sh | sh
#
# Run it again to update. Arguments are passed on to `pkm setup` (e.g. --vault <folder>).
# PKM_ARCHIVE overrides the download (ZIP of the repository, e.g. another branch).

set -eu

ARCHIVE="${PKM_ARCHIVE:-https://github.com/achim0x/pkm-llm-wiki/archive/refs/heads/main.zip}"
BIN="$HOME/.local/bin"

say() { printf '%s\n' "$*"; }

if command -v uv >/dev/null 2>&1; then
  UV=$(command -v uv)
elif [ -x "$BIN/uv" ]; then
  UV="$BIN/uv"
else
  say "Installing uv (manages Python for the PKM) ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
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
say "Downloading pkm-tools ..."
curl -LsSf "$ARCHIVE" -o "$TMP/pkm.zip"
unzip -q "$TMP/pkm.zip" -d "$TMP/src"
PKG=$(find "$TMP/src" -maxdepth 2 -type d -name pkm-tools | head -n 1)
if [ -z "$PKG" ]; then
  say "Error: pkm-tools not found in the download."
  exit 1
fi
"$UV" tool install --force --reinstall "$PKG"

say ""
say "Starting the setup ..."
if [ ! -t 0 ] && (exec </dev/tty) 2>/dev/null; then
  "$BIN/pkm" setup "$@" </dev/tty   # started via "curl … | sh": read the answers from the terminal
else
  "$BIN/pkm" setup "$@"
fi
say ""
say "If the command 'pkm' is not found in a new terminal, run: $UV tool update-shell"
