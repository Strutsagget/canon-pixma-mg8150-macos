# Canon PIXMA MG8150 driver for Apple Silicon macOS

Canon's Mac driver for the MG8150 stops at macOS 10.12 and is Intel-only. This
folder holds a native arm64 build of the open-source Gutenprint driver instead.

- `dist/Gutenprint/` – driver, installed to `/Library/Printers/Gutenprint`
- `dist/Canon-PIXMA-MG8150.ppd` – printer description (A4 default, absolute filter path)
- `install.sh` – installs the driver and adds the queue (`sudo ./install.sh`)

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
