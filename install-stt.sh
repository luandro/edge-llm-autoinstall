#!/usr/bin/env bash
# Offline multilingual Whisper CLI; standard 16kHz mono PCM WAV.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source scripts/usb-common.sh
path="" yes=0
while (($#)); do
  case "$1" in
    --usb) (($# >= 2)) || exit 2; path="$2"; shift 2 ;;
    --offline) shift ;;
    --yes) yes=1; shift ;;
    -h|--help) echo 'Usage: bash install-stt.sh [--usb PATH] [--yes] (offline only)'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
(( EUID != 0 )) || { echo 'Run as normal user.' >&2; exit 1; }
root="$(usb_select "$path" 1 "$yes" "$PWD")"
[[ -n "$root" ]] || exit 1
profile="$(env -u EDGE_LLM_TEST_PROFILE bash install.sh --online --mode safe --dry-run | sed -n 's/^Hardware:  \([^ ]*\) .*/\1/p')"
[[ "$profile" =~ ^(pi4|pi8|pi16|nuc16|k11)$ ]] || exit 1
bundle="$root/stt/$(usb_platform)/$profile"
if grep -qx "edge-llm-usb v2" "$root/.edge-llm-usb-v1" && [[ ! -f "$root/.portable-complete" ]]; then
  echo "Incomplete portable kit; finish preparation on the laptop." >&2; exit 1
fi
if [[ -f "$root/.portable-complete" ]]; then
  portable="$(usb_portable "$root")" || exit 1
  bundle="$portable/stt"
fi
usb_check "$bundle" whisper-cli ggml-base.bin
if (( ! yes )); then
  [[ -t 0 ]] || { echo 'Use --yes only with operator approval.' >&2; exit 1; }
  read -r -p 'Install offline Whisper into home directory? [y/N] ' reply
  [[ "$reply" =~ ^[Yy] ]] || exit 0
fi
dir="$HOME/.local/share/edge-stt"
usb_copy "$bundle/whisper-cli" "$dir/whisper-cli" 755
usb_runtime_check "$dir/whisper-cli" --help
usb_copy "$bundle/ggml-base.bin" "$dir/ggml-base.bin" 644
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/edge-transcribe" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$HOME/.local/share/edge-stt/whisper-cli" -m "$HOME/.local/share/edge-stt/ggml-base.bin" -t 2 "$@"
EOF
chmod 755 "$HOME/.local/bin/edge-transcribe"
echo 'Test: ~/.local/bin/edge-transcribe -l pt -f interview.wav'
echo 'Use 16kHz mono PCM WAV; -l en for English. Avoid simultaneous LLM+STT on Pi 4GB.'
