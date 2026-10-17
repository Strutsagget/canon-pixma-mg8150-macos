# Canon PIXMA MG8150 driver for Apple Silicon macOS

Canon's Mac driver for the MG8150 stops at macOS 10.12 and is Intel-only. This
folder holds a native arm64 build of the open-source Gutenprint driver instead.

- `dist/Gutenprint/` – driver, installed to `/Library/Printers/Gutenprint`
- `dist/Canon-PIXMA-MG8150.ppd` – printer description (A4 default, absolute filter path)
- `install.sh` – installs the driver and adds the queue (`sudo ./install.sh`)

## PPD changes from the generated file

- `*cupsFilter` points at the wrapper `rastertocanon-mg8150` (absolute path).
- A4 default paper size.
- Real printable margins (10/10/9/15 pt) instead of Gutenprint's zero
  margins, otherwise content in the top ~3 mm is cropped (blank text pages).
- Color defaults matched to Canon's own driver (measured with
  `tools/bjdensity.py`): `StpColorCorrection=Density`, `StpGCRLower=900`,
  `StpGCRUpper=1000`, `StpBlackTrans=1000`. Gutenprint's default mixed
  pigment black into every color, which made prints muddy and banded.

## Debugging tools

`tools/canon-ref/build.sh` builds Canon's cnijfilter 3.40 (MG8100 = model 377)
in a `linux/amd64` Docker container to make reference jobs; `bjdump.py`,
`bjblocks.py`, `bjrender.py` and `bjdensity.py` compare jobs. Use the vector
`tools/colorblocks.py` test page: macOS `cgpdftoraster` misrenders image PDFs
made by `sips`, which looks exactly like a driver bug.

## Ink levels

The printer has no SNMP, so macOS can't read supplies on its own. `src/canon-ink.c`
asks the printer over Canon's BJNP protocol (UDP 8611, command `0x20`) and parses
`CIR:` (remaining %) and `CTK:` (`IO` = ink out). The PPD's filter is the wrapper
`rastertocanon-mg8150`, which runs it before and after Gutenprint and emits
`ATTR: marker-*` lines, so Supply Levels updates on every print. From a terminal:

```bash
/Library/Printers/Gutenprint/bin/canon-ink 192.168.1.191
```

Build: `clang -O2 -Wall -Wextra -o dist/Gutenprint/bin/canon-ink src/canon-ink.c`

## Network

The printer is reached over Wi-Fi through LPD (`lpd://192.168.1.191/`). If its IP
changes, give it a DHCP reservation in the router, or update `PRINTER_URI` in
`install.sh` and run it again.

## Rebuilding

Source: `gutenprint-5.3.5.tar.xz` from https://sourceforge.net/projects/gimp-print/
(sha256 `f5a9f47de28530b1ae2069cfbc647a9a641baeeabe809bb0ef2b3ec5b9668d70`).

```bash
./configure --prefix=/Library/Printers/Gutenprint --disable-shared --enable-static \
  --with-modules=static --without-gimp2 --disable-translated-cups-ppds \
  --disable-globalized-cups-ppds --disable-nls --disable-samples \
  --disable-escputil --disable-testpattern
# _DARWIN_C_SOURCE: the build forces _POSIX_C_SOURCE, which hides u_int etc.
# that the macOS SDK's <netinet/ip.h> (pulled in by <cups/http.h>) needs.
make -j8 CPPFLAGS=-D_DARWIN_C_SOURCE
# /usr/libexec/cups is SIP-protected, so redirect the CUPS dirs into the prefix.
make install DESTDIR=$PWD/stage CPPFLAGS=-D_DARWIN_C_SOURCE \
  cups_conf_serverbin=/Library/Printers/Gutenprint/libexec/cups \
  cups_conf_datadir=/Library/Printers/Gutenprint/share/cups
STP_DATA_PATH=stage/Library/Printers/Gutenprint/share/gutenprint/5.3/xml \
  stage/Library/Printers/Gutenprint/sbin/cups-genppd.5.3 -Z -p ppd -l C bjc-PIXMA-MG8150
```

Then in the generated PPD, make `*cupsFilter` point at
`/Library/Printers/Gutenprint/libexec/cups/filter/rastertogutenprint.5.3`
and set the `Default*` page size entries to `A4`.
