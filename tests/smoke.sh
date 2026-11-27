#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
bash -n install.sh

check() {
  local profile="$1" mode="$2" expected="$3" out
  out="$(EDGE_LLM_TEST_PROFILE="$profile" bash install.sh --mode "$mode" --dry-run --model-dir /tmp/edge-llm-ci-models)"
  grep -Fq "Model:     $expected" <<<"$out" || {
    printf 'FAILED: %s %s expected %s\n%s\n' "$profile" "$mode" "$expected" "$out" >&2
    exit 1
  }
  printf 'PASS: %-5s %-4s %s\n' "$profile" "$mode" "$expected"
}
check pi4 safe 'Qwen3.5 0.8B Q4_K_M'
check pi4 best 'Qwen3.5 2B Q4_K_M'
check pi8 safe 'Qwen3.5 2B Q4_K_M'
check pi8 best 'Qwen3 30B-A3B'
check pi16 safe 'Qwen3.5 4B Q4_K_M'
check pi16 best 'Qwen3.6 35B-A3B CPU-3'
check nuc16 safe 'Qwen3.5 4B Q4_K_M'
check nuc16 best 'Qwen3.6 35B-A3B CPU-2'
check k11 best 'Gemma 4 26B-A4B Q4_K_M'
check k11 safe 'Gemma 4 E4B Q4_K_M'
for spec in 'inkling|Inkling 2 Mini' 'qwen38|Qwen3.8 27B' 'qwen36|Qwen3.6 35B-A3B UD-Q4_K_M' 'gemma4|Gemma 4 26B-A4B' 'gemma4-e4b|Gemma 4 E4B Q4_K_M' 'gptoss20b|gpt-oss 20B MXFP4' 'qwen35-9b|Qwen3.5 9B'; do
  choice="${spec%%|*}"
  expected="${spec#*|}"
  out="$(EDGE_LLM_TEST_PROFILE=k11 bash install.sh --model "$choice" --dry-run --model-dir /tmp/edge-llm-ci-models)"
  grep -Fq "Model:     $expected" <<<"$out" || { printf 'FAILED: k11 %s\n%s\n' "$choice" "$out" >&2; exit 1; }
  printf 'PASS: k11 --model %s\n' "$choice"
done
for backend in auto vulkan cpu; do
  out="$(EDGE_LLM_TEST_PROFILE=k11 bash install.sh --model qwen38 --backend "$backend" --gpu-layers 16 --context 4096 --dry-run --model-dir /tmp/edge-llm-ci-models)"
  grep -Fq 'Context:   4096' <<<"$out" || { echo 'FAILED: context override' >&2; exit 1; }
  grep -Fq "Backend:   $backend" <<<"$out" || { echo 'FAILED: backend override' >&2; exit 1; }
done
if EDGE_LLM_TEST_PROFILE=pi8 bash install.sh --dry-run --model inkling --mode safe --model-dir /tmp/edge-llm-ci-models >/dev/null 2>&1; then
  echo 'FAILED: non-K11 --model should be rejected' >&2; exit 1
fi
echo 'PASS: K11 backend/context options and non-K11 option validation'

# Auto mode deliberately prioritizes safe, no-tuning use on K11.
auto_out="$(EDGE_LLM_TEST_PROFILE=k11 bash install.sh --dry-run --model-dir /tmp/edge-llm-ci-models)"
grep -Fq 'Mode:      safe' <<<"$auto_out" || { echo 'FAILED: k11 auto must be safe' >&2; exit 1; }
grep -Fq 'Model:     Gemma 4 E4B' <<<"$auto_out" || { echo 'FAILED: k11 auto model' >&2; exit 1; }
# All explicit selection paths should be consistent and accepted.
if EDGE_LLM_TEST_PROFILE=k11 bash install.sh --model lfm25 --dry-run >/dev/null 2>&1; then
  echo 'FAILED: unsupported model unexpectedly accepted' >&2; exit 1
fi
echo 'PASS: K11 auto-safe default and unsupported-model validation'

# Pi 4 GB must default to safe and reject RAM-heavy context overrides.
pi4_auto="$(EDGE_LLM_TEST_PROFILE=pi4 bash install.sh --dry-run --model-dir /tmp/edge-llm-ci-models)"
grep -Fq 'Mode:      safe' <<<"$pi4_auto" || { echo 'FAILED: pi4 auto mode' >&2; exit 1; }
grep -Fq 'Context:   4096' <<<"$pi4_auto" || { echo 'FAILED: pi4 safe context' >&2; exit 1; }
if EDGE_LLM_TEST_PROFILE=pi4 bash install.sh --mode best --context 8192 --dry-run >/dev/null 2>&1; then
  echo 'FAILED: pi4 context should be capped at 4096' >&2; exit 1
fi
grep -Fq 'Context:   2048' <<<"$(EDGE_LLM_TEST_PROFILE=pi4 bash install.sh --mode best --dry-run --model-dir /tmp/edge-llm-ci-models)" || { echo 'FAILED: pi4 best context' >&2; exit 1; }
echo 'PASS: Pi 4GB automatic/safe, best context and memory guard'

