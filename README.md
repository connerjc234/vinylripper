# VinylRipper

A desktop application for digitizing vinyl records. Record from your turntable, automatically split tracks by detecting silence, look up album metadata from Discogs, and save as tagged FLAC/MP3/AIFF files.

## Download

Get the latest build for your platform from the [Releases page](https://github.com/connerjc234/vinylripper/releases).

| Platform | Package | How to run |
|----------|---------|------------|
| **Windows** | `VinylRipper-Windows-x86_64.zip` | Extract and double-click `VinylRipper.exe` |
| **Linux** | `VinylRipper-Linux-x86_64.AppImage` | `chmod +x` and run — [AppImage](https://appimage.org/) format |

> Windows: The first launch may be slow while Windows Defender scans the binary. This is normal.
>
> Linux: If your distribution doesn't integrate AppImages, install `appimagelauncher` or run via terminal.

No Python, no package managers, no terminal needed. FFmpeg is bundled inside the binary.

## Features

- **Live recording** — Capture audio from any input device with real-time waveform display
- **Auto track splitting** — Detects silence between tracks using FFmpeg; adjustable sensitivity and minimum gap
- **Discogs integration** — Search and fetch album metadata (artist, title, year, label, tracklist, cover art)
- **Vinyl-style numbering** — Automatic A1, A2, B1, B2 track positions with side detection
- **Sub-track/medley support** — Collapses multi-part tracks (A1.a, A1.b) into single entries
- **Multiple output formats** — FLAC (0–8 compression), MP3 (VBR 0–9), AIFF (16/24/32-bit)
- **Audio restoration** — Optional highpass rumble filter (30 Hz) and declicking via FFmpeg
- **Cover art embedding** — Downloads and embeds high-quality artwork automatically
- **Interactive waveform editor** — Drag markers, undo/redo (Ctrl+Z/Ctrl+Y), zoom, pan
- **Persistent settings** — JSON config at `~/.config/vinylripper/config.json` with environment variable overrides
- **Cross-platform** — Native support for Linux, macOS, and Windows

## Requirements

- A **USB turntable** or **audio interface** with line-in
- A [**Discogs Personal Access Token**](https://www.discogs.com/settings/developers) for metadata lookup

### Source install

If you prefer to run from source rather than using the pre-built binaries:

```bash
# Linux
sudo apt install ffmpeg portaudio19-dev libxcb-cursor0   # Debian/Ubuntu
sudo dnf install ffmpeg portaudio-devel                   # Fedora
sudo pacman -S ffmpeg portaudio                           # Arch

# macOS
brew install ffmpeg portaudio

# Windows (scoop — or download manually)
scoop install ffmpeg portaudio

# Then, on any platform:
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
vinylripper
```

See [Troubleshooting](#troubleshooting) below if you run into issues.

## Usage

1. Connect your **USB turntable** (or a standard turntable via a **USB audio interface**)
2. Launch VinylRipper
3. Select your input device from the dropdown
4. Click **Record** → search for your album on Discogs → select the release
5. Start playing your record, click **Stop** when done
6. Adjust split markers if needed (drag, or use Silence/Min Gap sliders)
7. Choose output format (FLAC/MP3/AIFF) and quality from toolbar
8. Click **Split & Export** or **Save As...**

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+Z | Undo marker change |
| Ctrl+Y | Redo marker change |
| Delete | Remove selected marker |
| Scroll | Zoom waveform |
| Drag | Pan waveform (when zoomed) |

## Platform Status

| Platform | Distribution | Notes |
|----------|-------------|-------|
| Linux | AppImage / source | Primary development platform |
| macOS | Homebrew + source | Apple Silicon & Intel |
| Windows | Standalone `.exe` | scoop/choco/conda also available |

## Project Structure

```
vinylripper/
├── main.py                 # Entry point
├── core/                   # Business logic
│   ├── audio_processor.py  # FFmpeg-based audio processing
│   ├── config.py           # Configuration management (JSON + env vars)
│   ├── discogs_client.py   # Discogs API client with sub-track support
│   ├── metadata.py         # Album metadata dataclass with vinyl positions
│   ├── recorder.py         # Audio recording (sounddevice)
│   └── splitter.py         # Silence detection (numpy fallback)
├── ui/                     # PyQt6 GUI
│   ├── main_window.py      # Main application window
│   ├── search_dialog.py    # Discogs search dialog
│   ├── settings_dialog.py  # Settings dialog
│   └── waveform_widget.py  # Live waveform display (undo/redo, minimap)
├── scripts/                # Build & packaging
│   ├── build.py            # PyInstaller builder
│   ├── build_appimage.sh   # Linux AppImage builder
│   ├── download_ffmpeg.py  # Bundles FFmpeg for Windows builds
│   └── appimage/           # AppImage metadata (desktop file, icon, AppRun)
├── docs/                   # GitHub Pages website
├── requirements.txt        # Python dependencies
├── requirements-linux.txt  # Linux system deps
├── requirements-macos.txt  # macOS system deps
└── pyproject.toml          # Build config
```

## Configuration

Settings are stored in `~/.config/vinylripper/config.json` and can be overridden via environment variables:

| Setting | Env Variable | Description |
|---------|--------------|-------------|
| Discogs Token | `VINYLRIPPER_DISCOGS_TOKEN` | Personal Access Token |
| Output Directory | `VINYLRIPPER_OUTPUT_DIR` | Default export folder |
| Output Format | `VINYLRIPPER_OUTPUT_FORMAT` | flac, mp3, aiff |
| FLAC Compression | `VINYLRIPPER_FLAC_COMPRESSION` | 0–8 |
| MP3 Quality | `VINYLRIPPER_MP3_QUALITY` | 0–9 (VBR) |
| Restoration Level | `VINYLRIPPER_RESTORATION_LEVEL` | 0=none, 1=highpass, 2=declick |
| Silence Threshold | `VINYLRIPPER_SILENCE_THRESHOLD` | dB (negative) |
| Min Silence | `VINYLRIPPER_MIN_SILENCE` | seconds |
| Min Track Length | `VINYLRIPPER_MIN_TRACK_LENGTH` | seconds |

## Troubleshooting

### Qt "Could not load platform plugin xcb" (Linux)
```bash
sudo apt install libxcb-cursor0
```

### No audio input devices found
- Make sure your user is in the `audio` group: `sudo usermod -a -G audio $USER` (log out/in after)
- Check PipeWire/PulseAudio is running: `pactl info`
- Try `pavucontrol` to verify input device visibility

### FFmpeg not found
```bash
# Debian/Ubuntu
sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# macOS
brew install ffmpeg

# Windows (choose one)
scoop install ffmpeg
choco install ffmpeg
conda install -c conda-forge ffmpeg
```

### PortAudio errors
```bash
# Debian/Ubuntu
sudo apt install portaudio19-dev

# Fedora
sudo dnf install portaudio-devel

# macOS
brew install portaudio

# Windows — sounddevice bundles PortAudio, usually not needed
scoop install portaudio
```

### Discogs token not working
- Generate a new token at: https://www.discogs.com/settings/developers
- Make sure it's a **Personal Access Token**, not OAuth
- Token needs no special scopes for public data

---

## License

MIT License — see [LICENSE](LICENSE) for details.
