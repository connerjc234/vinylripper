#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing system dependencies for VinylRipper..."

# Detect distro
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
    echo "Unknown distro. Please install manually: portaudio, python3-dev, pip, libxcb-cursor0"
    exit 1
fi

echo "==> Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "==> Installing Python packages..."
pip install --upgrade pip
pip install sounddevice soundfile mutagen requests pyqt6

echo "==> Done! Activate with: source .venv/bin/activate"
echo "==> Run with: vinylripper"