#!/usr/bin/env bash
# Build baseline ARM64 binaries by cross-compilation on an amd64 laptop, then
# publish them into an already-prepared directory-stand-in USB kit.
#
# Needed when rootless Docker cannot execute linux/arm64 (exec format error)
# even though host binfmt is registered. Emulated checks use qemu-user-static
# with an aarch64 Debian sysroot, not physical Pi validation.
#
# Usage: bash scripts/build-arm64-cross.sh [KIT_DIR] [AARCH64_SYSROOT]
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
KIT="$(realpath -e "${1:-/tmp/opencode/workshop/edge-llm-usb/edge-llm-usb}")"
SYSROOT="${2:-/tmp/opencode/workshop/arm64-rootfs}"
OUT="${TMPDIR:-/tmp}/edge-arm64-cross-out"
CACHE="$KIT/.build-cache"
command -v docker qemu-aarch64-static >/dev/null || { echo 'Need docker and qemu-aarch64-static' >&2; exit 1; }
[[ -f "$CACHE/sources.lock" ]] || { echo 'Prepare the kit first (prepare-usb.sh)' >&2; exit 1; }
mapfile -t rev < "$CACHE/sources.lock"
mkdir -p "$OUT"
if [[ ! -f "$OUT/SHA256SUMS" ]]; then
  docker build --platform linux/amd64 -f "$HERE/usb-build/Dockerfile.cross-arm64" --target export \
    --build-arg "LLAMA_REV=${rev[0]}" --build-arg "WHISPER_REV=${rev[1]}" \
    --build-arg JOBS=1 --output "type=local,dest=$OUT" "$HERE/usb-build"
else
  echo "Reusing already-exported ARM64 binaries in $OUT"
fi
(cd "$OUT" && sha256sum llama-server whisper-cli > SHA256SUMS && sha256sum --strict -c SHA256SUMS)
file "$OUT/llama-server" "$OUT/whisper-cli" | grep -q 'ARM aarch64' || { echo 'Not ARM64 ELF' >&2; exit 1; }
# sed reads all input, so it does not send SIGPIPE to qemu under pipefail.
qemu-aarch64-static -L "$SYSROOT" "$OUT/llama-server" --version 2>&1 | sed -n '1,3p'
qemu-aarch64-static -L "$SYSROOT" "$OUT/whisper-cli" --help 2>&1 | sed -n '1,3p'
cd "$REPO"
source scripts/usb-common.sh
for pair in 'pi4:Qwen3.5-0.8B-Q4_K_M.gguf' 'pi8:Qwen3.5-2B-Q4_K_M.gguf' 'pi16:Qwen3.5-4B-Q4_K_M.gguf'; do
  model="${pair#*:}"
  usb_publish "$KIT/portable/aarch64/llm/$model" "$OUT/llama-server" \
    "$CACHE/models/$model" llama-server "$model"
done
usb_publish "$KIT/portable/aarch64/stt" "$OUT/whisper-cli" "$CACHE/models/ggml-base.bin" \
  whisper-cli ggml-base.bin
mkdir -p "$KIT/provenance/aarch64"
cp "$OUT/"{build-info.txt,LICENSE-llama.cpp,LICENSE-whisper.cpp,llama-CMakeCache.txt,whisper-CMakeCache.txt} \
  "$KIT/provenance/aarch64/"
echo 'ARM64 cross-build and publish complete. Emulated checks are not physical Pi validation.'
