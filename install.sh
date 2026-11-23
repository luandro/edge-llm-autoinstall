#!/usr/bin/env bash
# One-command local model installer for Pi 5, Intel N95/N97 and Ryzen 8945HS / Radeon 780M.
set -Eeuo pipefail

APP=edge-llm
HOME_DIR="${HOME}/.local/share/${APP}"
SOURCE_DIR="${HOME_DIR}/src"
MODE=auto
MODEL_CHOICE=auto
BACKEND_CHOICE=auto
GPU_LAYERS=99
GPU_LAYERS_GIVEN=0
CONTEXT_OVERRIDE=""
MODEL_DIR=""
MODEL_DIR_GIVEN=0
YES=0
DRY_RUN=0

info() { printf '\n[edge-llm] %s\n' "$*"; }
fail() { printf '[edge-llm] ERROR: %s\n' "$*" >&2; exit 1; }
usage() {
  cat <<'EOF'
Usage: bash install.sh [--mode auto|best|safe] [--model NAME] [--backend auto|vulkan|cpu]
                       [--gpu-layers N] [--context N] [--model-dir PATH] [--yes] [--dry-run]

  --mode auto       Safer no-tuning K11 model; Pi 8GB without SSD uses safe model
  --mode best       Highest capability model for detected hardware
  --mode safe       Smaller and more dependable model
  --model NAME      Ryzen 8945HS: gemma4-e4b, gemma4, qwen36, inkling, qwen38, gptoss20b, qwen35-9b
  --backend NAME    Ryzen 8945HS: auto (Vulkan preferred), vulkan, cpu
  --gpu-layers N    Ryzen 8945HS: offload N layers to Radeon iGPU (default 99)
  --context N       Override model context window (512-131072 tokens)
  --model-dir PATH  Download GGUF weights to PATH (SSD recommended for Pi 8GB best)
  --yes             Skip the confirmation prompt
  --dry-run         Print the selection and exit without modifications

All servers use local http://127.0.0.1:8080/v1 and model id edge-llm.
EOF
}
while (($#)); do
  case "$1" in
    --mode) (($# >= 2)) || fail 'Missing value for --mode'; MODE="$2"; shift 2 ;;
    --model) (($# >= 2)) || fail 'Missing value for --model'; MODEL_CHOICE="$2"; shift 2 ;;
    --backend) (($# >= 2)) || fail 'Missing value for --backend'; BACKEND_CHOICE="$2"; shift 2 ;;
    --gpu-layers) (($# >= 2)) || fail 'Missing value for --gpu-layers'; GPU_LAYERS="$2"; GPU_LAYERS_GIVEN=1; shift 2 ;;
    --context) (($# >= 2)) || fail 'Missing value for --context'; CONTEXT_OVERRIDE="$2"; shift 2 ;;
    --model-dir) (($# >= 2)) || fail 'Missing value for --model-dir'; MODEL_DIR="$2"; MODEL_DIR_GIVEN=1; shift 2 ;;
    --yes|-y) YES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) fail "Unknown argument: $1" ;;
  esac
done
[[ "$MODE" =~ ^(auto|best|safe)$ ]] || fail 'Mode must be auto, best or safe.'
[[ "$MODEL_CHOICE" =~ ^(auto|gemma4-e4b|gemma4|inkling|qwen38|qwen36|gptoss20b|qwen35-9b)$ ]] || fail 'Invalid --model selection.'
[[ "$BACKEND_CHOICE" =~ ^(auto|vulkan|cpu)$ ]] || fail 'Backend must be auto, vulkan or cpu.'
[[ "$GPU_LAYERS" =~ ^[0-9]+$ ]] || fail 'GPU layers must be a non-negative integer.'
if [[ -n "$CONTEXT_OVERRIDE" ]]; then
  [[ "$CONTEXT_OVERRIDE" =~ ^[0-9]+$ ]] || fail 'Context must be an integer.'
  (( 10#$CONTEXT_OVERRIDE >= 512 && 10#$CONTEXT_OVERRIDE <= 131072 )) || fail 'Context must be 512-131072.'
fi
(( EUID != 0 || DRY_RUN == 1 )) || fail 'Run as your normal user; sudo is requested for system changes.'
[[ "$(uname -s)" == Linux ]] || fail 'Linux only.'
command -v systemctl >/dev/null || fail 'Requires systemd.'

ARCH="$(uname -m)"
CPU_NAME="$(grep -im1 '^model name' /proc/cpuinfo | cut -d: -f2- | sed 's/^ *//' || true)"
DEVICE=''
[[ ! -r /proc/device-tree/model ]] || DEVICE="$(tr -d '\000' </proc/device-tree/model)"
MEM_KIB="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
MEM_GIB="$((MEM_KIB / 1024 / 1024))"
# Tests can override hardware only during a dry-run; never for real installation.
if [[ -n "${EDGE_LLM_TEST_PROFILE:-}" && "$DRY_RUN" -eq 1 ]]; then
  PROFILE="$EDGE_LLM_TEST_PROFILE"
elif [[ "$ARCH" == aarch64 && "$DEVICE" == *'Raspberry Pi 5'* ]]; then
  if (( MEM_KIB >= 13 * 1024 * 1024 )); then PROFILE=pi16
  elif (( MEM_KIB >= 6 * 1024 * 1024 )); then PROFILE=pi8
  else fail 'Pi 5 requires at least 8 GB RAM.'; fi
elif [[ "$ARCH" == x86_64 && ( "$CPU_NAME" =~ (^|[^[:alnum:]])N95([^[:alnum:]]|$) || "$CPU_NAME" =~ (^|[^[:alnum:]])N97([^[:alnum:]]|$) ) ]]; then
  (( MEM_KIB >= 13 * 1024 * 1024 )) || fail 'N95/N97 profile needs approximately 16 GB RAM.'
  PROFILE=nuc16
elif [[ "$ARCH" == x86_64 && "$CPU_NAME" == *'AMD Ryzen'* && "$CPU_NAME" == *'8945HS'* ]]; then
  (( MEM_KIB >= 27 * 1024 * 1024 )) || fail 'Ryzen 8945HS profile needs approximately 32 GB RAM.'
  PROFILE=k11
else
  fail "Unsupported: ${DEVICE:-$CPU_NAME} (~${MEM_GIB} GiB RAM). Supported: Pi 5, N95/N97, Ryzen 8945HS."
fi
[[ "$PROFILE" =~ ^(pi8|pi16|nuc16|k11)$ ]] || fail 'Invalid test profile.'
if [[ "$PROFILE" != k11 && ( "$MODEL_CHOICE" != auto || "$BACKEND_CHOICE" != auto || "$GPU_LAYERS_GIVEN" -eq 1 ) ]]; then
  fail '--model, --backend and --gpu-layers are for the Ryzen 8945HS profile.'
fi

# Find a mounted writable SSD or NVMe for Pi 8 GB model paging.
find_fast_storage() {
  command -v python3 >/dev/null && command -v lsblk >/dev/null || return 0
  python3 - <<'PY'
import json, os, subprocess
try:
    data=json.loads(subprocess.check_output(['lsblk','-J','-o','NAME,TYPE,TRAN,FSTYPE,MOUNTPOINT'],stderr=subprocess.DEVNULL))
except Exception:
    raise SystemExit(0)
found=[]
def walk(d,bus=''):
    bus=d.get('tran') or bus
    mount=d.get('mountpoint')
    if bus in ('nvme','usb') and mount and d.get('fstype')!='vfat' and os.path.isdir(mount):
        try:
            free=os.statvfs(mount).f_bavail * os.statvfs(mount).f_frsize
            if free >= 13_000_000_000 and (mount=='/' or os.access(mount,os.W_OK)):
                found.append((free,mount))
        except OSError: pass
    for child in d.get('children') or []: walk(child,bus)
for d in data.get('blockdevices',[]): walk(d)
if found:
    mount=max(found)[1]
    print('ROOT' if mount=='/' else mount)
PY
}
SSD_MOUNT=''
if [[ "$PROFILE" == pi8 && "$MODEL_DIR_GIVEN" -eq 0 ]]; then SSD_MOUNT="$(find_fast_storage || true)"; fi
if [[ "$MODE" == auto ]]; then
  if [[ "$PROFILE" == k11 ]]; then MODE=safe
  elif [[ "$PROFILE" == pi8 && "$MODEL_DIR_GIVEN" -eq 0 && -z "$SSD_MOUNT" ]]; then MODE=safe
  else MODE=best; fi
fi
if [[ "$PROFILE" == pi8 && "$MODE" == best && "$MODEL_DIR_GIVEN" -eq 0 && -z "$SSD_MOUNT" ]]; then
  fail 'Pi 8GB best needs an SSD/NVMe with at least 13 GB free; use --mode safe or --model-dir on SSD.'
fi
if [[ "$MODEL_DIR_GIVEN" -eq 0 ]]; then
  if [[ "$PROFILE" == pi8 && "$MODE" == best && "$SSD_MOUNT" != ROOT ]]; then
    MODEL_DIR="${SSD_MOUNT%/}/edge-llm-models"
  else MODEL_DIR="$HOME_DIR/models"; fi
fi
[[ "$MODEL_DIR" == /* ]] || fail 'Model directory must be an absolute path.'
case "$MODEL_DIR" in *$'\n'*|*$'\r'*) fail 'Invalid model directory newline.' ;; esac

ENGINE=upstream
if [[ "$PROFILE" == k11 && "$MODEL_CHOICE" != auto ]]; then MODE=custom; fi
case "$PROFILE:$MODE" in
  pi8:safe)
    MODEL_NAME='Qwen3.5 2B Q4_K_M'; HF_REPO='unsloth/Qwen3.5-2B-GGUF'; GGUF='Qwen3.5-2B-Q4_K_M.gguf'
    BYTES=1900000000; CONTEXT=4096; UBATCH=256 ;;
  pi8:best)
    MODEL_NAME='Qwen3 30B-A3B (SSD, experimental)'; HF_REPO='byteshape/Qwen3-30B-A3B-Instruct-2507-GGUF'
    GGUF='Qwen3-30B-A3B-Instruct-2507-Q3_K_S-2.66bpw.gguf'
    BYTES=10200000000; CONTEXT=2048; UBATCH=128; ENGINE=ik ;;
  pi16:safe|nuc16:safe)
    MODEL_NAME='Qwen3.5 4B Q4_K_M'; HF_REPO='ggml-org/Qwen3.5-4B-GGUF'; GGUF='Qwen3.5-4B-Q4_K_M.gguf'
    BYTES=3300000000; CONTEXT=4096; UBATCH=256 ;;
  pi16:best)
    MODEL_NAME='Qwen3.6 35B-A3B CPU-3 (tight fit)'; HF_REPO='byteshape/Qwen3.6-35B-A3B-GGUF'
    GGUF='Qwen3.6-35B-A3B-Q3_K_S-3.39bpw.gguf'
    BYTES=14700000000; CONTEXT=1024; UBATCH=64 ;;
  nuc16:best)
    MODEL_NAME='Qwen3.6 35B-A3B CPU-2'; HF_REPO='byteshape/Qwen3.6-35B-A3B-GGUF'
    GGUF='Qwen3.6-35B-A3B-Q3_K_S-2.71bpw.gguf'
    BYTES=11700000000; CONTEXT=4096; UBATCH=128 ;;
  k11:best|k11:safe|k11:custom)
    if [[ "$MODEL_CHOICE" == auto && "$MODE" == best ]]; then MODEL_CHOICE=gemma4; fi
    if [[ "$MODEL_CHOICE" == auto && "$MODE" == safe ]]; then MODEL_CHOICE=gemma4-e4b; fi
    GTT_MIN_GIB=0
    case "$MODEL_CHOICE" in
      gemma4-e4b)
        MODEL_NAME='Gemma 4 E4B Q4_K_M (safe, Vulkan)'; HF_REPO='unsloth/gemma-4-E4B-it-GGUF'
        GGUF='gemma-4-E4B-it-Q4_K_M.gguf'; BYTES=4980000000; CONTEXT=8192 ;;
      inkling)
        MODEL_NAME='Inkling 2 Mini IQ4_NL (MoE)'; HF_REPO='ggml-org/Inkling-2-Mini-GGUF'
        GGUF='Inkling-2-Mini-IQ4_NL.gguf'; BYTES=17630000000; CONTEXT=8192; GTT_MIN_GIB=20 ;;
      qwen38)
        MODEL_NAME='Qwen3.8 27B Q4_K_M (dense)'; HF_REPO='ggml-org/Qwen3.8-27B-GGUF'
        GGUF='Qwen3.8-27B-Q4_K_M.gguf'; BYTES=19400000000; CONTEXT=8192; GTT_MIN_GIB=22 ;;
      qwen36)
        MODEL_NAME='Qwen3.6 35B-A3B UD-Q4_K_M (MoE, advanced)'; HF_REPO='unsloth/Qwen3.6-35B-A3B-GGUF'
        GGUF='Qwen3.6-35B-A3B-UD-Q4_K_M.gguf'; BYTES=22100000000; CONTEXT=8192; GTT_MIN_GIB=24 ;;
      gemma4)
        MODEL_NAME='Gemma 4 26B-A4B Q4_K_M (best, MoE)'; HF_REPO='lmstudio-community/gemma-4-26B-A4B-it-GGUF'
        GGUF='gemma-4-26B-A4B-it-Q4_K_M.gguf'; BYTES=16800000000; CONTEXT=8192; GTT_MIN_GIB=22 ;;
      gptoss20b)
        MODEL_NAME='gpt-oss 20B MXFP4 (MoE)'; HF_REPO='ggml-org/gpt-oss-20b-GGUF'
        GGUF='gpt-oss-20b-mxfp4.gguf'; BYTES=12110000000; CONTEXT=8192 ;;
      qwen35-9b)
        MODEL_NAME='Qwen3.5 9B Q4_K_M (safer)'; HF_REPO='SoAIHQ/Qwen3.5-9B-GGUF'
        GGUF='Qwen3.5-9B-Q4_K_M.gguf'; BYTES=5780000000; CONTEXT=16384 ;;
    esac
    UBATCH=256 ;;
esac
if [[ -n "$CONTEXT_OVERRIDE" ]]; then CONTEXT="$((10#$CONTEXT_OVERRIDE))"; fi
CPU_THREADS="$(getconf _NPROCESSORS_ONLN || echo 4)"
(( CPU_THREADS > 4 )) && CPU_THREADS=4
(( CPU_THREADS < 1 )) && CPU_THREADS=1
[[ "$PROFILE" == pi16 && "$MODE" == best ]] && CPU_THREADS=3
[[ "$PROFILE" != k11 ]] || CPU_THREADS=8
BATCH_THREADS="$CPU_THREADS"
BACKEND=cpu
[[ "$PROFILE" != k11 ]] || BACKEND="$BACKEND_CHOICE"

printf '\nHardware:  %s | %s | ~%s GiB RAM\n' "$PROFILE" "${DEVICE:-$CPU_NAME}" "$MEM_GIB"
printf 'Mode:      %s\nModel:     %s\nEngine:    %s llama.cpp\nBackend:   %s\nContext:   %s\nDownload:  ~%s GB\nStorage:   %s\nAPI:       http://127.0.0.1:8080/v1\n' \
  "$MODE" "$MODEL_NAME" "$ENGINE" "$BACKEND" "$CONTEXT" "$(( (BYTES + 999999999) / 1000000000 ))" "$MODEL_DIR"
if [[ "$PROFILE" == k11 ]]; then
  GTT_TOTAL_BYTES="$(for f in /sys/class/drm/card*/device/mem_info_gtt_total; do
    if [[ -r "$f" ]]; then cat "$f"; fi
  done | sort -nr | head -n 1 || true)"
  if [[ "$GTT_TOTAL_BYTES" =~ ^[0-9]+$ ]]; then
    GTT_TOTAL_GIB=$((GTT_TOTAL_BYTES / 1024 / 1024 / 1024))
    info "GPU-addressable GTT: ~${GTT_TOTAL_GIB} GiB; requested full offload needs ~${GTT_MIN_GIB} GiB."
  else
    GTT_TOTAL_GIB=0
    info 'Cannot read GPU GTT limit; full offload is unverified.'
  fi
  info 'Radeon 780M shares RAM: Vulkan is preferred but Linux GPU-addressable memory (GTT) may limit full offload.'
  if (( GTT_MIN_GIB > 0 )) && (( GPU_LAYERS_GIVEN == 0 )) && [[ "$BACKEND_CHOICE" != cpu ]] &&
     (( GTT_TOTAL_GIB > 0 && GTT_TOTAL_GIB < GTT_MIN_GIB )); then
    info "Full Vulkan offload is unlikely at current GTT (${GTT_TOTAL_GIB} GiB)."
    if (( DRY_RUN == 0 )); then
      fail "Choose --mode safe, --backend cpu or a partial --gpu-layers value; see docs/K11.md for optional, reversible GTT tuning."
    fi
  fi
  info 'If Vulkan allocation fails, rerun with --gpu-layers 16 or --backend cpu. No kernel/BIOS changes are automatic.'
elif [[ "$PROFILE" == pi8 && "$MODE" == best ]]; then
  info 'Experimental SSD-backed inference; speed may not match Potato OS benchmarks.'
elif [[ "$PROFILE" == pi16 && "$MODE" == best ]]; then
  info 'Very tight on 16 GB RAM. Use --mode safe if OOM-killed.'
fi
(( DRY_RUN == 0 )) || exit 0
if (( YES == 0 )); then
  [[ -t 0 ]] || fail 'Noninteractive installation requires --yes.'
  read -r -p 'Install this model and enable the local service? [Y/n] ' response
  [[ ! "$response" =~ ^[Nn] ]] || { info 'Cancelled.'; exit 0; }
fi

info 'Installing dependencies'
if command -v apt-get >/dev/null; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    git cmake build-essential pkg-config curl ca-certificates python3 python3-venv python3-pip \
    libcurl4-openssl-dev libopenblas-dev
  if [[ "$PROFILE" == k11 && "$BACKEND_CHOICE" != cpu ]]; then
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      libvulkan-dev glslc spirv-headers mesa-vulkan-drivers vulkan-tools
  fi
elif command -v pacman >/dev/null; then
  sudo pacman -S --needed --noconfirm \
    git cmake base-devel pkgconf curl ca-certificates python python-pip openblas
  if [[ "$PROFILE" == k11 && "$BACKEND_CHOICE" != cpu ]]; then
    sudo pacman -S --needed --noconfirm vulkan-headers vulkan-radeon vulkan-tools shaderc
  fi
else fail 'Requires apt or pacman.'; fi

if [[ "$PROFILE" == k11 && "$BACKEND_CHOICE" != cpu ]]; then
  if command -v vulkaninfo >/dev/null && vulkaninfo --summary 2>&1 | grep -Eqi 'DRIVER_ID_MESA_RADV|driverName.*radv|RADV PHOENIX'; then
    BACKEND=vulkan
    info 'Mesa RADV Vulkan device confirmed.'
  elif [[ "$BACKEND_CHOICE" == vulkan ]]; then
    fail 'No working Mesa RADV device found. Install/update Mesa or choose --backend cpu.'
  else
    BACKEND=cpu
    info 'No working AMD Vulkan device detected; selecting CPU backend.'
  fi
fi

mkdir -p "$SOURCE_DIR"
mkdir -p "$MODEL_DIR" 2>/dev/null || fail "Cannot create model directory $MODEL_DIR; set --model-dir to a writable path."
[[ -w "$MODEL_DIR" ]] || fail "Model directory is not writable: $MODEL_DIR"
FREE_BYTES="$(df -PB1 "$MODEL_DIR" | awk 'END{print $4}')"
if [[ ! -s "$MODEL_DIR/$GGUF" ]] && (( FREE_BYTES < BYTES + 2000000000 )); then
  fail "Not enough disk space for $GGUF; keep at least 2 GB spare."
fi
if [[ "$ENGINE" == ik ]]; then
  GIT_URL=https://github.com/ikawrakow/ik_llama.cpp.git
  SRC="$SOURCE_DIR/ik_llama.cpp"
  BUILD_DIR="$SRC/build"
else
  GIT_URL=https://github.com/ggml-org/llama.cpp.git
  SRC="$SOURCE_DIR/llama.cpp"
  BUILD_DIR="$SRC/build-$BACKEND"
fi
if [[ ! -d "$SRC/.git" ]]; then
  info "Cloning $GIT_URL"
  git clone --depth=1 "$GIT_URL" "$SRC"
else info 'Reusing previously downloaded source.'; fi
if [[ "$ENGINE" == ik ]]; then
  cmake -S "$SRC" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON \
    -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS -DGGML_CPU_KLEIDIAI=OFF \
    -DGGML_VULKAN=OFF -DLLAMA_BUILD_SERVER=ON
else
  if [[ "$BACKEND" == vulkan ]]; then VULKAN_CMAKE=ON; else VULKAN_CMAKE=OFF; fi
  cmake -S "$SRC" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_CURL=ON \
    -DGGML_VULKAN="$VULKAN_CMAKE" -DGGML_CUDA=OFF -DLLAMA_BUILD_SERVER=ON
fi
info "Building $BACKEND llama.cpp server"
cmake --build "$BUILD_DIR" --parallel "$CPU_THREADS" --target llama-server
BIN="$BUILD_DIR/bin/llama-server"
[[ -x "$BIN" ]] || fail "Missing $BIN after build."
if [[ ! -s "$MODEL_DIR/$GGUF" ]]; then
  info "Downloading $GGUF"
  python3 -m venv "$HOME_DIR/venv"
  "$HOME_DIR/venv/bin/python" -m pip install --quiet --upgrade huggingface_hub
  "$HOME_DIR/venv/bin/hf" download "$HF_REPO" "$GGUF" --local-dir "$MODEL_DIR"
fi
[[ -s "$MODEL_DIR/$GGUF" ]] || fail 'Model file not downloaded.'

GPU_CONFIG='-ngl 0'
CACHE_CONFIG=''
BATCH_CONFIG="-ub ${UBATCH}"
if [[ "$PROFILE" == k11 ]]; then
  if [[ "$BACKEND" == vulkan ]]; then GPU_CONFIG="-ngl ${GPU_LAYERS}"; fi
  CACHE_CONFIG='-fa on -ctk q8_0 -ctv q8_0'
  BATCH_CONFIG="-b 512 -ub ${UBATCH}"
fi
q_bin="$(printf '%q' "$BIN")"
q_model="$(printf '%q' "$MODEL_DIR/$GGUF")"
LAUNCH="$HOME_DIR/start.sh"
cat >"$LAUNCH" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec ${q_bin} -m ${q_model} \\
  --alias edge-llm --host 127.0.0.1 --port 8080 \\
  ${GPU_CONFIG} -t ${CPU_THREADS} --threads-batch ${BATCH_THREADS} -c ${CONTEXT} -np 1 \\
  ${BATCH_CONFIG} ${CACHE_CONFIG} --jinja
EOF
chmod 755 "$LAUNCH"
UNIT_TMP="$HOME_DIR/edge-llm.service"
cat >"$UNIT_TMP" <<EOF
[Unit]
Description=Local model server (${MODEL_NAME})
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$(id -un)
Group=$(id -gn)
WorkingDirectory=${HOME_DIR}
ExecStart=/usr/bin/bash ${LAUNCH}
Restart=on-failure
RestartSec=10
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
info 'Installing local-only systemd service'
sudo install -m 0644 "$UNIT_TMP" /etc/systemd/system/edge-llm.service
sudo systemctl daemon-reload
sudo systemctl enable edge-llm.service
sudo systemctl restart edge-llm.service
info "Installed $MODEL_NAME using $BACKEND; service load may take a while."
printf '\n  API:    http://127.0.0.1:8080/v1\n  Model:  edge-llm\n  Logs:   journalctl -u edge-llm -f\n  Test:   curl http://127.0.0.1:8080/v1/models\n'
