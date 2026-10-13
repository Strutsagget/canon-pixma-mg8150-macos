#!/bin/bash
# Installs the self-built Gutenprint driver and adds the Canon PIXMA MG8150.
# Run with: sudo ./install.sh
set -euo pipefail

PRINTER_NAME="Canon_MG8150"
PRINTER_URI="lpd://192.168.1.191/"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Please run with sudo: sudo $0" >&2
  exit 1
fi

# 1. Driver files. CUPS refuses filters that aren't owned by root or are
#    writable by others, so ownership and permissions matter here.
rm -rf /Library/Printers/Gutenprint
cp -R "$HERE/dist/Gutenprint" /Library/Printers/Gutenprint
chown -R root:wheel /Library/Printers/Gutenprint
chmod -R go-w /Library/Printers/Gutenprint
xattr -r -d com.apple.quarantine /Library/Printers/Gutenprint 2>/dev/null || true

# Ink-level poller. Filters can't reach the network (CUPS sandbox), so a
# LaunchDaemon caches the levels where the filter can read them.
mkdir -p /Library/Printers/Gutenprint/var
chown _lp:_lp /Library/Printers/Gutenprint/var
PLIST=/Library/LaunchDaemons/se.pija.canon-ink.plist
launchctl bootout system "$PLIST" 2>/dev/null || true
PRINTER_HOST="${PRINTER_URI#lpd://}"; PRINTER_HOST="${PRINTER_HOST%%/*}"
sed "s#192\.168\.1\.191#$PRINTER_HOST#" "$HERE/dist/se.pija.canon-ink.plist" > "$PLIST"
chown root:wheel "$PLIST"
chmod 644 "$PLIST"
launchctl bootstrap system "$PLIST"

# 2. Printer queue. lpadmin copies the PPD into /etc/cups/ppd itself.
lpadmin -p "$PRINTER_NAME" -E \
  -v "$PRINTER_URI" \
  -P "$HERE/dist/Canon-PIXMA-MG8150.ppd" \
  -D "Canon PIXMA MG8150" \
  -L "Gutenprint 5.3.5 (self-built)" \
  -o printer-is-shared=false
lpoptions -d "$PRINTER_NAME"

echo "Installed. Queue: $PRINTER_NAME -> $PRINTER_URI"
lpstat -p "$PRINTER_NAME" -v "$PRINTER_NAME"
