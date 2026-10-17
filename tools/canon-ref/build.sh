#!/bin/bash
# Runs inside linux/amd64 ubuntu:14.04. Builds Canon's cnijfilter 3.40 for
# the MG8100 (model 377) so we can produce reference print jobs.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq build-essential autoconf automake libtool \
  libpopt-dev libtiff5-dev libpng12-dev >/dev/null

SRC=/canon/cnijfilter-source-3.40-1
cp -a "$SRC" /build && cd /build

# Model libraries and their database.
cp -a 377/libs_bin64/* com/libs_bin64/* /usr/lib/ 2>/dev/null || cp -a 377/libs_bin64/* /usr/lib/
mkdir -p /usr/lib/bjlib && cp 377/database/* /usr/lib/bjlib/
ldconfig

cd cnijfilter
./autogen.sh --prefix=/usr --program-suffix=mg8100 \
  --enable-libpath=/usr/lib/bjlib --enable-binpath=/usr/bin >/dev/null
make -j4 >/dev/null
make install >/dev/null
cnijfiltermg8100 --help 2>&1 | head -40 || true
