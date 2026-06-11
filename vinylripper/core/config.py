from pathlib import Path
import json

CONFIG_DIR = Path.home() / ".config" / "vinylripper"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "discogs_token": "",
}


def load_config():
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = CONFIG_PATH.read_text()
        return {**DEFAULT_CONFIG, **json.loads(data)}
    except (FileNotFoundError, ValueError):
        return dict(DEFAULT_CONFIG)


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULT_CONFIG, **config}
    CONFIG_PATH.write_text(json.dumps(merged, indent=2))
