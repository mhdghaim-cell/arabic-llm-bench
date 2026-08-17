#!/usr/bin/env bash
# Regenerates assets/fonts/*.woff2 from IBM's official Plex sources.
#
# This is NOT part of `npm run build` — fonts only need regenerating when
# the type scale changes or the site starts using new scripts/punctuation
# not already covered by UNICODES below. Requires python3 + network access
# (downloads source TTFs from github.com/IBM/plex and installs a throwaway
# fonttools venv — nothing here becomes a runtime dependency of the site).
#
# Usage: ./scripts/subset-fonts.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

VENV="$WORK/venv"
SRC="$WORK/src"
OUT="$ROOT/assets/fonts"
mkdir -p "$SRC" "$OUT"

# Unicode ranges actually used across the site's content today:
#   U+0020-007E  basic Latin (letters, digits, ASCII punctuation)
#   U+0600-06FF  Arabic block (letters, harakat, tatweel, Arabic-Indic digits)
#   U+00AB,00BB  « » guillemets
#   U+00B7       · middot
#   U+2014       — em dash
#   U+2193,2197  ↓ ↗ card/link arrows
# If new content introduces a character outside this set, add its codepoint
# here and rerun — don't widen to whole extra Unicode blocks speculatively.
UNICODES="U+0020-007E,U+0600-06FF,U+00AB,U+00BB,U+00B7,U+2014,U+2193,U+2197"

echo "→ setting up throwaway fonttools venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip fonttools brotli

echo "→ downloading source TTFs from IBM/plex"
BASE="https://raw.githubusercontent.com/IBM/plex/master/packages"
curl -sL -o "$SRC/SansArabic-Regular.ttf"  "$BASE/plex-sans-arabic/fonts/complete/ttf/IBMPlexSansArabic-Regular.ttf"
curl -sL -o "$SRC/SansArabic-Medium.ttf"   "$BASE/plex-sans-arabic/fonts/complete/ttf/IBMPlexSansArabic-Medium.ttf"
curl -sL -o "$SRC/SansArabic-SemiBold.ttf" "$BASE/plex-sans-arabic/fonts/complete/ttf/IBMPlexSansArabic-SemiBold.ttf"
curl -sL -o "$SRC/SansArabic-Bold.ttf"     "$BASE/plex-sans-arabic/fonts/complete/ttf/IBMPlexSansArabic-Bold.ttf"
curl -sL -o "$SRC/Mono-Regular.ttf"        "$BASE/plex-mono/fonts/complete/ttf/IBMPlexMono-Regular.ttf"
curl -sL -o "$SRC/Mono-Medium.ttf"         "$BASE/plex-mono/fonts/complete/ttf/IBMPlexMono-Medium.ttf"

echo "→ subsetting"
PYFTSUBSET="$VENV/bin/pyftsubset"
subset() {
  "$PYFTSUBSET" "$SRC/$1" --unicodes="$UNICODES" --layout-features='*' \
    --flavor=woff2 --output-file="$OUT/$2.woff2"
}
subset SansArabic-Regular.ttf  sans-arabic-400
subset SansArabic-Medium.ttf   sans-arabic-500
subset SansArabic-SemiBold.ttf sans-arabic-600
subset SansArabic-Bold.ttf     sans-arabic-700
subset Mono-Regular.ttf        mono-400
subset Mono-Medium.ttf         mono-500

echo "→ done"
ls -la "$OUT"
