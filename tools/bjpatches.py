"""Measure ink per channel in each colorchart.py patch of a Canon job.

Usage: python3 tools/bjpatches.py job.canon [job2.canon ...]
The chart's black corner markers give its bounding box, so jobs with
different margins (Canon vs Gutenprint) are measured at the same spots.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import colorchart  # noqa: E402
import bjdensity_lib as bj  # noqa: E402


def measure(path):
    lines = bj.decode(open(path, "rb").read())
    k = lines["K"]
    rows = sorted(y for y, ln in k.items() if any(ln))
    top, bottom = rows[0], rows[-1]

    def kx(y):
        ln = k[y]
        xs = [x for x in range(len(ln) * 8) if bj.level("K", ln, x)]
        return xs[0], xs[-1]

    left, _ = kx(top)
    _, right = kx(bottom)
    # chart coordinates (150 dpi px) of the marker extremes
    rs = colorchart.rects()
    cx0, cy0 = rs[-2][0], rs[-2][1]
    cx1, cy1 = rs[-1][2], rs[-1][3]
    sx = (right - left) / (cx1 - cx0)
    sy = (bottom - top) / (cy1 - cy0)
    out = {}
    for (name, _), (x0, y0, x1, y1, _) in zip(colorchart.PATCHES, rs):
        m = 0.25  # sample the middle half of the patch
        px0, px1 = x0 + (x1 - x0) * m, x1 - (x1 - x0) * m
        py0, py1 = y0 + (y1 - y0) * m, y1 - (y1 - y0) * m
        res = {}
        for ch in "CMYK":
            tot = n = 0
            for yy in range(int(top + (py0 - cy0) * sy), int(top + (py1 - cy0) * sy), 5):
                ln = lines.get(ch, {}).get(yy, b"")
                for xx in range(int(left + (px0 - cx0) * sx), int(left + (px1 - cx0) * sx), 5):
                    tot += bj.level(ch, ln, xx)
                    n += 1
            res[ch] = tot / max(n, 1)
        out[name] = res
    return out


if __name__ == "__main__":
    results = [(os.path.basename(p), measure(p)) for p in sys.argv[1:]]
    print("%-9s" % "patch" + "".join("  %-22s" % name[:22] for name, _ in results))
    for name, _ in colorchart.PATCHES:
        row = "%-9s" % name
        for _, r in results:
            v = r[name]
            row += "  " + " ".join("%s%3.0f" % (ch, v[ch] * 100) for ch in "CMYK")
        print(row)
