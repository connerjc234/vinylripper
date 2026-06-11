# VinylRipper

> **⚠️ Work in Progress** — This project is under active development. Features may change, bugs exist, and the API is not stable yet.

A desktop application for digitizing vinyl records. Record from your turntable, automatically split tracks by detecting silence, look up album metadata from Discogs, and save as tagged FLAC files.

## Features

- **Live recording** — Capture audio from any input device with real-time waveform display
- **Auto track splitting** — Detects silence between tracks; adjustable sensitivity and minimum gap
- **Discogs integration** — Search and fetch album metadata (artist, title, year, label, tracklist, cover art)
- **FLAC with embedded tags** — Saves metadata and cover art directly in the audio file
- **Multiple formats** — FLAC, WAV, OGG, AIFF, AU, RAW

## Requirements

- Python 3.11+
- PortAudio (system library for audio capture)

## Installation

### Quick start (Linux — Debian/Ubuntu/Mint)
```bash
sudo apt install portaudio19-dev libxcb-cursor0
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
vinylripper
```

Or run the setup script: `bash setup.sh`

### Linux (Fedora/RHEL)
```bash
sudo dnf install portaudio-devel
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
vinylripper
```

### macOS
```bash
brew install portaudio
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
vinylripper
```

### Windows
```powershell
conda create -n vinylripper python=3.11
conda activate vinylripper
conda install -c conda-forge portaudio
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper
python -m venv .venv
.venv\Scripts\activate
pip install -e .
vinylripper
```

You'll need a [Discogs Personal Access Token](https://www.discogs.com/settings/developers) for metadata lookup.

## Usage

1. Connect your turntable to your computer's line-in or USB audio interface
2. Launch `vinylripper`
3. Select your input device from the dropdown
4. Click **Record** → search for your album on Discogs → select the release
5. Start playing your record, click **Stop** when done
6. Adjust split markers if needed, then **Split Tracks** or **Save As...**

## Platform Status

| Platform | Status | Notes |
|----------|--------|-------|
| Linux (Fedora/Debian) | ✅ Tested | Primary development platform |
| macOS | ⚠️ Untested | Should work with Homebrew PortAudio |
| Windows | ⚠️ Untested | Requires conda or manual PortAudio setup |

## Screenshots

*Coming soon...*

## Project Structure

```
vinylripper/
├── main.py                 # Entry point
├── core/                   # Business logic
│   ├── config.py          # Configuration management
│   ├── discogs_client.py  # Discogs API client
│   ├── metadata.py        # Album metadata dataclass
│   ├── recorder.py        # Audio recording
│   └── splitter.py        # Silence detection & track splitting
├── ui/                    # PyQt6 GUI
│   ├── main_window.py     # Main application window
│   ├── search_dialog.py   # Discogs search dialog
│   └── waveform_widget.py # Live waveform display
├── docs/                  # GitHub Pages website
├── requirements.txt       # Linux dependencies
├── requirements-macos.txt # macOS dependencies
└── requirements-windows.txt # Windows dependencies
```

## Troubleshooting

### Qt "Could not load platform plugin xcb" (Linux Mint/Ubuntu)
```bash
sudo apt install libxcb-cursor0
```

### No audio input devices found
- Make sure your user is in the `audio` group: `sudo usermod -a -G audio $USER` (log out/in after)
- Check PipeWire/PulseAudio is running: `pactl info`
- Try `pavucontrol` to verify input device visibility

### PortAudio errors
```bash
# Fedora
sudo dnf install portaudio-devel

# Debian/Ubuntu/Mint
sudo apt install portaudio19-dev

# macOS
brew install portaudio

# Windows (conda)
conda install -c conda-forge portaudio
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