# Specialized agents are explicitly opt-in on every hardware class; safe/best stay unchanged.
for profile in pi4 pi8 pi16 nuc16 k11; do
  for agent in botpsy mini-agent; do
    out="$(EDGE_LLM_TEST_PROFILE="$profile" bash install.sh --agent-model "$agent" --dry-run --model-dir /tmp/edge-llm-ci-models)"
    grep -Fq 'Mode:      agent' <<<"$out" || { echo "FAIL: $profile $agent mode"; exit 1; }
    case "$agent:$profile" in
      botpsy:pi4) expected='botpsy-0.8b-q4_k_m-imat.gguf'; grep -Fq 'Context:   4096' <<<"$out" || exit 1 ;;
      botpsy:*) expected='botpsy-0.8b-q8_0.gguf' ;;
      mini-agent:pi4) expected='mini-agent-v2-Q4_K_M.gguf' ;;
      mini-agent:*) expected='mini-agent-v2-Q5_K_M.gguf' ;;
    esac
    grep -Fq "GGUF:      $expected" <<<"$out" || { echo "FAIL: $profile $agent GGUF filename"; exit 1; }
    grep -Fq 'API:       http://127.0.0.1:8080/v1' <<<"$out" || { echo "FAIL: $profile $agent API"; exit 1; }
    echo "PASS: $profile agent=$agent ($expected)"
  done
done
if EDGE_LLM_TEST_PROFILE=k11 bash install.sh --dry-run --agent-model botpsy --model gemma4 >/dev/null 2>&1; then
  echo 'FAIL: --agent-model and --model should be mutually exclusive'; exit 1
fi
if EDGE_LLM_TEST_PROFILE=pi4 bash install.sh --dry-run --agent-model fake >/dev/null 2>&1; then
  echo 'FAIL: invalid agent should be rejected'; exit 1
fi
echo 'PASS: agent model flags and mutually exclusive model selection'

# USB fixtures; no network or real device.
for f in prepare-usb.sh install-stt.sh scripts/usb-common.sh; do bash -n "$f"; done
source scripts/usb-common.sh
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
root="$tmp/USB space/edge-llm-usb"
mkdir -p "$root"
touch "$root/.edge-llm-usb-v1"
[[ "$(usb_root "$tmp/USB space")" == "$root" ]]
[[ "$(usb_select "$root" 1 1 "$PWD")" == "$root" ]]
if usb_select "$tmp/missing" 1 1 "$PWD"; then exit 1; fi
model=Qwen3.5-0.8B-Q4_K_M.gguf
bundle="$root/llm/$(usb_platform)/pi4/$model"
mkdir -p "$bundle"
printf 'fake binary' > "$bundle/llama-server"
printf 'GGUF fixture' > "$bundle/$model"
(cd "$bundle" && sha256sum llama-server "$model" > SHA256SUMS)
usb_check "$bundle" llama-server "$model"
out="$(EDGE_LLM_TEST_PROFILE=pi4 bash install.sh --offline --usb "$root" --dry-run)"
grep -Fq 'Offline USB:' <<<"$out"
grep -Fq 'Mode:      safe' <<<"$out"
if EDGE_LLM_TEST_PROFILE=pi4 bash install.sh --offline --usb "$root" --mode best --dry-run; then exit 1; fi
if EDGE_LLM_TEST_PROFILE=pi8 bash install.sh --offline --usb "$root" --dry-run; then exit 1; fi
printf 'corruption' >> "$bundle/$model"
if usb_check "$bundle" llama-server "$model"; then exit 1; fi
echo 'PASS: USB selection, profile matching, corruption rejection'

# Laptop preparation requires no supported hardware and no USB for plan.
bash -n scripts/rehearse-usb.sh
plan="$(bash prepare-usb.sh --dry-run)"
grep -q 'linux/amd64 + linux/arm64' <<<"$plan"
while IFS='|' read -r profile repo filename; do
  [[ "$profile" != \#* && "$profile" != stt && -n "$profile" ]] || continue
  out="$(EDGE_LLM_TEST_PROFILE="$profile" bash install.sh --online --mode safe --dry-run)"
  grep -Fq "GGUF:      $filename" <<<"$out"
done < scripts/usb-build/models.tsv
# Portable v2 selects correct architecture without matching OS directory.
portable="$root/portable/$(uname -m)/llm/$model"
mkdir -p "$portable"
cp "$bundle/llama-server" "$portable/"
printf 'GGUF fixture' > "$portable/$model"
(cd "$portable" && sha256sum llama-server "$model" > SHA256SUMS)
touch "$root/.portable-complete"
out="$(EDGE_LLM_TEST_PROFILE=pi4 bash install.sh --offline --usb "$root" --dry-run)"
grep -Fq "$portable" <<<"$out"
echo 'PASS: portable laptop plan, catalog, v2 bundle lookup'

printf 'edge-llm-usb v2\n' > "$root/.edge-llm-usb-v1"
rm "$root/.portable-complete"
if EDGE_LLM_TEST_PROFILE=pi4 bash install.sh --offline --usb "$root" --dry-run; then echo 'FAIL: incomplete v2 accepted'; exit 1; fi
echo 'PASS: incomplete v2 fails closed even with legacy bundle present'
