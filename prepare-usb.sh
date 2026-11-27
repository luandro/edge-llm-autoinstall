#!/usr/bin/env bash
# Laptop-only multiarchitecture preparation. No target devices needed.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source scripts/usb-common.sh
path="" yes=0 dry=0 jobs=2
while (($#)); do
  case "$1" in
    --usb) (($# >= 2)) || exit 2; path="$2"; shift 2 ;;
    --yes) yes=1; shift ;;
    --dry-run) dry=1; shift ;;
    --jobs) (($# >= 2)) || exit 2; jobs="$2"; shift 2 ;;
    -h|--help) echo 'Usage: bash prepare-usb.sh [--usb /mounted/usb] [--yes] [--dry-run] [--jobs N]'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] && (( jobs <= 8 )) || exit 2
echo 'Plan: build linux/amd64 + linux/arm64 generic CPU binaries in Debian Bookworm containers; download all safe models and Whisper base; save pinned revisions, checksums, samples and Git snapshot.'
cat scripts/usb-build/models.tsv
echo 'USB: 128GB recommended; allow ~30GB for models/cache/copies plus build cache on Docker storage. Target glibc >=2.36, 64-bit Linux/systemd. No target machine needed.'
(( ! dry )) || exit 0
(( EUID != 0 )) || { echo 'Run as normal user.' >&2; exit 1; }
for cmd in docker git curl python3 sha256sum findmnt mountpoint; do command -v "$cmd" >/dev/null || { echo "Missing $cmd"; exit 1; }; done
docker buildx version
docker info --format 'Docker storage: {{.DockerRootDir}}'
df -h "$HOME"
if [[ -z "$path" ]]; then
  lsblk -o NAME,SIZE,TRAN,FSTYPE,MOUNTPOINTS >&2
  [[ -t 0 && "$yes" == 0 ]] || { echo 'Specify --usb /mount/path' >&2; exit 1; }
  read -r -p 'Mounted USB path: ' path
fi
path="$(realpath -e "$path")"
mountpoint -q "$path" && [[ "$path" != / && -w "$path" ]] || { echo 'Use a writable mounted directory, not a block device.' >&2; exit 1; }
fs="$(findmnt -n -o FSTYPE --target "$path")"
[[ "$fs" != vfat && "$fs" != msdos ]] || { echo 'Use exFAT or ext4, not FAT32.' >&2; exit 1; }
root="$path/edge-llm-usb"
[[ ! -e "$root" || -f "$root/.edge-llm-usb-v1" ]] || { echo 'Existing unmanaged directory; refusing overwrite.' >&2; exit 1; }
git diff --quiet HEAD -- && git diff --cached --quiet || { echo 'Commit tracked changes before preparing USB.' >&2; exit 1; }
rev="$(git rev-parse HEAD)"
df -h "$path" "$HOME"
if [[ ! -d "$root/.build-cache" ]]; then
  free="$(df -PB1 "$path" | awk 'END{print $4}')"
  (( free >= 32000000000 )) || { echo 'Initial complete kit needs at least 32 GB free; use larger USB.' >&2; exit 1; }
fi
if (( ! yes )); then
  [[ -t 0 ]] || exit 1
  read -r -p 'Download/build both architectures now? [y/N] ' reply
  [[ "$reply" =~ ^[Yy] ]] || exit 0
fi
# Do not auto-register privileged binfmt or install Docker on the host.
for p in amd64 arm64; do
  docker run --rm --platform "linux/$p" debian:bookworm-slim uname -m || {
    echo "Cannot run linux/$p. Set up Docker buildx/QEMU/binfmt with operator approval, then retry." >&2; exit 1;
  }
done
mkdir -p "$root"
printf 'edge-llm-usb v2\n' > "$root/.edge-llm-usb-v1"
rm -f "$root/.portable-complete"
cache="$root/.build-cache"
mkdir -p "$cache/models" "$root/provenance" "$root/samples"
# Lock the first resolved revisions; reruns never silently switch versions.
if [[ ! -f "$cache/sources.lock" ]]; then
  llama="$(git ls-remote https://github.com/ggml-org/llama.cpp.git HEAD | awk 'NR==1 {print $1}')"
  whisper="$(git ls-remote https://github.com/ggml-org/whisper.cpp.git HEAD | awk 'NR==1 {print $1}')"
  [[ "$llama" =~ ^[0-9a-f]{40}$ && "$whisper" =~ ^[0-9a-f]{40}$ ]] || exit 1
  printf '%s\n%s\n' "$llama" "$whisper" > "$cache/sources.lock.tmp"
  mv "$cache/sources.lock.tmp" "$cache/sources.lock"
