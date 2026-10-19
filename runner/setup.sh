#!/bin/bash
# Tools for a render job: our Hebrew fonts (OFL, in fonts/), ffmpeg, Playwright + Chromium.
#   bash runner/setup.sh [--no-browser]
set -e
t0=$(date +%s)
mkdir -p ~/.fonts && cp "$FARM"/fonts/*.ttf ~/.fonts/ && fc-cache -f >/dev/null
if ! command -v ffmpeg >/dev/null; then
  if curl -sfL --max-time 60 https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar -xJ -C /tmp; then
    sudo cp /tmp/ffmpeg-*-static/ffmpeg /tmp/ffmpeg-*-static/ffprobe /usr/local/bin/
  else
    sudo apt-get update -q && sudo apt-get install -y -q --no-install-recommends ffmpeg
  fi
fi
if [ "$1" != "--no-browser" ]; then
  pip install -q playwright psutil numpy
  python -m playwright install --only-shell chromium || python -m playwright install chromium
fi
echo "setup $(( $(date +%s) - t0 ))s  ffmpeg=$(command -v ffmpeg)  cpus=$(nproc)"
