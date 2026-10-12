#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ESP32_HOST_ARG="${1:-}"
PORT_ARG="${2:-57843}"
flutter pub get
flutter build web --dart-define="ESP32_HOST=$ESP32_HOST_ARG"
printf 'Open http://localhost:%s/ in Chrome\n' "$PORT_ARG"
python3 -m http.server "$PORT_ARG" --bind 127.0.0.1 --directory build/web
