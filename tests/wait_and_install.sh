#!/bin/bash
# Waits for LibreOffice to close, then installs the extension cleanly.
# Writes progress to /tmp/loai_install_status.txt
set -u
STATUS=/tmp/loai_install_status.txt
OXT="/home/mike/MyRepos/LibreOffice AI Assistent/dist/sphaera-lo-ai-assistant.oxt"
UNOPKG=/app/libreoffice/program/unopkg
: > "$STATUS"

for i in $(seq 1 110); do
  if ! pgrep -f "[s]office.bin" >/dev/null 2>&1; then
    echo "LO closed after $((i*5))s; installing..." >> "$STATUS"
    sleep 2
    if pgrep -f "[s]office.bin" >/dev/null 2>&1; then
      echo "LO reopened, aborting" >> "$STATUS"; exit 1
    fi
    P=/home/mike/.var/app/org.libreoffice.LibreOffice/config/libreoffice/4/user/uno_packages
    rm -rf "$P/cache"
    if flatpak run --command="$UNOPKG" org.libreoffice.LibreOffice add "$OXT" >> "$STATUS" 2>&1; then
      echo "ADD OK" >> "$STATUS"
    else
      echo "ADD FAILED" >> "$STATUS"; exit 1
    fi
    C=$(ls -d "$P/cache/uno_packages/"*.tmp_ 2>/dev/null | head -1)
    echo "deployed py files:" >> "$STATUS"
    find "$C" -name "*.py" | head -4 >> "$STATUS"
    grep -c "framework-script" "$C/sphaera-lo-ai-assistant.oxt/META-INF/manifest.xml" >> "$STATUS" 2>&1
    R="$P/cache/registry/com.sun.star.comp.deployment.configuration.PackageRegistryBackend"
    if [ -f "$R/configmgr.ini" ]; then echo "CONFIG LAYER OK" >> "$STATUS"; else echo "NO CONFIG LAYER" >> "$STATUS"; exit 1; fi
    exit 0
  fi
  sleep 5
done
echo "TIMEOUT: LO still running after ~9 minutes" >> "$STATUS"
exit 1
