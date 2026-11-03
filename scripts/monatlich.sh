#!/bin/bash
# Monatliches Neu-Training (Phase 5).
#  1. Python-Teil in der Sandbox: Daten nachladen, rollierend pruefen, Schranke, Export,
#     Vergleichsdaten (scripts/monatlich.py).
#  2. Ist ein neues Modell bereit: Branch modelle/<version> in smard-mcp mit den Modelldateien
#     und den Vergleichsdaten, Tests laufen vor dem Push. Gemergt wird von Hand.
# Aufruf (als root): scripts/monatlich.sh [--ohne-nachladen] [--ohne-push]
set -euo pipefail
cd "$(dirname "$0")/.."
MCP=${SMARD_MCP_REPO:-/root/smard-mcp}
BASIS=${SMARD_MCP_BASIS:-main}
WT=/root/smard-mcp-modelle
LOG=data/logs/monatlich_git.log
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$LOG"; }

py_args=()
push=1
for a in "$@"; do
  case "$a" in
    --ohne-push) push=0 ;;
    *) py_args+=("$a") ;;
  esac
done

set +e
scripts/als-dienst.sh scripts/monatlich.py "${py_args[@]}"
rc=$?
set -e
chown -R smard-forecast:smard-forecast data
if [ "$rc" -ne 0 ]; then
  log "Python-Teil endete mit $rc (2 = angehalten, siehe data/betrieb/status.json); kein Branch"
  exit "$rc"
fi
version=$(python3 -c 'import json; print(json.load(open("data/betrieb/status.json"))["version"])')
log "neues Modell $version, baue Branch modelle/$version auf origin/$BASIS"

git -C "$MCP" fetch -q origin
git -C "$MCP" worktree remove --force "$WT" 2>/dev/null || rm -rf "$WT"
git -C "$MCP" worktree prune
git -C "$MCP" worktree add -q -B "modelle/$version" "$WT" "origin/$BASIS"
cp data/modell/"$version"/*.json "$WT/models/"
cp data/phase4/vergleich_"$version".json "$WT/test/fixtures/forecast-parity.json"
ln -s "$MCP/node_modules" "$WT/node_modules"
(cd "$WT" && npx tsc --noEmit -p . && npx vitest run test/forecast-parity.test.ts test/forecast.test.ts) \
  >> "$LOG" 2>&1 || { log "Tests im Branch fehlgeschlagen, kein Push ($WT bleibt zum Nachsehen)"; exit 3; }
rm "$WT/node_modules"
git -C "$WT" add models test/fixtures/forecast-parity.json
if git -C "$WT" diff --cached --quiet; then
  log "Modelldateien unverändert, nichts zu tun"
  exit 0
fi
git -C "$WT" commit -q -m "Modelle $version (monatliches Neu-Training)

Erzeugt von smard-forecast scripts/monatlich.sh; rollierende Pruefung, Schranke und
Vergleichstest bestanden. Kennzahlen in models/modell.json."
if [ "$push" -eq 1 ]; then
  git -C "$WT" push -q -u origin "modelle/$version"
  log "Branch modelle/$version gepusht; zum Mergen einen Pull Request nach $BASIS öffnen"
else
  log "ohne Push: Branch modelle/$version liegt lokal in $WT"
fi
