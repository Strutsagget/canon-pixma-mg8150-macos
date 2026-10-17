"""Build an RGB->RGB 3D LUT that makes Gutenprint (Density mode, which is
linear: ink = 1 - value) lay down the same CMY ink as Canon's own driver.

Usage:
  python3 tools/buildlut.py chart out.ppm     # write the 9x9x9 patch chart
  python3 tools/buildlut.py lut canon.job out.lut
The .lut file is N^3 RGB triplets (bytes), red index slowest, preceded by
the 4-byte header b"LUT" + bytes([N]).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bjdensity_lib as bj  # noqa: E402

N = 9
LEVELS = [round(i * 255 / (N - 1)) for i in range(N)]
W, H = 1240, 1754          # A4 at 150 dpi
PITCH, SIZE = 34, 28       # patch pitch and size in px; 27 x 27 grid
COLS = N * 3               # 27 columns: (g, b) varies inside a red block
X0, Y0 = 160, 200
MARK = 20


def patches():
    """(r, g, b) and top-left (x, y) for every patch."""
    out = []
    for ri, r in enumerate(LEVELS):
        for gi, g in enumerate(LEVELS):
            for bi, b in enumerate(LEVELS):
                k = (ri * N + gi) * N + bi
                row, col = divmod(k, COLS)
                out.append(((r, g, b), (X0 + col * PITCH, Y0 + row * PITCH)))
    return out


def markers():
    rows = (N ** 3 + COLS - 1) // COLS
    x1, y1 = X0 + COLS * PITCH, Y0 + rows * PITCH
    return [(X0 - 2 * MARK, Y0 - 2 * MARK, X0 - MARK, Y0 - MARK),
            (x1 + MARK, y1 + MARK, x1 + 2 * MARK, y1 + 2 * MARK)]


def write_chart(path):
    px = bytearray(b"\xff" * (W * H * 3))

    def fill(x0, y0, x1, y1, rgb):
        run = bytes(rgb) * (x1 - x0)
        for y in range(y0, y1):
            px[(y * W + x0) * 3:(y * W + x1) * 3] = run

    for rgb, (x, y) in patches():
        fill(x, y, x + SIZE, y + SIZE, rgb)
    for x0, y0, x1, y1 in markers():
        fill(x0, y0, x1, y1, (0, 0, 0))
    open(path, "wb").write(b"P6\n%d %d\n255\n" % (W, H) + px)


def measure(job):
    lines = bj.decode(open(job, "rb").read())
    k = lines["K"]
    rows = sorted(y for y, ln in k.items() if any(ln))
    top, bottom = rows[0], rows[-1]

    def xs(y):
        ln = k[y]
        hit = [x for x in range(len(ln) * 8) if bj.level("K", ln, x)]
        return hit[0], hit[-1]

    left, right = xs(top)[0], xs(bottom)[1]
    (mx0, my0, _, _), (_, _, mx1, my1) = markers()
    sx, sy = (right - left) / (mx1 - mx0), (bottom - top) / (my1 - my0)
    res = {}
    for rgb, (x, y) in patches():
        m = SIZE * 0.25
        ink = []
        for ch in "CMYK":
            tot = n = 0
            for yy in range(int(top + (y + m - my0) * sy), int(top + (y + SIZE - m - my0) * sy), 2):
                ln = lines.get(ch, {}).get(yy, b"")
                for xx in range(int(left + (x + m - mx0) * sx), int(left + (x + SIZE - m - mx0) * sx), 2):
                    tot += bj.level(ch, ln, xx)
                    n += 1
            ink.append(tot / max(n, 1))
        res[rgb] = ink
    return res


def write_lut(job, path):
    ink = measure(job)
    out = bytearray(b"LUT" + bytes([N]))
    for r in LEVELS:
        for g in LEVELS:
            for b in LEVELS:
                c, m, y, k = ink[(r, g, b)]
                # Canon only uses K in deep shadows; fold it into CMY so the
                # Density-mode GCR settings decide about black on our side.
                c, m, y = (min(1.0, v + k) for v in (c, m, y))
                if k >= 0.8:  # Canon prints black as pure K: keep it pure black
                    c = m = y = 1.0
                out += bytes(round(255 * (1 - v)) for v in (c, m, y))
    open(path, "wb").write(out)
    for probe in [(0, 0, 0), (128, 128, 128), (255, 255, 255), (0, 255, 255), (0, 0, 255)]:
        p = tuple(min(LEVELS, key=lambda L: abs(L - v)) for v in probe)
        print(p, "canon ink C/M/Y/K =", " ".join("%.2f" % v for v in ink[p]))


if __name__ == "__main__":
    if sys.argv[1] == "chart":
        write_chart(sys.argv[2])
    else:
        write_lut(sys.argv[2], sys.argv[3])
