#!/usr/bin/env bash
# Run online on each distinct target hardware/OS profile; accumulate one USB.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source scripts/usb-common.sh
path="" yes=0 llm_only=0
while (($#)); do
  case "$1" in
    --usb) (($# >= 2)) || exit 2; path="$2"; shift 2 ;;
    --yes) yes=1; shift ;;
    --llm-only) llm_only=1; shift ;;
    -h|--help) echo 'Usage: bash prepare-usb.sh --usb /mounted/usb [--yes] [--llm-only]'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
(( EUID != 0 )) || { echo 'Run as normal user.' >&2; exit 1; }
if [[ -z "$path" ]]; then
  lsblk -o NAME,SIZE,TRAN,FSTYPE,MOUNTPOINTS >&2
  [[ -t 0 && "$yes" == 0 ]] || { echo 'Specify --usb /mount/path' >&2; exit 1; }
  read -r -p 'Mounted USB path: ' path
fi
path="$(realpath -e "$path")"
mountpoint -q "$path" && [[ "$path" != / && -w "$path" ]] || { echo 'Use a writable mounted directory, not a block device.' >&2; exit 1; }
fs="$(findmnt -n -o FSTYPE --target "$path")"
[[ "$fs" != vfat && "$fs" != msdos ]] || { echo 'Use exFAT or ext4, not FAT32 (4 GB file limit).' >&2; exit 1; }
root="$path/edge-llm-usb"
[[ ! -e "$root" || -f "$root/.edge-llm-usb-v1" ]] || { echo 'Existing unmanaged directory; refusing overwrite.' >&2; exit 1; }
git diff --quiet HEAD -- && git diff --cached --quiet || { echo 'Commit changes before preparing USB.' >&2; exit 1; }
rev="$(git rev-parse HEAD)"
profile="$(env -u EDGE_LLM_TEST_PROFILE bash install.sh --online --mode safe --dry-run | sed -n 's/^Hardware:  \([^ ]*\) .*/\1/p')"
[[ "$profile" =~ ^(pi4|pi8|pi16|nuc16|k11)$ ]] || exit 1
platform="$(usb_platform)"
df -h "$path" "$HOME"
echo "Prepare $profile / $platform at $root. Online build dependencies may be installed; no service changes."
if (( ! yes )); then
  [[ -t 0 ]] || exit 1
  read -r -p 'Proceed? [y/N] ' reply
  [[ "$reply" =~ ^[Yy] ]] || exit 0
fi
mkdir -p "$root"
printf 'edge-llm-usb v1\n' > "$root/.edge-llm-usb-v1"
bash install.sh --online --mode safe --export-usb "$root" --yes
if (( ! llm_only )); then
  cache="$HOME/.cache/edge-llm-usb-build"
  src="$cache/whisper.cpp"; build="$src/build-usb"; model="$cache/ggml-base.bin"
  dest="$root/stt/$platform/$profile"
  if [[ -d "$dest" ]]; then
    usb_check "$dest" whisper-cli ggml-base.bin
  else
    mkdir -p "$cache"
    [[ -d "$src/.git" ]] || git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$src"
    cmake -S "$src" -B "$build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
      -DGGML_NATIVE=ON -DGGML_OPENMP=OFF -DGGML_BACKEND_DL=OFF \
      -DWHISPER_BUILD_TESTS=OFF '-DCMAKE_EXE_LINKER_FLAGS=-static-libstdc++ -static-libgcc'
    cmake --build "$build" --parallel 2 --target whisper-cli
    if [[ ! -s "$model" ]]; then
      curl -fL --retry 3 -o "$model.part" https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin
      mv "$model.part" "$model"
    fi
    [[ "$(stat -c %s "$model")" -gt 100000000 ]] || { echo 'Incomplete Whisper model.' >&2; exit 1; }
    usb_runtime_check "$build/bin/whisper-cli" --help
    usb_publish "$dest" "$build/bin/whisper-cli" "$model" whisper-cli ggml-base.bin
  fi
fi
# Only committed content, never credentials, .git, caches or untracked files.
checkout="$root/repo-$rev"
if [[ ! -d "$checkout" ]]; then
  tmp="$(mktemp -d "$root/.repo.XXXXXXXX")"
  git archive "$rev" | tar -xf - -C "$tmp"
  mv -T "$tmp" "$checkout"
fi
printf 'Open folder repo-%s in edge-llm-usb on the target.\nRun: bash install.sh --offline --mode safe\nThen: bash install-stt.sh\nSee docs/WORKSHOP_USB.md. If not detected, pass --usb /actual/mount.\n' "$rev" > "$root/START-HERE.txt"
sync
cat "$root/START-HERE.txt"
echo "Prepared $profile. Repeat on each distinct CPU/OS profile using the SAME USB."
