"""Ink density per channel inside rectangles of a Canon multiraster job.

Usage: python3 tools/bjdensity.py job.canon
K/Y are 1 bit per pixel; C/M are 3 levels packed 5 pixels per byte (base 3),
as declared by ESC(t for the MG8100 plain-paper modes.
"""
import struct
import sys

d = open(sys.argv[1], "rb").read()
order, lpb, y, band, i = "CMYK", 16, 0, [], 0
lines = {}


def unpack(b):
    out, cur, p = [], bytearray(), 0
    while p < len(b):
        x = b[p]; p += 1
        if x == 0x80:
            out.append(bytes(cur)); cur = bytearray()
        elif x < 128:
            cur += b[p:p + x + 1]; p += x + 1
        else:
            cur += bytes([b[p]]) * (257 - x); p += 1
    return out


def flush():
    global y, band
    for ch, blk in zip(order, band):
        for n, ln in enumerate(unpack(blk)):
            lines.setdefault(ch, {})[y + n] = ln
    y += lpb
    band = []


while True:
    j = d.find(b"\x1b(", i)
    if j < 0:
        break
    c = d[j + 2:j + 3]; ln = struct.unpack("<H", d[j + 3:j + 5])[0]
    body = d[j + 5:j + 5 + ln]; i = j + 5 + ln
    if c == b"J": lpb = body[0]
    elif c == b"L":
        if band: flush()
        order = body.decode()
    elif c == b"e":
        if band: flush()
        y += int.from_bytes(body, "big")
    elif c == b"F":
        band.append(body)
        if len(band) == len(order): flush()
if band: flush()


def level(ch, row, x):
    """Ink amount 0..1 at pixel x of a decoded line."""
    if ch in "CM":
        byte = x // 5
        if byte >= len(row): return 0
        v = row[byte]
        digit = (v // 3 ** (4 - x % 5)) % 3
        return digit / 2
    byte = x // 8
    if byte >= len(row): return 0
    return (row[byte] >> (7 - x % 8)) & 1


ys = sorted(set().union(*[set(v) for v in lines.values()]))
top, bottom = ys[0], ys[-1]
H = bottom - top
# boxes as fractions of the printed content's bounding box (bar on top, 2x2 grid below)
boxes = {"bar": (.1, .9, .05, .2), "cyan": (.1, .4, .35, .5),
         "magenta": (.6, .9, .35, .5), "yellow": (.1, .4, .75, .9), "gray": (.6, .9, .75, .9)}
W = 4500
for name, (x0, x1, y0, y1) in boxes.items():
    res = []
    for ch in "CMYK":
        tot = n = 0
        for yy in range(int(top + y0 * H), int(top + y1 * H), 7):
            row = lines.get(ch, {}).get(yy, b"")
            for x in range(int(x0 * W), int(x1 * W), 7):
                tot += level(ch, row, x); n += 1
        res.append(f"{ch}{tot / max(n, 1):4.0%}")
    print(f"{name:8s}", " ".join(res))
