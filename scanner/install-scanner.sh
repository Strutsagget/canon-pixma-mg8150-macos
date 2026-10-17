#!/bin/zsh
# Builds "MG8150 Scanner.app" (a tiny launcher for the eSCL bridge) into
# ~/Applications and runs it as a per-user LaunchAgent, so the scanner shows
# up in Image Capture and Preview. No sudo needed.
#
# The app wrapper is required: macOS only grants Local Network access to
# processes that belong to an app, and asks once ("Allow") on first scan.
# Requires: brew install sane-backends python, and bjnp://<printer-ip> in
# /opt/homebrew/etc/sane.d/pixma.conf.
set -e
HERE="${0:A:h}"
LABEL=se.pija.mg8150-escl
APP="$HOME/Applications/MG8150 Scanner.app"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
clang -O2 -Wall -o "$APP/Contents/MacOS/launcher" "$HERE/launcher.c"
cp "$HERE/escl-bridge.py" "$APP/Contents/Resources/"

cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>MG8150 Scanner</string>
  <key>CFBundleIdentifier</key><string>se.pija.mg8150scanner</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSUIElement</key><true/>
  <key>NSLocalNetworkUsageDescription</key>
  <string>Connects to the Canon PIXMA MG8150 on your network so you can scan from Image Capture and Preview.</string>
  <key>NSBonjourServices</key>
  <array><string>_uscan._tcp</string></array>
</dict>
</plist>
EOF
codesign --force --sign - "$APP"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$APP/Contents/MacOS/launcher</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/mg8150-escl.log</string>
</dict>
</plist>
EOF

launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Scanner bridge running from $APP (eSCL on port 8090)"
