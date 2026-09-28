#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the extension icons (16/26/42 px PNG) without external deps.

Draws a four-point 'sparkle' with a purple->blue vertical gradient and a
small secondary sparkle, on a transparent background.
"""

import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "src", "extension", "icons")

TOP = (0x6C, 0x4D, 0xFF)     # purple
BOTTOM = (0x2E, 0x9B, 0xFF)  # blue


def _lerp(a, b, t):
    return int(round(a + (b - a) * max(0.0, min(1.0, t))))


def _color_at(y, h):
    t = y / max(1.0, h - 1.0)
    return (_lerp(TOP[0], BOTTOM[0], t),
            _lerp(TOP[1], BOTTOM[1], t),
            _lerp(TOP[2], BOTTOM[2], t))


def _inside_star(x, y, cx, cy, r):
    """Concave four-point star: p-norm with p = 0.55."""
    dx = abs(x - cx)
    dy = abs(y - cy)
    if dx == 0.0 and dy == 0.0:
        return True
    return (dx / r) ** 0.55 + (dy / r) ** 0.55 <= 1.0


def render(size):
    ss = 4  # supersampling factor
    img = [[(0, 0, 0, 0)] * size for _ in range(size)]
    main_r = size * 0.42
    main_cx, main_cy = size * 0.44, size * 0.56
    dot_r = size * 0.13
    dot_cx, dot_cy = size * 0.76, size * 0.24

    for py in range(size):
        for px in range(size):
            coverage = 0
            for sy in range(ss):
                for sx in range(ss):
                    x = px + (sx + 0.5) / ss
                    y = py + (sy + 0.5) / ss
                    if (_inside_star(x, y, main_cx, main_cy, main_r) or
                            (x - dot_cx) ** 2 + (y - dot_cy) ** 2 <= dot_r ** 2):
                        coverage += 1
            if coverage:
                r, g, b = _color_at(py, size)
                a = int(255 * coverage / (ss * ss))
                img[py][px] = (r, g, b, a)
    return img


def write_png(path, img):
    size = len(img)
    raw = bytearray()
    for row in img:
        raw.append(0)  # filter: none
        for r, g, b, a in row:
            raw.extend((r, g, b, a))

    def chunk(tag, data):
        block = tag + data
        return (struct.pack(">I", len(data)) + block +
                struct.pack(">I", zlib.crc32(block) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


def main():
    os.makedirs(OUT, exist_ok=True)
    for size in (16, 26, 42):
        write_png(os.path.join(OUT, "ai_%d.png" % size), render(size))
        print("wrote %s/ai_%d.png" % (OUT, size))


if __name__ == "__main__":
    main()
