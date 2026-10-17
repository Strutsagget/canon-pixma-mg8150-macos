"""Decode a Canon multiraster job (ESC(L / ESC(F / ESC(e / ESC(J) into lines.

decode(job_bytes) -> {channel: {raster_line: bytes}}
level(channel, line, x) -> ink amount 0..1 at pixel x
K/Y are 1 bit per pixel; C/M are 3 levels packed 5 pixels per byte (base 3),
as declared by ESC(t for the MG8100 plain-paper modes.
"""
import struct


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


def decode(d):
    order, lpb, y, band, i = "CMYK", 16, 0, [], 0
    lines = {}

    def flush():
        nonlocal y, band
        for ch, blk in zip(order, band):
            for n, ln in enumerate(unpack(blk)):
                lines.setdefault(ch, {})[y + n] = ln
        y += lpb
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
            lpb = body[0]
        elif c == b"L":
            if band:
                flush()
            order = body.decode()
        elif c == b"e":
            if band:
                flush()
            # In multiraster mode ESC(e advances in raster blocks, not lines
            # (Canon's job encodes a 400-line gap as e=25 with 16-line blocks).
            y += int.from_bytes(body, "big") * lpb
        elif c == b"F":
            band.append(body)
            if len(band) == len(order):
                flush()
    if band:
        flush()
    return lines


def level(ch, row, x):
    if ch in "CM":
        byte = x // 5
        if byte >= len(row):
            return 0
        return ((row[byte] // 3 ** (4 - x % 5)) % 3) / 2
    byte = x // 8
    if byte >= len(row):
        return 0
    return (row[byte] >> (7 - x % 8)) & 1
