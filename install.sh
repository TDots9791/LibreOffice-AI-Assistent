#!/usr/bin/env bash
# Install the extension into LibreOffice (native or flatpak), user scope.
set -euo pipefail
cd "$(dirname "$0")"

OXT="dist/sphaera-lo-ai-assistant.oxt"
ACTION="add"
[ "${1:-}" = "--remove" ] && ACTION="remove"

if [ ! -f "$OXT" ] && [ "$ACTION" = "add" ]; then
  ./build.sh
fi

ABS="$(cd "$(dirname "$OXT")" && pwd)/$(basename "$OXT")"

# Installing while LibreOffice runs corrupts the deployment database
# (backenddb.xml keeps pointing at replaced files -> unopkg breaks).
if pgrep -f "[s]office.bin" >/dev/null 2>&1; then
  echo "LibreOffice is running. Close ALL LibreOffice windows and retry." >&2
  echo "(Installing into a running instance corrupts the extension registry.)" >&2
  exit 1
fi

if command -v unopkg >/dev/null 2>&1; then
  echo ">> native LibreOffice detected"
  if [ "$ACTION" = "add" ]; then
    unopkg add --force "$ABS"
  else
    unopkg remove org.sphaera.lo.assistant
  fi
elif command -v flatpak >/dev/null 2>&1 && flatpak info org.libreoffice.LibreOffice >/dev/null 2>&1; then
  echo ">> flatpak LibreOffice detected"
  UNOPKG="/app/libreoffice/program/unopkg"
  if [ "$ACTION" = "add" ]; then
    flatpak run --command="$UNOPKG" org.libreoffice.LibreOffice add --force "$ABS"
  else
    flatpak run --command="$UNOPKG" org.libreoffice.LibreOffice remove org.sphaera.lo.assistant
  fi
else
  echo "LibreOffice not found (neither native nor flatpak)." >&2
  exit 1
fi

echo ">> done. Restart LibreOffice, then use Tools > AI Assistant…"
