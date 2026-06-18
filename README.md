# VinylRipper

> **⚠️ Work in Progress** — This project is under active development. Features may change, bugs exist, and the API is not stable yet.

A desktop application for digitizing vinyl records. Record from your turntable, automatically split tracks by detecting silence, look up album metadata from Discogs, and save as tagged FLAC/MP3/AIFF files.

## Features

- **Live recording** — Capture audio from any input device with real-time waveform display
- **Auto track splitting** — Detects silence between tracks using FFmpeg; adjustable sensitivity and minimum gap
- **Discogs integration** — Search and fetch album metadata (artist, title, year, label, tracklist, cover art)
- **Vinyl-style numbering** — Automatic A1, A2, B1, B2 track positions with side detection
- **Sub-track/medley support** — Collapses multi-part tracks (A1.a, A1.b) into single entries
- **Multiple output formats** — FLAC (0-8 compression), MP3 (VBR 0-9), AIFF (16/24/32-bit)
- **Audio restoration** — Optional highpass rumble filter (30Hz) and declicking via FFmpeg
- **Cover art embedding** — Downloads and embeds high-quality artwork automatically
- **Interactive waveform editor** — Drag markers, undo/redo (Ctrl+Z/Ctrl+Y), zoom, pan
- **Persistent settings** — JSON config with environment variable overrides
- **Cross-platform** — Native support for Linux, macOS, and Windows

## Download (Windows)

