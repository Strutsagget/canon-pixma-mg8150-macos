"""Write an A4 test page (PPM, 150 dpi) with solid K, C, M, Y and gray blocks.

Usage: python3 tools/colorblocks.py out.ppm && sips -s format pdf out.ppm --out out.pdf
"""
import sys

W, H = 1240, 1754
px = bytearray(b"\xff" * (W * H * 3))


def box(x0, y0, x1, y1, rgb):
    run = bytes(rgb) * (x1 - x0)
    for y in range(y0, y1):
        start = (y * W + x0) * 3
        px[start:start + len(run)] = run


box(100, 100, 1140, 500, (0, 0, 0))
box(100, 600, 600, 1000, (0, 255, 255))
box(640, 600, 1140, 1000, (255, 0, 255))
box(100, 1100, 600, 1500, (255, 255, 0))
box(640, 1100, 1140, 1500, (128, 128, 128))

with open(sys.argv[1], "wb") as f:
    f.write(b"P6 %d %d 255\n" % (W, H) + px)
