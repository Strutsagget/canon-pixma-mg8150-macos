# SPDX-License-Identifier: GPL-2.0-or-later
"""Color chart for tuning: a 4x4 grid of patches plus black corner markers.

Usage: python3 tools/colorchart.py out.pdf [out.ppm]
The PDF is vector (for the CUPS/Gutenprint path); the PPM is the same chart
at 150 dpi for Canon's cifmg8100. PATCHES is shared with bjpatches.py.
"""
import sys

PATCHES = [
    ("cyan", (0, 255, 255)), ("magenta", (255, 0, 255)), ("yellow", (255, 255, 0)), ("black", (0, 0, 0)),
    ("red", (255, 0, 0)), ("green", (0, 255, 0)), ("blue", (0, 0, 255)), ("webgreen", (0, 128, 0)),
    ("navy", (0, 0, 128)), ("maroon", (128, 0, 0)), ("orange", (255, 128, 0)), ("skin", (230, 180, 150)),
    ("gray25", (192, 192, 192)), ("gray50", (128, 128, 128)), ("gray75", (64, 64, 64)), ("sky", (128, 192, 255)),
]
# Layout on a 150 dpi A4 grid (1240 x 1754 px).
X0, Y0, CELL, PATCH = 120, 150, 250, 210
MARK = 30  # black corner markers define the chart's bounding box for measuring


def rects():
    out = []
    for k, (_, rgb) in enumerate(PATCHES):
        r, c = divmod(k, 4)
        x, y = X0 + c * CELL, Y0 + r * CELL
        out.append((x, y, x + PATCH, y + PATCH, rgb))
    x1, y1 = X0 + 3 * CELL + PATCH, Y0 + 3 * CELL + PATCH
    out.append((X0 - 2 * MARK, Y0 - 2 * MARK, X0 - MARK, Y0 - MARK, (0, 0, 0)))
    out.append((x1 + MARK, y1 + MARK, x1 + 2 * MARK, y1 + 2 * MARK, (0, 0, 0)))
    return out


def write_pdf(path):
    s, h = 72 / 150, 842
    content = "".join(
        "%.4f %.4f %.4f rg %.2f %.2f %.2f %.2f re f\n" % (
            r / 255, g / 255, b / 255, x0 * s, h - y1 * s, (x1 - x0) * s, (y1 - y0) * s)
        for x0, y0, x1, y1, (r, g, b) in rects()).encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R >>",
            b"<< /Length %d >>\nstream\n" % len(content) + content + b"endstream"]
    out, offs = b"%PDF-1.4\n", []
    for n, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % n + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    open(path, "wb").write(out)


def write_ppm(path):
    W, H = 1240, 1754
    px = bytearray(b"\xff" * (W * H * 3))
    for x0, y0, x1, y1, rgb in rects():
        run = bytes(rgb) * (x1 - x0)
        for y in range(y0, y1):
            px[(y * W + x0) * 3:(y * W + x1) * 3] = run
    open(path, "wb").write(b"P6\n%d %d\n255\n" % (W, H) + px)


if __name__ == "__main__":
    write_pdf(sys.argv[1])
    if len(sys.argv) > 2:
        write_ppm(sys.argv[2])
