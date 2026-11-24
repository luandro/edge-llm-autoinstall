---
name: edge-llm-autoinstall
description: Deploy and benchmark offline AI on Pi 5, N95/N97 and K11
compatibility: Hermes Agent with terminal or SSH access to Linux with systemd; internet needed for initial model downloads.
metadata:
  author: luandro
  version: "1.0.0"
---

# Edge AI Fleet Installer

## When to Use

Use this skill when asked to **install, troubleshoot, benchmark, or tune local/offline AI** on Raspberry Pi 5 (4, 8, or 16 GB), Intel Alder Lake-N N95/N97 (16 GB), or GMKtec K11 / Ryzen 9 8945HS / Radeon 780M (32 GB). Also use it to choose models for **Brazilian Portuguese (pt-BR) summarization, STT, EN→PT-BR translation**, and lightweight local agent workflows.

This skill is a deployment procedure, not a promise that every workload is already implemented. Read the target repository's current `README.md` and `install.sh --help` before any installation.

## Source of Truth and Current Scope

- Public project: https://github.com/luandro/edge-llm-autoinstall
- Installer: `install.sh`; tests: `tests/smoke.sh`; text benchmark: `scripts/benchmark.py`.
- Read the matching reference in the checkout: `docs/K11.md`, `docs/PI5_4GB.md`, `docs/TASK_RESEARCH_NOTES.md`, and other `docs/` research when relevant. Treat benchmark estimates as **unverified on the target** until measured.
- **Currently implemented:** one GGUF LLM via `llama.cpp` (or experimental `ik_llama.cpp` on Pi 8 GB best), installed as `edge-llm.service`, OpenAI-compatible chat at `http://127.0.0.1:8080/v1`, model ID `edge-llm`, localhost only.
- **Not implemented yet:** transcription endpoint, dedicated STT engine, dedicated neural translation engine, unified multi-model pipeline, automated model unloading or benchmark-based tuning. Do not claim they work or invent `--task`/`--tasks` flags. Request an implementation task before modifying this repository to add them.

## Procedure

### 1. Establish the target and perform read-only inspection

Use Hermes' terminal (locally or through authorized SSH). Do not confuse the Hermes controller's hardware with the remote **target**. Confirm which host will be changed. Ask only for truly missing access/permission information.

Run on the target:

```bash
uname -sm
cat /proc/device-tree/model 2>/dev/null || true
lscpu | grep -E 'Model name|Architecture|CPU\(s\)|Thread|Core' || true
free -h
lsblk -o NAME,SIZE,TYPE,TRAN,FSTYPE,MOUNTPOINTS
df -h "$HOME"
command -v systemctl && command -v sudo
```

For Pi: `vcgencmd get_throttled` and `vcgencmd measure_temp` if available. For K11: `vulkaninfo --summary`, `cat /sys/class/drm/card*/device/mem_info_gtt_total 2>/dev/null`, and `sudo dmidecode -t memory` **only with permission** to check channel population, configured DDR speed and GTT. Note actual RAM, storage medium, kernel/Mesa versions, CPU governor, temperature, and free disk. Do not infer dual-channel from total GB alone.

Require Linux, systemd, sufficient writable storage, initial internet access for packages and model downloads, and ability to run authorized sudo. Use Raspberry Pi OS **64-bit** and active cooling on Pi. A remote target must be reachable through an authorized SSH tunnel/VPN, not a public unauthenticated API.

### 2. Choose a safe starting point

| Target | Safer starting model (`--mode safe`) | Highest-capability *experimental/opt-in* (`--mode best`) |
| --- | --- | --- |
| Pi 5, 4 GB | Qwen3.5 0.8B Q4, 4K context | Qwen3.5 2B Q4, 2K context (tight memory) |
| Pi 5, 8 GB | Qwen3.5 2B Q4, 4K context | Qwen3 30B-A3B Q3 via `ik_llama`, SSD-backed, 2K context |
| Pi 5, 16 GB | Qwen3.5 4B Q4, 4K context | Qwen3.6 35B-A3B CPU-3, 1K context, very tight fit |
| Intel N95/N97, 16 GB | Qwen3.5 4B Q4, 4K context | Qwen3.6 35B-A3B CPU-2, 4K context, often slow |
| GMKtec K11, 32 GB | Gemma 4 E4B Q4, 8K context, Vulkan if RADV works | Gemma 4 26B-A4B Q4, 8K context, requires ~22 GiB GPU-addressable GTT for full offload |

**Default to safe for first deployment**, especially on headless fleet nodes or machines serving other workloads. `--mode auto` is not uniformly safe: it selects **best** on Pi 16 GB and N95/N97, as well as on Pi 8 GB with detected SSD. Pi 4 GB and K11 select safe automatically. Treat large-model profiles as an opt-in experiment, never a guaranteed fast installation.

### Optional tool-use models, by explicit request only

`bash install.sh --agent-model botpsy` and `--agent-model mini-agent` work on **all supported machines** as experimental alternatives. **BotPsy 0.8B** is an English-first thinking-enabled tool router; **mini-agent-v2 1.5B** is optimized for Bash, Python and small tool calls. On Pi 4 GB the installer uses Q4; on larger devices BotPsy uses Q8 and mini-agent Q5. They **replace**, rather than augment, the one local LLM service. There is no task router, simultaneous model loading or automatic delegation.

