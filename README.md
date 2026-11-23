# Edge LLM Auto Installer

One `install.sh` for **Raspberry Pi 5 (8/16 GB)**, **Intel N95/N97 (16 GB)** and **GMKtec K11 / AMD Ryzen 9 8945HS (32 GB, Radeon 780M)** on Linux with systemd.

## Install

```bash
bash install.sh
```

The installer detects supported hardware, explains its plan and requests one approval. On K11, automatic mode deliberately selects the safe model; large full-offload setups are opt-in. It installs `llama.cpp`, downloads one GGUF model and creates a local-only systemd service. Existing models remain on disk when changing profiles.

```bash
bash install.sh --mode safe      # smaller, more reliable model
bash install.sh --mode best      # larger, higher-capability model
bash install.sh --dry-run        # detection and plan only
bash install.sh --yes            # no interactive confirmation
```

## Models

| Hardware | Best (`--mode best`) | Safe (`--mode safe`) |
| --- | --- | --- |
| Pi 5, 8 GB | Qwen3 30B-A3B Q3_K_S, SSD-backed experimental | Qwen3.5 2B Q4 |
| Pi 5, 16 GB | Qwen3.6 35B-A3B CPU-3, very tight on RAM | Qwen3.5 4B Q4 |
| Intel N95/N97, 16 GB | Qwen3.6 35B-A3B CPU-2, slow on bandwidth-limited CPU | Qwen3.5 4B Q4 |
| **Ryzen 8945HS, 32 GB** | **Gemma 4 26B-A4B Q4, opt-in GTT capacity** | **Gemma 4 E4B Q4, no kernel tuning** |

The Pi 8 GB automatically selects safe mode if it cannot locate usable SSD/NVMe storage; override with `--model-dir` to a mounted SSD. For GPU setups, Vulkan requires Mesa/Vulkan and sufficient GPU-addressable shared system memory (GTT).

## GMKtec K11 (Ryzen 8945HS, Radeon 780M)

```bash
bash install.sh --dry-run                 # inspect selection
bash install.sh                           # safe Gemma 4 E4B by default
bash install.sh --mode best               # Gemma 4 26B-A4B, if enough GPU GTT
bash install.sh --model qwen36            # Qwen3.6 35B-A3B, advanced coding
bash install.sh --model inkling           # English coding experimental
bash install.sh --model qwen38            # dense Qwen3.8 (slower)
bash install.sh --model gptoss20b         # alternative MoE for tools
```

The K11 runs a recent upstream **llama.cpp + Vulkan Mesa RADV** build when available, or falls back to CPU. It uses 8 CPU threads, Q8 K/V cache, `-ub 256`, flash attention and a single active request. Default context is 8K. Linux GPU-addressable shared memory (GTT) can be smaller than physical RAM: the installer blocks insufficient full-offload configurations when the GTT limit is known. The installer **never changes kernel or BIOS memory settings**. See [K11 research and guidance](docs/K11.md).

**Current scope:** this one-script repository installs and serves **one LLM**. The supplied [K11 deep-research report](docs/K11_OFFLINE_AI_RESEARCH.md) informs a *next phase* for pt-BR STT (Parakeet/faster-whisper), EN→PT-BR translation (CTranslate2/OPUS-MT), summarization pipelines and dynamic model unloading. Those services are **not yet implemented**; don't assume `/v1/audio/transcriptions` works.

## API and management

- OpenAI-style endpoint: `http://127.0.0.1:8080/v1`
- Model ID: `edge-llm`
- Health check: `curl http://127.0.0.1:8080/v1/models`
- Logs: `journalctl -u edge-llm -f`
- Service: `sudo systemctl status edge-llm`
- Stop: `sudo systemctl stop edge-llm`

This API listens on `127.0.0.1`, not the LAN. Use an SSH tunnel or private VPN rather than exposing an unauthenticated API on the internet. Re-running the installer replaces the launch script/service settings, not downloaded weights. It does not automatically install STT or translation engines.

**Current validation:** shell syntax and selection dry runs are tested, not runtime inference on the target devices. The K11 model IDs for Gemma 4 E4B, Gemma 4 26B-A4B and Qwen3.6 were checked against Hugging Face listings. Published third-party performance reports are not guarantees of this script's performance or of stability at long contexts.

## Research

- [Deep research: offline pt-BR speech-to-text, EN→PT-BR translation and summarization](docs/DEEP_RESEARCH_PROMPT.md)
- [Ryzen 8945HS / Radeon 780M model options and tuning](docs/K11.md)

## Publish on GitHub

```bash
git init -b main
git add .
git commit -m "Add Pi 5, N95/N97 and AMD 8945HS installers"
gh repo create luandro/edge-llm-autoinstall --public --source . --remote origin --push
```

The repository must be created once using an authenticated GitHub CLI; the script itself does not require GitHub access.