fi
mapfile -t revisions < "$cache/sources.lock"
[[ "${revisions[0]}" =~ ^[0-9a-f]{40}$ && "${revisions[1]}" =~ ^[0-9a-f]{40}$ ]] || exit 1
# Resolve actual multiarch base manifest; record/pin digest rather than floating tag.
if [[ ! -f "$cache/base.lock" ]]; then
  # Do not `exit` inside awk: closing the pipe early sends SIGPIPE to buildx,
  # which fails the substitution under `set -o pipefail`.
  digest="$(docker buildx imagetools inspect debian:bookworm-slim | awk '$1=="Digest:" && !seen {print $2; seen=1}')"
  [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo 'Could not resolve base digest.'; exit 1; }
  printf 'debian:bookworm-slim@%s\n' "$digest" > "$cache/base.lock"
fi
base_image="$(cat "$cache/base.lock")"
[[ "$base_image" =~ ^debian:bookworm-slim@sha256:[0-9a-f]{64}$ ]] || exit 1
cp "$cache/sources.lock" "$cache/base.lock" "$root/provenance/"
# Use a temporary Linux directory for BuildKit export; exFAT may not preserve mode bits.
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
for platform in amd64 arm64; do
  case "$platform" in amd64) arch=x86_64 ;; arm64) arch=aarch64 ;; esac
  built="$cache/bin-$arch"
  if [[ ! -f "$built/SHA256SUMS" ]]; then
    mkdir -p "$tmp/$arch"
    docker buildx build --platform "linux/$platform" --target export \
      --build-arg "BASE_IMAGE=$base_image" --build-arg "LLAMA_REV=${revisions[0]}" \
      --build-arg "WHISPER_REV=${revisions[1]}" --build-arg "JOBS=$jobs" \
      --output "type=local,dest=$tmp/$arch" scripts/usb-build
    mkdir -p "$built"
    cp "$tmp/$arch/"* "$built/"
    (cd "$built" && sha256sum llama-server whisper-cli > SHA256SUMS)
  fi
  (cd "$built" && sha256sum --strict -c SHA256SUMS)
  grep -Fxq "llama=${revisions[0]}" "$built/build-info.txt"
  grep -Fxq "whisper=${revisions[1]}" "$built/build-info.txt"
  mkdir -p "$root/provenance/$arch"
  cp "$built/"{build-info.txt,LICENSE-llama.cpp,LICENSE-whisper.cpp,llama-CMakeCache.txt,whisper-CMakeCache.txt} "$root/provenance/$arch/"
  if [[ "$platform" == amd64 ]]; then cp "$built/"sample-*.wav "$root/samples/"; fi
  # Test image stays on the laptop for network-disabled rehearsal. No target Docker needed.
  docker buildx build --platform "linux/$platform" --target runtime --build-arg "BASE_IMAGE=$base_image" \
    --load -t "edge-usb-rehearsal:$platform" scripts/usb-build
