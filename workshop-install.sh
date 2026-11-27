#!/usr/bin/env bash
# Bounded, offline deployment task for human operator or Hermes.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source scripts/usb-common.sh
path="" yes=0 dry=0 llm_only=0
while (($#)); do
  case "$1" in
    --usb) (($# >= 2)) || exit 2; path="$2"; shift 2 ;;
    --yes) yes=1; shift ;;
    --dry-run) dry=1; shift ;;
    --llm-only) llm_only=1; shift ;;
    -h|--help) echo 'Usage: bash workshop-install.sh [--usb PATH] [--dry-run] [--yes] [--llm-only]'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
(( EUID != 0 || dry )) || { echo 'Run as normal user.' >&2; exit 1; }
root="$(usb_select "$path" 1 "$yes" "$PWD")"
[[ -n "$root" ]] || exit 1
# Real hardware detection only: no fixture override in this wrapper.
env -u EDGE_LLM_TEST_PROFILE bash install.sh --offline --usb "$root" --mode safe --dry-run
if (( ! llm_only )); then
  if [[ -f "$root/.portable-complete" ]]; then
    portable="$(usb_portable "$root")"
    [[ -d "$portable/stt" ]] || { echo 'Missing Whisper bundle.' >&2; exit 1; }
  fi
  echo 'Also installs multilingual Whisper CLI (no concurrent inference).'
fi
for cmd in python3 curl sudo systemctl; do
  command -v "$cmd" >/dev/null || { echo "Missing target prerequisite: $cmd" >&2; exit 1; }
done
if systemctl is-active --quiet edge-llm; then
  echo 'Existing edge-llm service detected. Installation replaces its service configuration; back up before approving.'
elif command -v ss >/dev/null && ss -ltnH 'sport = :8080' | grep -q .; then
  echo 'Port 8080 already in use by another service. Do not stop it automatically.' >&2; exit 1
fi
(( ! dry )) || exit 0
if (( ! yes )); then
  [[ -t 0 ]] || { echo 'Use a human terminal or --yes only after explicit operator approval.' >&2; exit 1; }
  read -r -p 'Install offline LLM service and selected tools now? [y/N] ' reply
  [[ "$reply" =~ ^[Yy] ]] || exit 0
fi
# sudo authorization remains interactive and under human control.
sudo -v
logdir="$HOME/.local/state/edge-workshop"
mkdir -p "$logdir"
log="$(mktemp "$logdir/install.XXXXXXXX.log")"
chmod 600 "$log"
echo "Detailed log: $log"
if [[ -f /etc/systemd/system/edge-llm.service ]]; then
  backup="$(mktemp "$logdir/service.XXXXXXXX.bak")"
  cp /etc/systemd/system/edge-llm.service "$backup"
  echo "Previous service unit: $backup"
  if [[ -f "$HOME/.local/share/edge-llm/start.sh" ]]; then cp "$HOME/.local/share/edge-llm/start.sh" "$backup.start.sh"; fi
fi
if ! bash install.sh --offline --usb "$root" --mode safe --yes >"$log" 2>&1; then
  tail -n 12 "$log" >&2; echo 'LLM install failed; inspect log before retry.' >&2; exit 1
fi
if (( ! llm_only )); then
  if ! bash install-stt.sh --usb "$root" --yes >>"$log" 2>&1; then
    tail -n 12 "$log" >&2; echo 'Whisper install failed; LLM may already be active.' >&2; exit 1
  fi
fi
ready=0
for ((attempt=0;attempt<120;attempt++)); do
  if systemctl is-active --quiet edge-llm && python3 scripts/edge-task.py health >>"$log" 2>&1; then ready=1; break; fi
  sleep 2
done
(( ready )) || { echo "API did not become ready. Inspect $log and journalctl -u edge-llm -n 40." >&2; exit 1; }
if ! python3 scripts/edge-task.py pt 'The meeting is on Friday at nine.' --max-tokens 256 >>"$log" 2>&1; then
  tail -n 8 "$log" >&2; echo 'API ready but inference failed.' >&2; exit 1
fi
tail -n 4 "$log"
echo 'Local LLM API responded; verify translation quality and run STT separately. No external provider contacted by this script.'
