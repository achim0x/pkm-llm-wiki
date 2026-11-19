# Security policy

## Reporting a vulnerability

Please do **not** open a public issue for a security problem. Report it privately via GitHub:
**Security → Report a vulnerability** in this repository (private vulnerability reporting). Describe
the problem, the affected version (`pkm --version`) and, if possible, how to reproduce it.

You will get an answer as soon as possible; fixes are published as a new release with a note in
[docs/release-notes.md](docs/release-notes.md).

## Supported versions

Only the latest release receives security fixes. Update by running the installer again (see
[docs/installation.md](docs/installation.md)).

## Scope

pkm-tools runs locally: the MCP servers talk to Claude Desktop over stdio only, have no network access
and only read and write inside the vault, the import folder and the app folder. Content the tools read
is sent to the language model you use. See the section "Security and privacy" in the
[README](README.md#security-and-privacy).
