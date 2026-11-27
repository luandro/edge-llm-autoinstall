# Verification, benchmarking and stable settings

Read this after an installation or when measuring model alternatives. Never present estimates from another machine as measured results from the target.

## Verify functionality

```bash
sudo systemctl is-active edge-llm
curl --fail --silent http://127.0.0.1:8080/v1/models
ss -ltnp | grep ':8080'
python3 scripts/benchmark.py --output "$HOME/edge-llm-benchmark.json"
```

If the service fails: `journalctl -u edge-llm -n 120 --no-pager`. Verify `ss` shows only `127.0.0.1:8080`; do not open `0.0.0.0` for convenience. The text benchmark tests translation, summary and instruction-following **through the chat API**; it does **not** test STT, dedicated NMT or real Hermes tool calling. For agent profiles use the controlled tests in `docs/AGENT_MODELS.md`.

On the target capture temperature/throttling, peak RAM/swap, GTT usage (K11), model/quantization, backend, CPU threads, context, microbatch, prompt processing, generation tok/s, latency and errors. Use consistent Portuguese samples and compare **factual correctness** (names, numbers, dates, actions) as well as speed. Run at least three warm trials per candidate; document cold-load delay separately.

## Compare models reproducibly (benchmark runner)

Read `docs/BENCHMARKING.md` first. The runner is independent of `install.sh`: one temporary `llama-server` at a time on an unused loopback port, cached GGUFs in user space, and it never executes commands suggested by the model.

```bash
bash benchmark.sh --dry-run --models small
bash benchmark.sh --models small --suite quick --runs 1
bash benchmark.sh --models edge --suite full --runs 3
# Optional LFM3 base vs adapter, with explicit license review:
bash benchmark.sh --models adapter --suite full --runs 3
# Existing service, no download/compile:
bash benchmark.sh --server-url http://127.0.0.1:8080 --suite full --runs 3
```

`small` covers Qwen3.5 0.8B Q4, BotPsy 0.8B Q4, mini-agent-v2 Q4 and Qwen3.5 2B Q4; `edge` adds Qwen3.5 4B and Gemma 4 E4B. `all` includes very large models: **never run it by default** or silently bypass the download limit. `--yes` is permitted only if the operator explicitly approved cached downloads and unprivileged compilation; the runner never touches sudo/systemd.

Run the full suite on the **actual** hardware. Cloud Colab CUDA helps compare behavior but **cannot predict** ARM, N95/N97 or Radeon Vulkan speeds. Use consistent task/context/backend and repeat 3x if feasible. Reports land under `reports/<UTC timestamp>/`; prefer `comparison.csv` and `results.json`. Manually inspect PT-BR translations/summaries — built-in scores check term overlap, not semantic correctness or unsupported claims. Benchmark tool calls are proposals only, **not** an end-to-end Hermes execution test. Never execute model-suggested Bash/Python on a real machine during testing.

## Stable settings by target

- **Pi 5:** CPU only, usually 4 threads (Pi 16 GB best uses 3), low RAM overhead; test 2K vs 4K context. On 4 GB avoid other resident models and aggressive swap. More RAM does not mean more speed.
- **Intel N95/N97:** CPU-only, 4 threads; memory bandwidth limits larger dense models. Start 4K context, one request, small microbatch; compare wall-clock quality and prompt-processing time before accepting a large MoE.
- **K11:** upstream `llama.cpp` with Vulkan **Mesa RADV**; CPU fallback when Vulkan cannot allocate or bandwidth is insufficient. Initial: 8 physical threads, 8K context, `-ub 256`, one request, flash attention, q8_0 K/V cache. Check **available GTT**, not just 32 GB total RAM. Full offload of Gemma 26B (~22 GiB) or Qwen3.6 (~24 GiB) may be unavailable; use safe or partial `--gpu-layers` first.
- Avoid MTP, speculative decoding, custom quants and ROCm by default until verified on the actual device. SSD is for model storage, **not** a RAM replacement. Do not automatically edit BIOS, modprobe, kernel GTT/TTM, initramfs or swap.
- Changes to threads/batch/cache not exposed by `install.sh` need a reviewed code change or documented manual test. Re-running the installer overwrites generated `start.sh`; hand edits are not persistent.

## Route workloads honestly

- **Summarization:** `/v1/chat/completions` with a Portuguese prompt; chunk long transcriptions to fit context and preserve timestamps/facts. Compare with `scripts/benchmark.py`.
- **EN→PT-BR:** LLM translation through chat can be tested; no dedicated `/v1/translate` endpoint exists. A lightweight translator (CTranslate2 INT8 + OPUS-MT) is planned, not implemented.
- **pt-BR STT:** USB CLI uses multilingual Whisper base; benchmark on target. Research candidates: Parakeet TDT 0.6B v3 multilingual ONNX INT8 + Silero VAD, CPU `whisper.cpp`/faster-whisper. TAGARELA derivatives may carry **non-commercial** dataset restrictions; never auto-install for unrestricted/commercial use. NLLB distilled models need license review.
- Multi-stage audio→STT→translate→summarize on 4/8 GB remains unimplemented; unload one model before loading the next, preserve timestamped text and verify peak RSS. Do not promise a working pipeline.
