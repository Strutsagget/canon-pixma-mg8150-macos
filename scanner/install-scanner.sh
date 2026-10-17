#!/bin/zsh
# Installs the MG8150 eSCL bridge as a per-user LaunchAgent, so the scanner
# shows up in Image Capture and Preview. No sudo needed.
# Requires: brew install sane-backends, and bjnp://<printer-ip> in
# /opt/homebrew/etc/sane.d/pixma.conf.
set -e
HERE="${0:A:h}"
LABEL=se.pija.mg8150-escl
DEST="$HOME/Library/Application Support/MG8150Scanner"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$DEST" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cp "$HERE/escl-bridge.py" "$DEST/"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string><string>-I</string>
    <string>$DEST/escl-bridge.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/mg8150-escl.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Scanner bridge running: Canon PIXMA MG8150 (eSCL on port 8090)"
