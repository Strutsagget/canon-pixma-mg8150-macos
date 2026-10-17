"""Summarise a Canon BJ/IVEC print job: setup commands and raster structure.

Usage: python3 tools/bjdump.py job.canon
"""
import re
import struct
import sys
from collections import Counter

d = open(sys.argv[1], "rb").read()
i = 0
seq = []
setup = []
while True:
    j = d.find(b"\x1b", i)
    if j < 0:
        break
    if d[j + 1:j + 2] == b"(":
        c = d[j + 2:j + 3].decode("latin1")
        ln = struct.unpack("<H", d[j + 3:j + 5])[0]
        body = d[j + 5:j + 5 + ln]
        seq.append(c)
        if c not in "FAe":
            setup.append(f"ESC({c} len={ln}: {body[:48].hex()}")
        elif c == "A":
            seq[-1] = "A" + body[:1].decode("latin1")
        i = j + 5 + ln
    elif d[j + 1:j + 2] == b"[":
        c = d[j + 2:j + 3].decode("latin1")
        ln = struct.unpack("<H", d[j + 3:j + 5])[0]
        setup.append(f"ESC[{c} len={ln}: {d[j + 5:j + 5 + min(ln, 48)]!r}")
        i = j + 5 + ln
    else:
        setup.append(f"ESC{d[j + 1:j + 2]!r}")
        i = j + 2

for s in setup:
    print(s)
s = " ".join(seq)
print("raster commands:", Counter(x for x in seq if x[0] in "FAe").most_common(12))
print("first raster sequence:", " ".join(x for x in seq if x[0] in "FAe")[:300])