done
# Download one copy per exact upstream file, using immutable model revision and curl resume.
while IFS='|' read -r profile repo model; do
  [[ "$profile" != \#* && -n "$profile" ]] || continue
  entry="$cache/models/$model"
  if [[ ! -f "$entry.revision" ]]; then
    curl -fsSL --retry 3 "https://huggingface.co/api/models/$repo" |
      python3 -c 'import json,sys; print(json.load(sys.stdin)["sha"])' > "$entry.revision.tmp"
    mv "$entry.revision.tmp" "$entry.revision"
  fi
  modelrev="$(cat "$entry.revision")"
  [[ "$modelrev" =~ ^[a-f0-9]{40}$ ]] || exit 1
  if [[ ! -f "$entry.sha256" ]]; then
    # Compare with Hub LFS metadata when available, not just a self-generated checksum.
    curl -fsSL --retry 3 "https://huggingface.co/api/models/$repo/revision/$modelrev?blobs=true" > "$tmp/hf.json"
    read -r expected_size expected_sha < <(python3 -c 'import json,sys; f=next(x for x in json.load(open(sys.argv[1]))["siblings"] if x["rfilename"]==sys.argv[2]); print(f.get("size") or f.get("lfs",{}).get("size") or 0, f.get("lfs",{}).get("sha256") or "-")' "$tmp/hf.json" "$model")
    curl -fL --retry 3 -C - -o "$entry.part" "https://huggingface.co/$repo/resolve/$modelrev/$model"
    if (( expected_size > 0 )); then [[ "$(stat -c %s "$entry.part")" == "$expected_size" ]] || { echo "Upstream size mismatch $model"; exit 1; }; fi
    if [[ "$expected_sha" != "-" ]]; then [[ "$(sha256sum "$entry.part" | awk '{print $1}')" == "$expected_sha" ]] || { echo "Upstream LFS digest mismatch $model"; exit 1; }; fi
    [[ "$(stat -c %s "$entry.part")" -gt 100000000 ]] || { echo "Truncated $model"; exit 1; }
    if [[ "$profile" != stt ]]; then [[ "$(head -c 4 "$entry.part")" == GGUF ]] || exit 1; fi
    mv "$entry.part" "$entry"
    (cd "$(dirname "$entry")" && sha256sum "$model" > "$model.sha256")
  fi
  (cd "$(dirname "$entry")" && sha256sum --strict -c "$model.sha256")
  printf '%s|%s|%s|%s\n' "$profile" "$repo" "$modelrev" "$model" >> "$tmp/models.lock"
  for arch in x86_64 aarch64; do
    # x86 gets all LLMs for rehearsal; ARM gets Pi models only.
    [[ "$arch" != aarch64 || "$profile" != k11 ]] || continue
    if [[ "$profile" == stt ]]; then
      usb_publish "$root/portable/$arch/stt" "$cache/bin-$arch/whisper-cli" "$entry" whisper-cli "$model"
    else
      usb_publish "$root/portable/$arch/llm/$model" "$cache/bin-$arch/llama-server" "$entry" llama-server "$model"
    fi
  done
done < scripts/usb-build/models.tsv
cp "$tmp/models.lock" "$root/provenance/models.lock"
# Cache official bootstrap script for review; full Hermes install still requires WAN.
mkdir -p "$root/hermes"
if [[ ! -f "$root/hermes/install.sh" ]]; then
  curl -fsSL --retry 3 https://hermes-agent.nousresearch.com/install.sh -o "$root/hermes/install.sh.part"
  mv "$root/hermes/install.sh.part" "$root/hermes/install.sh"
fi
(cd "$root/hermes" && sha256sum install.sh > SHA256SUMS)
checkout="$root/repo-$rev"
if [[ ! -d "$checkout" ]]; then
  stage="$(mktemp -d "$root/.repo.XXXXXXXX")"
  git archive "$rev" | tar -xf - -C "$stage"
  mv -T "$stage" "$checkout"
fi
printf '%s\n' 'Synthetic eSpeak examples (not human or Indigenous language evaluation).' \
 'PT: A rádio comunitária entrevistou três moradores. A reunião será na sexta-feira, às nove horas.' \
 'EN: The community radio interviewed three residents. The meeting is on Friday at nine in the morning.' > "$root/samples/REFERENCES.txt"
(cd "$root/samples" && sha256sum sample-*.wav REFERENCES.txt > SHA256SUMS)
printf 'Abra a pasta repo-%s.\n1. bash install.sh --offline --mode safe\n2. bash install-stt.sh\nLeia docs/WORKSHOP_USB.md. Hermes online: docs/HERMES_WORKSHOP.md.\nNo laptop: bash scripts/rehearse-usb.sh --usb /ponto/de/montagem\n' "$rev" > "$root/START-HERE.txt"
printf '%s\n' "$rev" > "$root/.portable-complete.tmp"
mv "$root/.portable-complete.tmp" "$root/.portable-complete"
sync
echo 'Both architectures prepared. Run laptop rehearsal before declaring readiness.'
