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
- Linux (PipeWire or ALSA)
- PortAudio development libraries

## Installation

```bash
# Clone the repository
git clone https://github.com/connerjc234/vinylripper.git
cd vinylripper

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Install system dependencies (Fedora)
sudo dnf install portaudio-devel

# Run the app
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
└── docs/                  # GitHub Pages website
```

## Development Status

This is a **personal learning project** — I'm building it to learn Python, PyQt, audio processing, and GUI development. Expect:

- Breaking changes
- Incomplete features
- Occasional crashes
- Messy code in places

Feel free to watch the repo or open issues, but don't rely on this for anything critical yet.

## License

MIT License — see [LICENSE](LICENSE) for details.