Grab the latest `VinylRipper-Windows-x86_64.zip` from the [Releases page](https://github.com/connerjc234/vinylripper/releases).

Inside the zip is `VinylRipper.exe` — double-click it. No Python, no terminal, no package managers needed. FFmpeg is bundled inside the exe.

> The first launch may be slow while Windows Defender scans the binary. This is normal.

## Requirements (for source installs)

- A **USB turntable** or **audio interface** with line-in to connect your turntable
- Python 3.11+
- **FFmpeg** (system library for audio processing & format conversion)
- PortAudio (system library for audio capture)

## Installation

### Linux (Debian/Ubuntu/Mint)
```bash
sudo apt install ffmpeg portaudio19-dev libxcb-cursor0
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
vinylripper
```

### Linux (Fedora/RHEL)
```bash
sudo dnf install ffmpeg portaudio-devel
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
vinylripper
```

### Linux (Arch)
```bash
sudo pacman -S ffmpeg portaudio
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
vinylripper
```

### macOS (Homebrew)
```bash
brew install ffmpeg portaudio
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
vinylripper
```

### Windows
```powershell
# Option A: Using scoop (recommended — easiest)
# Install scoop from https://scoop.sh first, then:
scoop install ffmpeg portaudio
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper
python -m venv .venv
.venv\Scripts\activate
pip install -e .
vinylripper

# Option B: Using conda
conda create -n vinylripper python=3.11
conda activate vinylripper
conda install -c conda-forge portaudio
# Download FFmpeg from https://ffmpeg.org/download.html and add to PATH
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper
pip install -e .
vinylripper

# Option C: Automated setup script
# Run from PowerShell in the vinylripper directory:
.\setup.ps1
.\.venv\Scripts\activate
vinylripper
```

You'll need a [Discogs Personal Access Token](https://www.discogs.com/settings/developers) for metadata lookup.

## Usage

1. Connect your **USB turntable** (or a standard turntable via a **USB audio interface**) to your computer
2. Launch `vinylripper`
3. Select your input device from the dropdown
4. Click **Record** → search for your album on Discogs → select the release
5. Start playing your record, click **Stop** when done
6. Adjust split markers if needed (drag, or use Silence/Min Gap sliders)
7. Choose output format (FLAC/MP3/AIFF) and quality from toolbar
8. Click **Split & Export** or **Save As...**

### Keyboard Shortcuts
- **Ctrl+Z** — Undo marker change
- **Ctrl+Y** — Redo marker change
- **Delete** — Remove selected marker (when implemented)
- **Scroll** — Zoom waveform
- **Drag** — Pan waveform (when zoomed)

## Platform Status

| Platform | Status | Notes |
|----------|--------|-------|
| Linux (Debian/Ubuntu/Fedora/Arch) | ✅ Tested | Primary development platform |
| macOS (Apple Silicon & Intel) | ✅ Tested | Homebrew FFmpeg + PortAudio |
| Windows | ✅ Tested | scoop/choco/conda install; see instructions below |

## Screenshots

*Coming soon...*

## Project Structure

```
vinylripper/
├── main.py                 # Entry point
├── core/                   # Business logic
│   ├── audio_processor.py # FFmpeg-based audio processing
│   ├── config.py          # Configuration management (JSON + env)
│   ├── discogs_client.py  # Discogs API client (sub-track support)
│   ├── metadata.py        # Album metadata dataclass (vinyl positions)
│   ├── recorder.py        # Audio recording (sounddevice)
│   └── splitter.py        # Silence detection (numpy fallback)
├── ui/                    # PyQt6 GUI
│   ├── main_window.py     # Main application window
│   ├── search_dialog.py   # Discogs search dialog
│   ├── settings_dialog.py # Settings dialog
│   └── waveform_widget.py # Live waveform display (undo/redo, minimap)
├── docs/                  # GitHub Pages website
├── requirements.txt       # Python dependencies
├── requirements-linux.txt # Linux system deps
├── requirements-macos.txt # macOS system deps
└── pyproject.toml         # Build config
```

## Configuration

Settings are stored in `~/.config/vinylripper/config.json` and can be overridden via environment variables:

| Setting | Env Variable | Description |
|---------|--------------|-------------|
| Discogs Token | `VINYLRIPPER_DISCOGS_TOKEN` | Personal Access Token |
| Output Directory | `VINYLRIPPER_OUTPUT_DIR` | Default export folder |
| Output Format | `VINYLRIPPER_OUTPUT_FORMAT` | flac, mp3, aiff |
| FLAC Compression | `VINYLRIPPER_FLAC_COMPRESSION` | 0-8 |
| MP3 Quality | `VINYLRIPPER_MP3_QUALITY` | 0-9 (VBR) |
| Restoration Level | `VINYLRIPPER_RESTORATION_LEVEL` | 0=none, 1=highpass, 2=declick |
| Silence Threshold | `VINYLRIPPER_SILENCE_THRESHOLD` | dB (negative) |
| Min Silence | `VINYLRIPPER_MIN_SILENCE` | seconds |
| Min Track Length | `VINYLRIPPER_MIN_TRACK_LENGTH` | seconds |

## Troubleshooting

### Qt "Could not load platform plugin xcb" (Linux Mint/Ubuntu)
```bash
sudo apt install libxcb-cursor0
```

### No audio input devices found
- Make sure your user is in the `audio` group: `sudo usermod -a -G audio $USER` (log out/in after)
- Check PipeWire/PulseAudio is running: `pactl info`
- Try `pavucontrol` to verify input device visibility

### FFmpeg not found
```bash
# Fedora
sudo dnf install ffmpeg

# Debian/Ubuntu/Mint
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows (choose one)
scoop install ffmpeg          # via scoop
choco install ffmpeg          # via chocolatey
conda install -c conda-forge ffmpeg  # via conda
# Or download from https://ffmpeg.org/download.html and add to PATH
```

### PortAudio errors
```bash
# Fedora
sudo dnf install portaudio-devel

# Debian/Ubuntu/Mint
sudo apt install portaudio19-dev

# macOS
brew install portaudio

# Windows
scoop install portaudio       # via scoop
choco install portaudio       # via chocolatey
conda install -c conda-forge portaudio  # via conda
# Note: sounddevice bundles PortAudio on Windows, so this may not be needed.
```

### Discogs token not working
- Generate a new token at: https://www.discogs.com/settings/developers
- Make sure it's a **Personal Access Token**, not OAuth
- Token needs no special scopes for public data

---

## Development Status

This is a **personal learning project** — I'm building it to learn Python, PyQt, audio processing, and GUI development. Expect:

- Breaking changes
- Incomplete features
- Occasional crashes
- Messy code in places

Feel free to watch the repo or open issues, but don't rely on this for anything critical yet.

## License

MIT License — see [LICENSE](LICENSE) for details.