Before testing these, read `docs/AGENT_MODELS.md` for the quantified evidence, limits, licenses, safe test plan and rollback. The **LFM3-1.7B Hermes RL LoRA** is documented as a **manual research experiment only**, not an installed option: the authors evaluated a 64K+ context workflow and did not re-evaluate the GGUF adapter. Do not treat an 8K Pi run as equivalent, or promote a specialist as the default PT-BR summarizer/translator.

```bash
bash install.sh --agent-model botpsy --dry-run
bash install.sh --agent-model mini-agent --dry-run
# After approval, select exactly one:
bash install.sh --agent-model mini-agent
# Run read-only/sandboxed tool-call tests, including no-tool decisions and PT-BR prompts.
bash install.sh --mode safe   # restore the general-purpose baseline
```

K11 optional `--model` choices: `gemma4-e4b`, `gemma4`, `qwen36` (larger agent/coding MoE; ~24 GiB GTT), `inkling` (English-focused, unverified on this K11), `qwen38` (dense, likely slow), `gptoss20b`, `qwen35-9b`. Model and GPU override flags work **only** on K11. Do not apply NVIDIA CUDA/NInfer-all instructions to the AMD 780M.

### 3. Review, preview, approve once, install

```bash
git clone --depth=1 https://github.com/luandro/edge-llm-autoinstall.git
cd edge-llm-autoinstall
bash -n install.sh
bash tests/smoke.sh
bash install.sh --mode safe --dry-run
```

If checkout already exists: inspect `git status --short`; do not overwrite local changes. Update with `git pull --ff-only` only when clean and after reviewing what changed.

Review `install.sh` from the trusted source before running it with sudo privileges. Show the operator the detected profile, chosen model, download size, target model directory, memory/disk constraints, potential service changes, and any missing requirements. Preserve the existing service configuration before replacing it when it exists (requires approval). Get one approval for installation/package downloads and systemd changes. **Never use `--yes` without prior explicit authorization for unattended deployment.**

```bash
bash install.sh --mode safe
# After a successful safe baseline, only if requested and resources permit:
bash install.sh --mode best
# K11 choices:
bash install.sh --model qwen36 --backend auto
bash install.sh --model inkling --gpu-layers 16
```

`--model-dir /absolute/path` directs weights to a mounted disk. For Pi 8 GB `--mode best`, first ensure **SSD/NVMe** with ≥13 GB free and verify that the weights actually live there; microSD paging is not equivalent. On Pi 4 GB use `--mode safe` first; keep other services small and do not raise context above the installer's 4K cap. The script compiles locally, downloads GGUF weights and creates a persistent local-only `edge-llm.service`. Do **not** claim the install is complete until the service and an inference request work.

### 4. Verify functionality and measure real performance

```bash
sudo systemctl is-active edge-llm
curl --fail --silent http://127.0.0.1:8080/v1/models
ss -ltnp | grep ':8080'
python3 scripts/benchmark.py --output "$HOME/edge-llm-benchmark.json"
```

If the service fails: `journalctl -u edge-llm -n 120 --no-pager`. Verify `ss` shows only `127.0.0.1:8080`; do not open it on `0.0.0.0` for convenience. Benchmark tool tests translation, summary and instruction-following **through the LLM chat API**; it does **not** benchmark STT or dedicated NMT. It also does **not** benchmark real Hermes tool-calling; for agent profiles use the separate controlled tests specified in `docs/AGENT_MODELS.md`.

On the target, capture temperature/throttling, peak RAM/swap, GTT usage (K11), model/quantization, backend, CPU threads, context, microbatch, prompt processing, generation tok/s, latency and errors. Use consistent Portuguese transcription/translation/summary samples and compare **factual correctness** (names, numbers, dates, actions) as well as speed. Run at least three warm trials for each candidate; document cold-load delay separately. Never present estimates from another computer as a measured result from this one.

### 4a. Compare multiple models reproducibly (benchmark runner)

For new deployments, upgrades and tool-optimized models, **measure alternatives before changing the production service**. The benchmark runner is independent from `install.sh`: it starts one temporary local `llama-server` at a time, selects an unused loopback port, downloads cached GGUFs in user space, and does not execute any commands suggested by the model. Read `docs/BENCHMARKING.md` first.

```bash
bash benchmark.sh --dry-run --models small
bash benchmark.sh --models small --suite quick --runs 1
bash benchmark.sh --models edge --suite full --runs 3
# Optional LFM3 base vs Hermes LoRA with explicit model-license review:
bash benchmark.sh --models adapter --suite full --runs 3
# Existing single service, no downloading/compilation:
bash benchmark.sh --server-url http://127.0.0.1:8080 --suite full --runs 3
```

