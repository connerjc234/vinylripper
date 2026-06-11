#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing system dependencies for VinylRipper..."

if command -v dnf &> /dev/null; then
    echo "Detected Fedora/RHEL"
    sudo dnf install -y portaudio-devel python3-devel python3-pip libxcb-cursor0
elif command -v apt &> /dev/null; then
    echo "Detected Debian/Ubuntu/Mint"
    sudo apt update && sudo apt install -y portaudio19-dev python3-dev python3-pip libxcb-cursor0
elif command -v pacman &> /dev/null; then
    echo "Detected Arch"
    sudo pacman -S --needed portaudio python python-pip libxcb-cursor
else
    echo "Unknown distro. Install manually: portaudio, python3-dev, pip, libxcb-cursor0"
    exit 1
fi

echo "==> Creating virtual environment and installing..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

echo ""
echo "  Done! Run:   source .venv/bin/activate"
echo "  Then:        vinylripper"
