"""Write an A4 PDF with Helvetica text from 6 to 72 pt, black and in color.

Usage: python3 tools/textsizes.py out.pdf && lp -d Canon_MG8150 out.pdf
"""
import sys

SIZES = (6, 8, 10, 12, 14, 18, 24, 36, 48, 72)
SAMPLE = "Hej! Snabba bruna räven åt öl – 0123456789"


def pdf_string(s):
    s = s.replace("–", "-")  # WinAnsi has an en dash, keep it simple
    b = s.encode("cp1252")
    return b"(" + b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


lines = []
y = 800
for size in SIZES:
    y -= size * 1.25
    text = SAMPLE if size < 36 else "ÅÄÖ åäö" + (" Hej!" if size < 72 else "")
    lines.append(b"BT /F1 %d Tf 0 0 0 rg 40 %.1f Td %s Tj ET" % (size, y, pdf_string(f"{size} pt {text}")))
y -= 30
for size, rgb, label in ((14, "0 0 1", "Blå text"), (14, "1 0 0", "Röd text"),
                         (14, "0 0.5 0", "Grön text"), (14, "0.5 0.5 0.5", "Grå text")):
    y -= size * 1.6
    lines.append(b"BT /F1 %d Tf %s rg 40 %.1f Td %s Tj ET" % (size, rgb.encode(), y, pdf_string(label)))
lines.append(b"BT /F2 10 Tf 0 0 0 rg 40 60 Td %s Tj ET" % pdf_string(
    "Times 10 pt: Canon PIXMA MG8150 via Gutenprint 5.3.5 på Apple Silicon"))
content = b"\n".join(lines)

font = b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>"
objs = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
    b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>",
    b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
    font % b"Helvetica",
    font % b"Times-Roman",
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
