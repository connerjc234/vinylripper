#!/usr/bin/env python3
"""Generate a 256x256 VinylRipper icon PNG using only Python stdlib.

Usage: python generate_icon.py [--size N] <output_path>

Creates a vinyl record icon (dark circle with red center label and "VR").
No external dependencies required — uses struct + zlib for raw PNG output.
"""

import argparse
import math
import struct
import sys
import zlib


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    raw = chunk_type + data
    crc = struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
    return struct.pack(">I", len(data)) + raw + crc


def _rgba(r: int, g: int, b: int, a: int = 255) -> tuple[int, int, int, int]:
    return (r, g, b, a)


def build_png(width: int, height: int, pixels: list[int]) -> bytes:
    """Build a valid PNG from a flat RGBA pixel list."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(
        b"IHDR",
        struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0),  # 8-bit RGBA
    )

    raw = b""
    for y in range(height):
        raw += b"\x00"  # filter byte (None)
        for x in range(width):
            idx = (y * width + x) * 4
            raw += bytes(pixels[idx : idx + 4])

    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


def generate_vinyl_icon(size: int) -> bytes:
    """Generate a vinyl record icon as raw RGBA pixel data."""
    cx = cy = size // 2
    max_r = size // 2 - 2
    label_r = size // 5
    hole_r = size // 24
    pixels: list[int] = []

    for y in range(size):
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > max_r:
                # Outside the record — transparent
                pixels.extend(_rgba(0, 0, 0, 0))
            elif dist < hole_r:
                # Spindle hole
                pixels.extend(_rgba(0, 0, 0, 0))
            elif dist < label_r:
                # Red label
                t = dist / label_r
                r = int(229 + (198 - 229) * t)
                g = int(57 + (40 - 57) * t)
                b = int(53 + (40 - 53) * t)
                pixels.extend(_rgba(r, g, b, 255))
            else:
                # Black record body with subtle gradient
                t = (dist - label_r) / (max_r - label_r)
                v = int(42 - t * 12)
                pixels.extend(_rgba(v, v, v, 255))
                # Grooves
                # Thin rings at specific radii for visual texture
                for groove_r in [
                    int(label_r * 1.25),
                    int(label_r * 1.5),
                    int(label_r * 1.75),
                    int(label_r * 2.0),
                    max_r - 4,
                ]:
                    if abs(dist - groove_r) < 0.8:
                        pixels[-4:] = _rgba(v + 8, v + 8, v + 10, 255)
                        break

    return build_png(size, size, pixels)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate VinylRipper icon PNG")
    parser.add_argument("output", help="Output PNG path")
    parser.add_argument("--size", type=int, default=256, help="Icon size (default: 256)")
    args = parser.parse_args()

    png_data = generate_vinyl_icon(args.size)
    with open(args.output, "wb") as f:
        f.write(png_data)
    print(f"Icon written to {args.output} ({args.size}x{args.size})", file=sys.stderr)


if __name__ == "__main__":
    main()
