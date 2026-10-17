# SPDX-License-Identifier: GPL-2.0-or-later
"""Show the internal structure of the first ESC(F raster blocks of a job."""
import struct, sys
d = open(sys.argv[1], "rb").read()
n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
i = 0; k = 0; group = []
while k < n:
    j = d.find(b"\x1b(", i)
    if j < 0: break
    c = d[j+2:j+3]; ln = struct.unpack("<H", d[j+3:j+5])[0]; b = d[j+5:j+5+ln]; i = j+5+ln
    if c == b"e":
        print("ESC(e", b.hex()); continue
    if c != b"F": continue
    # decode packbits lines, 0x80 = end of line
    lines = []; cur = 0; nz = 0; p = 0
    while p < len(b):
        x = b[p]; p += 1
        if x == 0x80: lines.append((cur, nz)); cur = nz = 0; continue
        if x < 128: seg = b[p:p+x+1]; p += x+1
        else: seg = bytes([b[p]]) * (257 - x); p += 1
        cur += len(seg); nz += sum(1 for v in seg if v)
    print(f"F#{k} len={ln} lines={len(lines)} widths={sorted(set(w for w,_ in lines))[:4]} inked_lines={sum(1 for _,z in lines if z)} head={b[:10].hex()}")
    k += 1