`small` covers Qwen3.5 0.8B Q4, BotPsy 0.8B Q4, mini-agent-v2 Q4 and Qwen3.5 2B Q4; `edge` adds Qwen3.5 4B and Gemma 4 E4B. `all` includes many very large models; **never run it by default** or silently bypass the download limit. `--yes` is permitted only if the operator explicitly approved cached package/model downloads and unprivileged compilation; there is no sudo/systemd modification in the runner.

Run the full suite on the **actual** Pi/N95/K11 to measure real prompt/decode latency and peak RAM. Cloud Colab CUDA helps compare behavior but **cannot predict ARM, N95/N97 or Radeon Vulkan speeds**. On the physical device, use consistent task/context/backend, and repeat 3× if feasible. Reports are under `reports/<UTC timestamp>/`. Prefer `comparison.csv` and `results.json`; manually inspect PT-BR translations/summaries because the built-in quality scores only check names/terms/fact overlap, not semantic correctness or unsupported claims. Benchmark tool calls are proposals only—**not an end-to-end Hermes execution test**. Never execute model-suggested Bash/Python commands on a real machine during testing.

### 5. Find the best *stable* settings

- **Pi 5:** CPU only, usually 4 threads (Pi 16 GB best uses 3), low RAM overhead; test 2K versus 4K context. On 4 GB avoid other resident models and aggressive swap. A 16 GB Pi is not faster than an 8 GB Pi simply because it has more RAM.
- **Intel N95/N97:** CPU-only with 4 threads; memory bandwidth limits larger dense models. Start 4K context, one request, small microbatch; compare wall-clock quality and prompt-processing time before accepting a huge MoE.
- **K11:** use latest practical upstream `llama.cpp` with Vulkan **Mesa RADV**; fallback CPU when Vulkan cannot allocate or hardware lacks memory bandwidth. Initial settings: 8 physical CPU threads, 8K context, `-ub 256`, one request, flash attention and q8_0 K/V cache. Check **available GTT**, not just 32 GB total RAM. Full GPU offload of Gemma 26B (~22 GiB GTT) or Qwen3.6 (~24 GiB GTT) may be unavailable without manual changes; use the safe model or partial `--gpu-layers` first.
- Avoid enabling MTP, speculative decoding, custom quants or ROCm by default until model/runtime support, speed and correctness have been verified on the actual device. SSD is for model storage, **not** a replacement for RAM. Do not automatically edit BIOS, modprobe, kernel GTT/TTM, initramfs or swap settings.
- Changes to threads, batch and cache not exposed by `install.sh` require a reviewed code change or documented manual test. Re-running the installer overwrites the generated `start.sh`, so do not treat hand edits as persistent configuration.

### 6. Route workloads honestly

- **Summarization now:** use `/v1/chat/completions` with a Portuguese prompt; chunk long transcriptions to fit context and preserve timestamps and factual details. Compare answers using `scripts/benchmark.py`.
- **EN→PT-BR now:** LLM translation through chat can be tested; there is no dedicated `/v1/translate` endpoint. The planned lightweight translator is CTranslate2 INT8 + OPUS-MT, with explicit Brazilian Portuguese evaluation.
- **pt-BR STT not yet installed:** candidates include Parakeet TDT 0.6B v3 multilingual ONNX INT8 + Silero VAD, or CPU `whisper.cpp` / faster-whisper. TAGARELA pt-BR derivatives have possible **non-commercial** upstream dataset restrictions; never auto-install those for an unrestricted/commercial workflow. NLLB distilled models also need license review.
- For future multi-stage audio → STT → translate → summarize on 4/8 GB machines, unload one model before loading the next, preserve timestamped text between stages and verify peak RSS. Do not promise a working pipeline until it is implemented and end-to-end tested in the repository.

## Pitfalls and Recovery

- **OOM / service crash:** inspect `journalctl -u edge-llm`, `free -h`, `dmesg` (permission permitting) and `df -h`. Reduce context / choose safe; on K11 reduce GPU layers or use `--backend cpu`. If changing models failed, reinstall the known-good safe profile; installer has **no automatic rollback**.
- **GPU Vulkan failure:** ensure Mesa RADV, working `/dev/dri` permissions and GTT headroom; do not force ROCm or kernel tuning to bypass a failed safety check.
- **Wrong hardware profile / unsupported system:** stop and report diagnostics; don't spoof production hardware through the dry-run-only `EDGE_LLM_TEST_PROFILE` variable.
- **Service appears started but chat fails:** wait for model load; check `/v1/models`, test an actual completion, review logs and file sizes. A nonempty downloaded file is not proof of full integrity; check it before retrying a suspected truncated download.
- **Remote agent setup:** local-only means API is reachable from the target's own loopback. Use an SSH tunnel/private VPN for access from Hermes; never publish an unauthenticated listener on the internet.

## Verification / Report Back

Return a concise result with: target identifier (no secrets), detected hardware, RAM/channel and storage, OS, chosen model + quantization, safe/best choice, backend, threads/context/microbatch, service status, loopback API URL, one successful chat response, measured throughput and temperature, notes about any manual overrides, and any outstanding STT/NMT tasks. Mark missing hardware tests as **unverified** and leave a clear safe fallback. Keep logs/transcripts on the target unless the operator explicitly authorizes sharing.
