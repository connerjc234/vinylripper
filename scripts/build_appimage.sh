#!/usr/bin/env bash
# Build VinylRipper AppImage for Linux.
#
# Usage:
#   bash scripts/build_appimage.sh              # PyInstaller → AppImage
#   bash scripts/build_appimage.sh --skip-install  # use existing PyInstaller build
#
# Prerequisites:
#   - Python 3.11+, PyInstaller (installed by build.py if needed)
#   - rsvg-convert (optional — for icon conversion; falls back to Python PNG gen)
#
# Output: dist/VinylRipper-x86_64.AppImage

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
PYINSTALLER_OUT="$DIST_DIR/VinylRipper"
APPDIR="$DIST_DIR/VinylRipper.AppDir"
APPIMAGE="$DIST_DIR/VinylRipper-Linux-x86_64.AppImage"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

cleanup() {
    [[ -n "${APPIMAGETOOL_TMP:-}" && -f "$APPIMAGETOOL_TMP" ]] && rm -f "$APPIMAGETOOL_TMP"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
SKIP_INSTALL=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-install) SKIP_INSTALL=true ;;
        --help|-h) echo "Usage: $0 [--skip-install]"; exit 0 ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
# Step 1 — Build with PyInstaller (if not already present)
# ---------------------------------------------------------------------------
if [[ ! -x "$PYINSTALLER_OUT/VinylRipper" ]]; then
    info "Building with PyInstaller..."
    PY_ARGS=""
    $SKIP_INSTALL && PY_ARGS="$PY_ARGS --skip-install"
    python3 "$REPO_ROOT/scripts/build.py" $PY_ARGS
else
    info "Using existing PyInstaller build at $PYINSTALLER_OUT"
fi

# ---------------------------------------------------------------------------
# Step 2 — Create AppDir structure
# ---------------------------------------------------------------------------
info "Creating AppDir at $APPDIR ..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR"

# Copy the entire PyInstaller output (executable + _internal/)
cp -r "$PYINSTALLER_OUT"/* "$APPDIR/"

# ---------------------------------------------------------------------------
# Step 3 — AppRun entry point
# ---------------------------------------------------------------------------
cat > "$APPDIR/AppRun" << 'APP_RUN_EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/VinylRipper" "$@"
APP_RUN_EOF
chmod +x "$APPDIR/AppRun"

# ---------------------------------------------------------------------------
# Step 4 — Desktop file
# ---------------------------------------------------------------------------
cp "$REPO_ROOT/scripts/appimage/vinylripper.desktop" "$APPDIR/"

# ---------------------------------------------------------------------------
# Step 5 — Icon (PNG)
# ---------------------------------------------------------------------------
ICON_PNG="$APPDIR/vinylripper.png"
if command -v rsvg-convert &>/dev/null; then
    info "Generating icon via rsvg-convert..."
    rsvg-convert -w 256 -h 256 \
        "$REPO_ROOT/scripts/appimage/vinylripper.svg" \
        -o "$ICON_PNG"
elif python3 -c "from PIL import Image; print('ok')" 2>/dev/null; then
    info "Generating icon via Pillow (from SVG)..."
    python3 -c "
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw
import subprocess, sys
# Fall back to the stdlib generator
sys.exit(1)
" 2>/dev/null && true
    # If Pillow SVG render isn't available, use our stdlib generator
    info "Falling back to Python stdlib icon generator..."
    python3 "$REPO_ROOT/scripts/appimage/generate_icon.py" "$ICON_PNG"
else
    info "Using Python stdlib icon generator..."
    python3 "$REPO_ROOT/scripts/appimage/generate_icon.py" "$ICON_PNG"
fi

if [[ ! -f "$ICON_PNG" ]]; then
    error "Failed to generate icon PNG"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 6 — appimagetool
# ---------------------------------------------------------------------------
info "Locating appimagetool..."
APPIMAGETOOL=""
if command -v appimagetool &>/dev/null; then
    APPIMAGETOOL="$(command -v appimagetool)"
    info "Using system appimagetool at $APPIMAGETOOL"
else
    APPIMAGETOOL_TMP="$(mktemp /tmp/appimagetool-XXXXXX)"
    info "Downloading appimagetool..."
    wget -q -O "$APPIMAGETOOL_TMP" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL_TMP"
    APPIMAGETOOL="$APPIMAGETOOL_TMP"
fi

# ---------------------------------------------------------------------------
# Step 7 — Build the AppImage
# ---------------------------------------------------------------------------
info "Building AppImage..."
export ARCH=x86_64

# APPIMAGE_EXTRACT_AND_RUN=1 lets the AppImage run without FUSE
APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" --no-appstream "$APPDIR" "$APPIMAGE"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
info "AppImage created: $APPIMAGE"
ls -lh "$APPIMAGE"
echo "  └─ $(file "$APPIMAGE" | cut -d: -f2)"
