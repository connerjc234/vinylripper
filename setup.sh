#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing Fedora system dependencies for VinylRipper..."
sudo dnf install -y portaudio-devel python3-devel python3-pip python3-pyqt6 python3-numpy python3-discogs-client

echo "==> Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "==> Installing Python packages..."
pip install --upgrade pip
pip install sounddevice soundfile mutagen requests

echo "==> Done! Activate with: source .venv/bin/activate"
