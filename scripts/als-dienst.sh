#!/bin/bash
# Fuehrt ein Projektskript als Systembenutzer smard-forecast aus, in einer systemd-Sandbox:
# nur data/ ist beschreibbar, kein Zugriff auf Home-Verzeichnisse, keine neuen Rechte,
# hoechstens 4 GB Speicher. Aufruf: scripts/als-dienst.sh scripts/phase2_solar.py [Argumente]
set -euo pipefail
cd "$(dirname "$0")/.."
exec systemd-run --wait --pipe --collect --quiet \
  --uid=smard-forecast --gid=smard-forecast \
  -p ProtectSystem=strict -p ProtectHome=yes -p ReadWritePaths=/srv/smard-forecast/data \
  -p NoNewPrivileges=yes -p PrivateTmp=yes -p PrivateDevices=yes \
  -p MemoryMax=4G -p Nice=10 -p CPUQuota=600% \
  -E OMP_NUM_THREADS=6 \
  --working-directory=/srv/smard-forecast \
  /srv/smard-forecast/.venv/bin/python -I "$@"
