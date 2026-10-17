# SPDX-License-Identifier: GPL-2.0-or-later
"""Write an A4 vector PDF test page with solid K, C, M, Y and gray blocks.

Usage: python3 tools/colorblocks.py out.pdf && lp -d Canon_MG8150 out.pdf

Vector on purpose: macOS cgpdftoraster misrenders the image PDFs that
`sips` makes from PPM files, which looked exactly like a driver bug.
"""
import sys

PX = 72 / 150  # layout is on a 150 dpi grid (1240x1754), converted to points
PAGE_H = 842


def rect(x0, y0, x1, y1, rgb):
    r, g, b = (c / 255 for c in rgb)
    return "%.3f %.3f %.3f rg %.2f %.2f %.2f %.2f re f\n" % (
        r, g, b, x0 * PX, PAGE_H - y1 * PX, (x1 - x0) * PX, (y1 - y0) * PX)


content = "".join([
    rect(100, 100, 1140, 500, (0, 0, 0)),
    rect(100, 600, 600, 1000, (0, 255, 255)),
    rect(640, 600, 1140, 1000, (255, 0, 255)),
    rect(100, 1100, 600, 1500, (255, 255, 0)),
    rect(640, 1100, 1140, 1500, (128, 128, 128)),
]).encode()

objs = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R >>",
    b"<< /Length %d >>\nstream\n" % len(content) + content + b"endstream",
]
out = b"%PDF-1.4\n"
offsets = []
for n, obj in enumerate(objs, 1):
    offsets.append(len(out))
    out += b"%d 0 obj\n" % n + obj + b"\nendobj\n"
xref = len(out)
out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)

with open(sys.argv[1], "wb") as f:
    f.write(out)
