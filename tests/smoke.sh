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
