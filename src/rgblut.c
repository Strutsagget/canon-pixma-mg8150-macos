/*
 * rgblut - apply a 3D RGB lookup table to a CUPS raster stream.
 *
 *   rgblut table.lut < in.ras > out.ras
 *
 * Used in front of Gutenprint so the MG8150 lays down the same ink as
 * Canon's own driver (see tools/buildlut.py). Only 8-bit chunky RGB pages
 * are changed; anything else is copied through untouched.
 * Table format: "LUT" + N, then N^3 RGB triplets, red index slowest.
 */
#include <cups/raster.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned char *lut;
static int n;

static int load_lut(const char *path)
{
  FILE *f = fopen(path, "rb");
  unsigned char hdr[4];
  if (!f || fread(hdr, 1, 4, f) != 4 || memcmp(hdr, "LUT", 3) || hdr[3] < 2) {
    if (f) fclose(f);
    return -1;
  }
  n = hdr[3];
  size_t size = (size_t)n * n * n * 3;
  lut = malloc(size);
  int ok = lut && fread(lut, 1, size, f) == size;
  fclose(f);
  return ok ? 0 : -1;
}

/* Trilinear interpolation of one pixel, in place. */
static void map_pixel(unsigned char *px)
{
  float pos[3];
  int i0[3];
  float t[3];
  for (int c = 0; c < 3; c++) {
    pos[c] = px[c] * (n - 1) / 255.0f;
    i0[c] = (int)pos[c];
    if (i0[c] >= n - 1) i0[c] = n - 2;
    t[c] = pos[c] - i0[c];
  }
  float out[3] = {0, 0, 0};
  for (int corner = 0; corner < 8; corner++) {
    int dr = corner >> 2 & 1, dg = corner >> 1 & 1, db = corner & 1;
    float w = (dr ? t[0] : 1 - t[0]) * (dg ? t[1] : 1 - t[1]) * (db ? t[2] : 1 - t[2]);
    const unsigned char *e =
      lut + (((size_t)(i0[0] + dr) * n + (i0[1] + dg)) * n + (i0[2] + db)) * 3;
    out[0] += w * e[0];
    out[1] += w * e[1];
    out[2] += w * e[2];
  }
  for (int c = 0; c < 3; c++)
    px[c] = (unsigned char)(out[c] + 0.5f);
}

int main(int argc, char **argv)
{
  if (argc != 2 || load_lut(argv[1]) != 0) {
    fprintf(stderr, "ERROR: rgblut: cannot load table %s\n", argc > 1 ? argv[1] : "(none)");
    return 1;
  }

  cups_raster_t *in = cupsRasterOpen(0, CUPS_RASTER_READ);
  cups_raster_t *out = cupsRasterOpen(1, CUPS_RASTER_WRITE);
  cups_page_header2_t h;

  while (cupsRasterReadHeader2(in, &h)) {
    if (!cupsRasterWriteHeader2(out, &h))
      return 1;
    int rgb = h.cupsColorSpace == CUPS_CSPACE_RGB && h.cupsBitsPerColor == 8 &&
              h.cupsBitsPerPixel == 24 && h.cupsColorOrder == CUPS_ORDER_CHUNKED;
    unsigned char *line = malloc(h.cupsBytesPerLine);
    unsigned char last_in[3] = {255, 255, 255}, last_out[3] = {255, 255, 255};
    for (unsigned y = 0; y < h.cupsHeight; y++) {
      if (cupsRasterReadPixels(in, line, h.cupsBytesPerLine) != h.cupsBytesPerLine)
        break;
      if (rgb) {
        for (unsigned x = 0; x + 2 < h.cupsBytesPerLine; x += 3) {
          unsigned char *p = line + x;
          if (p[0] == 255 && p[1] == 255 && p[2] == 255)
            continue;                       /* paper white stays white */
          if (memcmp(p, last_in, 3) == 0) { /* runs of one color are common */
            memcpy(p, last_out, 3);
            continue;
          }
          memcpy(last_in, p, 3);
          map_pixel(p);
          memcpy(last_out, p, 3);
        }
      }
      cupsRasterWritePixels(out, line, h.cupsBytesPerLine);
    }
    free(line);
  }
  cupsRasterClose(in);
  cupsRasterClose(out);
  return 0;
}
