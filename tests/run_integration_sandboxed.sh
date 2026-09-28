#!/bin/bash
# Runs inside the flatpak sandbox: spawns soffice.bin directly (same netns),
# waits for its URP port, runs the batched integration client, cleans up.
set -u
PROFILE=/home/mike/lo-ai-test-profile3
PORT=2006
TESTS="/home/mike/MyRepos/LibreOffice AI Assistent/tests"
export PYTHONPATH=/app/libreoffice/program
export LOAI_PROFILE="$PROFILE"
export LOAI_PORT="$PORT"

rm -rf "$PROFILE"
pkill -f "lo-ai-test-profile3" 2>/dev/null
sleep 1

/app/libreoffice/program/soffice.bin \
  -env:UserInstallation="file://$PROFILE" \
  --headless --invisible --norestore --nologo \
  "--accept=socket,host=127.0.0.1,port=$PORT;urp;" &
SOFFICE_PID=$!

for i in $(seq 1 40); do
  if python3 "$TESTS/check_port.py" "$PORT" 2>/dev/null; then
    echo "port up after ${i}x0.5s"
    break
  fi
  sleep 0.5
done

sleep 1
python3 "$TESTS/integration_client.py"
RC=$?

kill "$SOFFICE_PID" 2>/dev/null
wait "$SOFFICE_PID" 2>/dev/null
exit $RC
