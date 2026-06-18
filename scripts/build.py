#!/usr/bin/env python3
"""Build VinylRipper standalone executable with PyInstaller.

Usage:
    python scripts/build.py                 # one-folder build
    python scripts/build.py --onefile       # single .exe build
    python scripts/build.py --appimage      # Linux AppImage
    python scripts/build.py --clean         # clean build artifacts
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
BUILD_DIR = REPO_ROOT / "build"
SPEC_PATH = REPO_ROOT / "vinylripper.spec"


def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def install_project():
    print("Installing project and dependencies...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-e", str(REPO_ROOT)]
    )


def download_ffmpeg():
    dest = REPO_ROOT / "ffmpeg_bin"
    subprocess.check_call(
        [sys.executable, str(REPO_ROOT / "scripts" / "download_ffmpeg.py"), str(dest)]
    )


def generate_spec(onefile: bool = False):
    """Write a PyInstaller spec file for VinylRipper."""
    hidden_imports = [
        "PyQt6.QtPlatformIntegration",
        "sounddevice",
        "mutagen",
        "numpy",
        "requests",
        "discogs_client",
        "psutil",
    ]

    exclude = [
        "PyQt6.QtWebEngine",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebChannel",
        "PyQt6.QtPositioning",
        "PyQt6.QtSensors",
        "PyQt6.QtTest",
        "PyQt6.QtBluetooth",
        "PyQt6.QtNfc",
        "PyQt6.QtMultimedia",
        "PyQt6.QtMultimediaWidgets",
        "PyQt6.QtSql",
        "PyQt6.QtXml",
        "PyQt6.QtXmlPatterns",
        "PyQt6.QtHelp",
        "PyQt6.QtDesigner",
        "PyQt6.QtQml",
        "PyQt6.QtQuick",
        "PyQt6.QtQuick3D",
        "PyQt6.QtQuickWidgets",
        "PyQt6.QtRemoteObjects",
        "PyQt6.QtScxml",
        "PyQt6.QtStateMachine",
        "PyQt6.QtCharts",
        "PyQt6.QtDataVisualization",
        "PyQt6.QtGraphs",
        "PyQt6.QtHttpServer",
        "PyQt6.QtSpatialAudio",
        "PyQt6.QtTextToSpeech",
        "PyQt6.QtWebSockets",
        "PyQt6.QtDBus",
        "matplotlib",
        "scipy",
        "tkinter",
        "notebook",
        "jupyter",
        "pandas",
        "setuptools",
        "pip",
    ]

    datas = []
    binaries = []

    ffmpeg_dir = REPO_ROOT / "ffmpeg_bin"
    if ffmpeg_dir.exists():
        for f in ffmpeg_dir.iterdir():
            if f.name.startswith("ffmpeg") or f.name.startswith("ffprobe"):
                binaries.append((str(f), "."))

    is_win = sys.platform == "win32"

    spec = f"""# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['vinylripper/main.py'],
    pathex=[{str(REPO_ROOT)!r}],
    binaries={binaries!r},
    datas={datas!r},
    hiddenimports={hidden_imports!r},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes={exclude!r},
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, cipher=block_cipher)
"""
    if onefile:
        spec += f"""
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VinylRipper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console={False if is_win else True},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='_internal',
)
"""
    else:
        spec += f"""
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VinylRipper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console={False if is_win else True},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VinylRipper',
)
"""
    SPEC_PATH.write_text(spec)
    print(f"Spec written to {SPEC_PATH}")


def run_pyinstaller(onefile: bool = False):
    ensure_pyinstaller()
    generate_spec(onefile=onefile)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--log-level=INFO",
        str(SPEC_PATH),
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=REPO_ROOT)
    print(f"Build complete. Output in {DIST_DIR / 'VinylRipper'}")


def clean():
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"Removed {d}")
    spec = SPEC_PATH
    if spec.exists():
        spec.unlink()
        print(f"Removed {spec}")
    for p in REPO_ROOT.rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    for p in REPO_ROOT.rglob("*.spec"):
        if p.parent == REPO_ROOT:
            p.unlink()


def build_appimage():
    """Wrap PyInstaller output into a Linux AppImage."""
    script = REPO_ROOT / "scripts" / "build_appimage.sh"
    if not script.exists():
        print("build_appimage.sh not found — skipping AppImage build")
        return
    print("Building AppImage...")
    subprocess.check_call(["bash", str(script)])


def main():
    parser = argparse.ArgumentParser(description="Build VinylRipper executable")
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Build single .exe (default on Windows; use --multi-folder to override)",
    )
    parser.add_argument(
        "--multi-folder",
        action="store_true",
        help="Build folder (default on Linux/macOS)",
    )
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts")
    parser.add_argument("--skip-install", action="store_true", help="Skip pip install")
    parser.add_argument(
        "--skip-ffmpeg", action="store_true", help="Skip FFmpeg download"
    )
    parser.add_argument(
        "--appimage",
        action="store_true",
        help="Build PyInstaller folder + Linux AppImage",
    )
    args = parser.parse_args()

    if args.clean:
        clean()
        return

    if not args.skip_install:
        install_project()
    if not args.skip_ffmpeg:
        download_ffmpeg()

    # Default: --onefile on Windows (double-clickable .exe), folder on other platforms
    onefile = (
        args.onefile
        if args.onefile
        else (not args.multi_folder and sys.platform == "win32")
    )
    run_pyinstaller(onefile=onefile)

    if args.appimage:
        build_appimage()


if __name__ == "__main__":
    main()
