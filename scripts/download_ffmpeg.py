import io
import os
import platform
import shutil
import tarfile
import zipfile
from pathlib import Path
from urllib.request import urlopen

FFMPEG_URLS = {
    "win32": {
        "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "path_in_zip": "ffmpeg-master-latest-win64-gpl/bin",
    },
    "linux": {
        "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
        "path_in_zip": "ffmpeg-master-latest-linux64-gpl/bin",
    },
    "darwin-x86_64": {
        "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-macos-x86_64-gpl.zip",
        "path_in_zip": "ffmpeg-master-latest-macos-x86_64-gpl/bin",
    },
    "darwin-arm64": {
        "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-macos-arm64-gpl.zip",
        "path_in_zip": "ffmpeg-master-latest-macos-arm64-gpl/bin",
    },
}


def _get_platform_key() -> str:
    raw = platform.system().lower()
    if raw == "windows":
        return "win32"
    if raw == "darwin":
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            return "darwin-arm64"
        return "darwin-x86_64"
    return raw


def download_ffmpeg(target_dir: Path) -> tuple[Path, Path]:
    plat = _get_platform_key()
    info = FFMPEG_URLS.get(plat)
    if not info:
        raise RuntimeError(f"Unsupported platform: {plat}")

    target_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_path = target_dir / ("ffmpeg.exe" if plat == "win32" else "ffmpeg")
    ffprobe_path = target_dir / ("ffprobe.exe" if plat == "win32" else "ffprobe")

    if ffmpeg_path.exists() and ffprobe_path.exists():
        print(f"FFmpeg already present at {target_dir}")
        return ffmpeg_path, ffprobe_path

    url = info["url"]
    print(f"Downloading {url}...")

    resp = urlopen(url)
    data = resp.read()
    print(f"Downloaded {len(data) / 1024 / 1024:.1f} MiB")

    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            all_names = zf.namelist()
            prefix = info["path_in_zip"]
            for name in all_names:
                if name.startswith(prefix) and not name.endswith("/"):
                    rel = os.path.relpath(name, prefix)
                    dest = target_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
    elif url.endswith(".tar.xz"):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r|xz") as tf:
            prefix = info["path_in_zip"]
            for member in tf.getmembers():
                if member.name.startswith(prefix) and not member.isdir():
                    rel = os.path.relpath(member.name, prefix)
                    dest = target_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with tf.extractfile(member) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
    else:
        raise RuntimeError(f"Unsupported archive format (not .zip or .tar.xz): {url}")

    for f in target_dir.iterdir():
        if f.name.startswith("ffmpeg") and f.suffix in ("", ".exe"):
            f.chmod(0o755)

    if not ffmpeg_path.exists():
        found = list(target_dir.glob("ffmpeg*"))
        if found:
            found[0].rename(ffmpeg_path)
    if not ffprobe_path.exists():
        found = list(target_dir.glob("ffprobe*"))
        if found:
            found[0].rename(ffprobe_path)

    print(f"FFmpeg: {ffmpeg_path}")
    print(f"FFprobe: {ffprobe_path}")
    return ffmpeg_path, ffprobe_path


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ffmpeg_bin")
    download_ffmpeg(out)
