# PKM with LLM wiki – installer for Windows (PowerShell).
#
# Installs uv (if missing) and the package pkm-tools, then starts `pkm setup`.
# Git is optional: without Git the PKM runs without version control.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/achim0x/pkm-llm-wiki/main/install.ps1 | iex"
#
# Run it again to update. $env:PKM_ARCHIVE overrides the download (URL or path of a ZIP of the repository).
# $env:PKM_SETUP_ARGS passes arguments on to `pkm setup` (e.g. "--vault C:\Users\me\Nextcloud\Vault").

$ErrorActionPreference = "Stop"

$Archive = if ($env:PKM_ARCHIVE) { $env:PKM_ARCHIVE } else { "https://github.com/achim0x/pkm-llm-wiki/archive/refs/heads/main.zip" }
$Bin = Join-Path $env:USERPROFILE ".local\bin"

$Uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $Uv -and (Test-Path (Join-Path $Bin "uv.exe"))) { $Uv = Join-Path $Bin "uv.exe" }
if (-not $Uv) {
    Write-Host "Installing uv (manages Python for the PKM) ..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
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
if ($env:PKM_SETUP_ARGS) { $SetupArgs = $env:PKM_SETUP_ARGS -split " " }
& (Join-Path $Bin "pkm.exe") setup @SetupArgs
$SetupCode = $LASTEXITCODE
Write-Host ""
Write-Host "If the command 'pkm' is not found in a new terminal, run: uv tool update-shell"
if ($SetupCode -ne 0) { throw "pkm setup reported errors (see above)." }
