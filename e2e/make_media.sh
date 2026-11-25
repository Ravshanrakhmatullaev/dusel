#!/bin/bash
# Soxta kamera uchun QR video (Chromium --use-file-for-fake-video-capture)
set -e
D=${1:-media}; mkdir -p "$D"
python3 -c "import segno; segno.make('https://dusel.pages.dev/?code=05000', error='m').save('$D/qr_05000.png', scale=12, border=4)"
ffmpeg -loglevel error -y -loop 1 -i "$D/qr_05000.png" -t 4 -r 10 -vf "scale=480:480,pad=640:480:80:0:white,format=yuv420p" "$D/qr_05000.y4m"
