#!/bin/zsh
# Score Gutenprint option sets against Canon's reference ink usage on the
# colorchart. Usage: tools/tune.sh "opts1" "opts2" ...   (CUPS option strings)
# Needs .work/t/chart.ras and .work/t/chart-canon.canon (see README).
set -e
cd "${0:A:h}/.."
T=.work/t
P=dist/Canon-PIXMA-MG8150.ppd
for opts in "$@"; do
  PPD=$P /Library/Printers/Gutenprint/libexec/cups/filter/rastertogutenprint.5.3 \
    1 n t 1 "$opts" $T/chart.ras > $T/tune.canon 2>/dev/null
  printf "%-80s " "$opts"
  python3 -I - $T/chart-canon.canon $T/tune.canon <<'EOF'
import sys
sys.path.insert(0, "tools")
import bjpatches
ref, got = bjpatches.measure(sys.argv[1]), bjpatches.measure(sys.argv[2])
# Compare total ink (C+M+Y+K) and per-channel error; K counted double since
# pigment black where Canon uses none muddies colors most.
err = sum(abs(ref[p][c] - got[p][c]) * (2 if c == "K" else 1) for p in ref for c in "CMYK")
worst = max(ref, key=lambda p: sum(abs(ref[p][c] - got[p][c]) for c in "CMYK"))
print("error %5.2f  worst: %s" % (err, worst))
EOF
done
