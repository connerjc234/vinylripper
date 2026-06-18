# Setup script for VinylRipper on Windows
# Run this script from PowerShell as Administrator (for system-wide FFmpeg/PortAudio install)
# Or from a regular PowerShell for per-user install via conda/scoop

param(
    [switch]$SkipSystemDeps,
    [switch]$SkipVenv
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== VinylRipper Windows Setup ===" -ForegroundColor Cyan

# ---- System Dependencies ----
if (-not $SkipSystemDeps) {
    # Check for scoop
    $hasScoop = $null -ne (Get-Command scoop -ErrorAction SilentlyContinue)
    # Check for choco
    $hasChoco = $null -ne (Get-Command choco -ErrorAction SilentlyContinue)

    if (-not $hasScoop -and -not $hasChoco) {
        Write-Host "`nRecommended: Install scoop (package manager) from https://scoop.sh" -ForegroundColor Yellow
        Write-Host "Or install manually:" -ForegroundColor Yellow
        Write-Host "  1. FFmpeg: https://ffmpeg.org/download.html (add to PATH)" -ForegroundColor Yellow
        Write-Host "  2. PortAudio: conda install -c conda-forge portaudio" -ForegroundColor Yellow
        Write-Host "`nProceeding with Python venv + pip install only..."
    }

    # Check for ffmpeg
    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if (-not $ffmpeg) {
        Write-Host "`nFFmpeg not found in PATH." -ForegroundColor Yellow
        if ($hasScoop) {
            Write-Host "Installing FFmpeg via scoop..." -ForegroundColor Green
            scoop install ffmpeg
        } elseif ($hasChoco) {
            Write-Host "Installing FFmpeg via choco (may need admin)..." -ForegroundColor Green
            choco install ffmpeg -y
        } else {
            Write-Host "Please download FFmpeg from https://ffmpeg.org/download.html" -ForegroundColor Red
            Write-Host "Extract and add the bin/ folder to your PATH, then re-run this script." -ForegroundColor Red
        }
    } else {
        Write-Host "FFmpeg found: $($ffmpeg.Source)" -ForegroundColor Green
    }

    # Check for portaudio — may be bundled with sounddevice on Windows
    Write-Host "`nPortAudio is bundled with sounddevice on Windows — no separate install needed." -ForegroundColor Green
}

# ---- Python Virtual Environment ----
if (-not $SkipVenv) {
    $venvPath = Join-Path $RepoRoot ".venv"
    if (-not (Test-Path $venvPath)) {
        Write-Host "`nCreating virtual environment..." -ForegroundColor Cyan
        python -m venv $venvPath
    } else {
        Write-Host "`nVirtual environment already exists." -ForegroundColor Green
    }

    # Activate and install
    $pip = Join-Path $venvPath "Scripts" "pip.exe"
    Write-Host "Installing VinylRipper and dependencies..." -ForegroundColor Cyan
    & $pip install --upgrade pip
    & $pip install -e $RepoRoot

    Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To run VinylRipper:" -ForegroundColor White
    Write-Host "  .\.venv\Scripts\activate" -ForegroundColor Yellow
    Write-Host "  vinylripper" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Or run directly:" -ForegroundColor White
    Write-Host "  .\.venv\Scripts\python -m vinylripper.main" -ForegroundColor Yellow
} else {
    Write-Host "`n=== System deps check complete ===" -ForegroundColor Cyan
}
