#!/bin/bash
# Archiv-Job auf den Server bringen: ARCHIV_HOST=root@<server> archiv/ausrollen.sh
# Die Server-Adresse steht nicht im Repo (wie bei smard-mcp).
set -euo pipefail
: "${ARCHIV_HOST:?ARCHIV_HOST setzen, z. B. root@server}"
cd "$(dirname "$0")/.."
python3 -c 'import json,tomllib;print(json.dumps([{k:o[k] for k in ("name","lat","lon","typ")} for o in tomllib.load(open("config/orte.toml","rb"))["ort"]],indent=1))' > /tmp/orte.json.$$
ssh "$ARCHIV_HOST" 'id smard-forecast >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin smard-forecast; install -d -o root -g root -m 755 /opt/smard-forecast-archiv'
scp -q archiv/archiv.py "$ARCHIV_HOST:/opt/smard-forecast-archiv/archiv.py"
scp -q /tmp/orte.json.$$ "$ARCHIV_HOST:/opt/smard-forecast-archiv/orte.json"
rm -f /tmp/orte.json.$$
scp -q archiv/smard-forecast-archiv.service archiv/smard-forecast-archiv.timer "$ARCHIV_HOST:/etc/systemd/system/"
ssh "$ARCHIV_HOST" 'chmod 644 /opt/smard-forecast-archiv/*; systemctl daemon-reload; systemctl enable --now smard-forecast-archiv.timer; systemctl start smard-forecast-archiv.service; journalctl -u smard-forecast-archiv.service -n 3 --no-pager'
