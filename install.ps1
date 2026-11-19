# PKM with LLM wiki – installer for Windows (PowerShell).
#
# Installs uv (if missing) and the package pkm-tools, then starts `pkm setup`.
# Git is optional: without Git the PKM runs without version control.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://github.com/achim0x/pkm-llm-wiki/releases/latest/download/install.ps1 | iex"
#
# Installs the wheel of a GitHub release and checks its SHA-256 before installing; the dependencies are
# pinned to the versions tested for that release (constraints.txt). The copy of this script attached to
# a release knows its version and the checksum of its wheel; the copy in the repository fetches the
# latest release and takes the checksum from its SHA256SUMS.
#
# Run it again to update. $env:PKM_VERSION installs a certain release (e.g. v0.3.3).
# $env:PKM_ARCHIVE installs from a ZIP of the repository instead (URL or path; development) – without check.
# $env:PKM_RELEASE_URL takes the release files from another place (folder or URL; tests), needs PKM_VERSION.
# $env:PKM_VAULT passes the vault folder to `pkm setup` (spaces allowed); $env:PKM_SETUP_ARGS passes further
# arguments (quote paths with spaces: '--vault "C:\Users\me\My Vault"').
# uv is taken from PATH; otherwise the installer of the pinned uv version $env:PKM_UV_VERSION is used.

$ErrorActionPreference = "Stop"

$Repo = "achim0x/pkm-llm-wiki"
$StampedVersion = "__PKM_VERSION__"      # set by the release workflow
$StampedSha256 = "__PKM_WHEEL_SHA256__"  # SHA-256 of the wheel of that release
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

function Get-PkmFile([string]$Source, [string]$Target) {
    if ($Source -match "^https?://") { Invoke-WebRequest -Uri $Source -OutFile $Target -UseBasicParsing }
    else { Copy-Item $Source $Target }
}

function Get-Sha256([string]$Path) { (Get-FileHash -Algorithm SHA256 $Path).Hash.ToLower() }

function Get-SumOf([string]$Sums, [string]$Name) {
    foreach ($Line in Get-Content $Sums) {
        $Parts = $Line -split "\s+", 2
        if ($Parts.Count -eq 2 -and $Parts[1].TrimStart("*") -eq $Name) { return $Parts[0].ToLower() }
    }
    return ""
}

$Tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("pkm-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Tmp | Out-Null
try {
    if ($env:PKM_ARCHIVE) {
        Write-Host "Downloading pkm-tools from $env:PKM_ARCHIVE (PKM_ARCHIVE: no checksum check) ..."
        $Zip = Join-Path $Tmp "pkm.zip"
        Get-PkmFile $env:PKM_ARCHIVE $Zip
        Expand-Archive -Path $Zip -DestinationPath (Join-Path $Tmp "src")
        $Pkg = Get-ChildItem -Path (Join-Path $Tmp "src") -Directory -Recurse -Depth 1 |
            Where-Object { $_.Name -eq "pkm-tools" } | Select-Object -First 1
        if (-not $Pkg) { throw "pkm-tools not found in the download." }
        & $Uv tool install --force --reinstall $Pkg.FullName
    } else {
        $Version = $env:PKM_VERSION
        $Expected = ""
        if (-not $StampedVersion.StartsWith("__") -and (-not $Version -or $Version -eq $StampedVersion)) {
            $Version = $StampedVersion
            $Expected = $StampedSha256.ToLower()
        }
        if (-not $Version) {
            $Version = (Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest").tag_name
            if (-not $Version) { throw "Could not find the latest release." }
        }
        $Base = if ($env:PKM_RELEASE_URL) { $env:PKM_RELEASE_URL } else { "https://github.com/$Repo/releases/download/$Version" }
        $WheelName = "pkm_tools-$($Version.TrimStart('v'))-py3-none-any.whl"
        $Wheel = Join-Path $Tmp $WheelName
        $Constraints = Join-Path $Tmp "constraints.txt"
        $Sums = Join-Path $Tmp "SHA256SUMS"
        Write-Host "Downloading pkm-tools $Version ..."
        Get-PkmFile "$Base/$WheelName" $Wheel
        Get-PkmFile "$Base/constraints.txt" $Constraints
        Get-PkmFile "$Base/SHA256SUMS" $Sums
        if (-not $Expected) { $Expected = Get-SumOf $Sums $WheelName }
        $ExpectedConstraints = Get-SumOf $Sums "constraints.txt"
        if (-not $Expected -or (Get-Sha256 $Wheel) -ne $Expected) {
            throw "Checksum of $WheelName does not match ($Version). Nothing was installed."
        }
        if (-not $ExpectedConstraints -or (Get-Sha256 $Constraints) -ne $ExpectedConstraints) {
            throw "Checksum of constraints.txt does not match ($Version). Nothing was installed."
        }
        Write-Host "Checksum OK ($Version)."
        & $Uv tool install --force --reinstall --constraints $Constraints $Wheel
    }
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
