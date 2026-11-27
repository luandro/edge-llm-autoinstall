#!/usr/bin/env bash
# Read-only USB, network-disabled containers. Does not change host services.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/usb-common.sh
path="" full=0
while (($#)); do
  case "$1" in
    --usb) (($# >= 2)) || exit 2; path="$2"; shift 2 ;;
    --full-arm) full=1; shift ;;
    -h|--help) echo 'Usage: bash scripts/rehearse-usb.sh --usb /mount [--full-arm]'; exit 0 ;;
    *) exit 2 ;;
  esac
done
root="$(usb_select "$path" 1 1 "$PWD")"
[[ -f "$root/.portable-complete" ]] || { echo 'Incomplete portable kit.'; exit 1; }
rev="$(cat "$root/.portable-complete")"
repo="$root/repo-$rev"
[[ -f "$repo/scripts/usb-build/rehearse.py" ]] || exit 1
(cd "$root/hermes" && sha256sum --strict -c SHA256SUMS)
(cd "$root/samples" && sha256sum --strict -c SHA256SUMS)
for plat in amd64 arm64; do
  case "$plat" in amd64) arch=x86_64; mode=full ;; arm64) arch=aarch64; mode=version; (( ! full )) || mode=small ;; esac
  docker image inspect "edge-usb-rehearsal:$plat" >/dev/null
  docker run --rm --pull never --platform "linux/$plat" --network none \
    --mount "type=bind,source=$root,target=/kit,readonly" \
    "edge-usb-rehearsal:$plat" python3 "/kit/repo-$rev/scripts/usb-build/rehearse.py" "$arch" "$mode"
done
