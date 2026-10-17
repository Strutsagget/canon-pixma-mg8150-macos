"""Decode a Canon multiraster job (ESC(L / ESC(F / ESC(e) into per-channel
coverage images, to see what a driver actually asks the printer to print.

Usage: python3 tools/bjrender.py job.canon out_prefix
Writes out_prefix-<channel>.pgm (one pixel per data byte, dark = ink).
"""
import struct
import sys

d = open(sys.argv[1], "rb").read()
order = "CMYK"
lines_per_block = 16
rows = {}          # channel -> list of decoded lines (bytes)
y = 0              # current raster line
band = []          # blocks collected for the current band
i = 0


def unpack(b):
    out, cur, p = [], bytearray(), 0
    while p < len(b):
        x = b[p]
        p += 1
        if x == 0x80:
            out.append(bytes(cur))
            cur = bytearray()
        elif x < 128:
            cur += b[p:p + x + 1]
            p += x + 1
        else:
            cur += bytes([b[p]]) * (257 - x)
            p += 1
    return out


def flush_band():
    global y, band
    for ch, blk in zip(order, band):
        lines = unpack(blk)
        dst = rows.setdefault(ch, [])
        for n in range(lines_per_block):
            while len(dst) <= y + n:
                dst.append(b"")
            if n < len(lines):
                dst[y + n] = lines[n]
    y += lines_per_block
    band = []


while True:
    j = d.find(b"\x1b(", i)
    if j < 0:
        break
    c = d[j + 2:j + 3]
    ln = struct.unpack("<H", d[j + 3:j + 5])[0]
    body = d[j + 5:j + 5 + ln]
    i = j + 5 + ln
    if c == b"J":
        lines_per_block = body[0]
    elif c == b"L":
        if band:
            flush_band()
        order = body.decode()
    elif c == b"e":
        if band:
            flush_band()
        y += int.from_bytes(body, "big")
    elif c == b"F":
        band.append(body)
        if len(band) == len(order):
            flush_band()
if band:
    flush_band()

for ch, lines in rows.items():
    w = max((len(l) for l in lines), default=1) or 1
    h = len(lines)
    step = 4  # downscale rows
    img = bytearray()
    out_h = 0
    for r in range(0, h, step):
        row = bytearray(255 for _ in range(w))
        for rr in lines[r:r + step]:
            for x, v in enumerate(rr):
                if v:
                    row[x] = 0
        img += row
        out_h += 1
    with open(f"{sys.argv[2]}-{ch}.pgm", "wb") as f:
        f.write(b"P5 %d %d 255\n" % (w, out_h) + img)
    print(ch, "width", w, "lines", h)
