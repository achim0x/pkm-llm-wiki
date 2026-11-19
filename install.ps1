# PKM with LLM wiki – installer for Windows (PowerShell).
#
# Installs uv (if missing) and the package pkm-tools, then starts `pkm setup`.
# Git is optional: without Git the PKM runs without version control.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/achim0x/pkm-llm-wiki/main/install.ps1 | iex"
#
# Run it again to update. $env:PKM_ARCHIVE overrides the download (URL or path of a ZIP of the repository).
# $env:PKM_VAULT passes the vault folder to `pkm setup` (spaces allowed); $env:PKM_SETUP_ARGS passes further
# arguments (quote paths with spaces: '--vault "C:\Users\me\My Vault"').
# uv is taken from PATH; otherwise the installer of the pinned uv version $env:PKM_UV_VERSION is used.

$ErrorActionPreference = "Stop"

$Archive = if ($env:PKM_ARCHIVE) { $env:PKM_ARCHIVE } else { "https://github.com/achim0x/pkm-llm-wiki/archive/refs/heads/main.zip" }
$Bin = Join-Path $env:USERPROFILE ".local\bin"

$Uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $Uv -and (Test-Path (Join-Path $Bin "uv.exe"))) { $Uv = Join-Path $Bin "uv.exe" }
if (-not $Uv) {
    $UvVersion = if ($env:PKM_UV_VERSION) { $env:PKM_UV_VERSION } else { "0.11.32" }
    Write-Host "Installing uv $UvVersion (manages Python for the PKM) ..."
    Write-Host "  (Alternative: install uv yourself, e.g. 'winget install astral-sh.uv', and run this installer again.)"
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/$UvVersion/install.ps1 | iex"
    $Uv = Join-Path $Bin "uv.exe"
}

$Git = Get-Command git -ErrorAction SilentlyContinue
if ($Git) {
    Write-Host "Git found: version control will be on."
} else {
    Write-Host "Note: Git is not installed. The PKM will run without version control."
    Write-Host "      To turn it on later: install Git (https://git-scm.com/install/ or 'winget install Git.Git')"
    Write-Host "      and run this installer or 'pkm setup' again."
}

$Tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("pkm-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Tmp | Out-Null
try {
    Write-Host "Downloading pkm-tools ..."
    $Zip = Join-Path $Tmp "pkm.zip"
    if (Test-Path $Archive) { Copy-Item $Archive $Zip } else { Invoke-WebRequest -Uri $Archive -OutFile $Zip -UseBasicParsing }
    Expand-Archive -Path $Zip -DestinationPath (Join-Path $Tmp "src")
    $Pkg = Get-ChildItem -Path (Join-Path $Tmp "src") -Directory -Recurse -Depth 1 |
        Where-Object { $_.Name -eq "pkm-tools" } | Select-Object -First 1
    if (-not $Pkg) { throw "pkm-tools not found in the download." }
    & $Uv tool install --force --reinstall $Pkg.FullName
    if ($LASTEXITCODE -ne 0) { throw "uv tool install failed." }
} finally {
    Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Starting the setup ..."
$SetupArgs = @()
if ($env:PKM_VAULT) { $SetupArgs += @("--vault", $env:PKM_VAULT) }
if ($env:PKM_SETUP_ARGS) {
    # Split like the shell does, so that quoted paths with spaces stay one argument.
    $Tokens = [System.Management.Automation.PSParser]::Tokenize($env:PKM_SETUP_ARGS, [ref]$null)
    $SetupArgs += $Tokens | Where-Object { $_.Type -in "CommandArgument", "String", "CommandParameter", "Number" } |
        ForEach-Object { $_.Content }
}
& (Join-Path $Bin "pkm.exe") setup @SetupArgs
$SetupCode = $LASTEXITCODE
Write-Host ""
Write-Host "If the command 'pkm' is not found in a new terminal, run: uv tool update-shell"
if ($SetupCode -ne 0) { throw "pkm setup reported errors (see above)." }
