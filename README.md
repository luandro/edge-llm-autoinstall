# Edge LLM Auto Installer

One `install.sh` for **Raspberry Pi 5 (4/8/16 GB)**, **Intel N95/N97 (16 GB)** and **GMKtec K11 / AMD Ryzen 9 8945HS (32 GB, Radeon 780M)** on Linux with systemd.

## Install

```bash
git clone https://github.com/luandro/edge-llm-autoinstall.git
cd edge-llm-autoinstall
bash install.sh --mode safe
```

For a first unattended-fleet rollout, start with `--mode safe` rather than `--mode auto`: auto selects experimental best profiles on some machines.

The installer detects supported hardware, explains its plan and requests one approval. On K11, automatic mode deliberately selects the safe model; large full-offload setups are opt-in. It installs `llama.cpp`, downloads one GGUF model and creates a local-only systemd service. Existing models remain on disk when changing profiles.

```bash
bash install.sh --mode safe      # smaller, more reliable model
bash install.sh --mode best      # larger, higher-capability model
bash install.sh --dry-run        # detection and plan only
bash install.sh --yes            # no interactive confirmation
```

## Use as a Hermes Agent skill

Install the skill **on the machine running Hermes** (not on every target device):

```bash
hermes skills install https://raw.githubusercontent.com/luandro/edge-llm-autoinstall/main/SKILL.md
hermes skills list
```

Or from a Hermes chat:

```text
/skills install https://raw.githubusercontent.com/luandro/edge-llm-autoinstall/main/SKILL.md
```

Then ask Hermes:

```text
/edge-llm-autoinstall Inspect this machine and install the safest local model. Benchmark the Portuguese summary and EN-to-PT-BR translation quality, and report actual settings.
```

For a remote target, tell Hermes which host to access and give it **authorized SSH/sudo access**. The skill checks the hardware, runs the installer dry-run first, requests approval for changes, verifies the local API and measures real performance before recommending a stronger model. The agent does not need access to your passwords in the repository.

Read [SKILL.md](SKILL.md) for the complete procedure and safeguards. To fetch future improvements, use `hermes skills check` and `hermes skills update edge-llm-autoinstall`. Hermes installs skills through its safety scanner; read the contents before accepting installation.

**Current capabilities:** the installer runs a single local chat/summarization/LLM-translation model. Standalone **pt-BR STT and a dedicated EN→PT-BR translation service are not installed yet**; the skill clearly identifies them as follow-up implementation work.

## Models

| Hardware | Best (`--mode best`) | Safe (`--mode safe`) |
| --- | --- | --- |
| **Pi 5, 4 GB** | **Qwen3.5 2B Q4 (~1.28 GB), 2K context** | **Qwen3.5 0.8B Q4 (~0.53 GB), 4K context** |
| Pi 5, 8 GB | Qwen3 30B-A3B Q3_K_S, SSD-backed experimental | Qwen3.5 2B Q4 |
| Pi 5, 16 GB | Qwen3.6 35B-A3B CPU-3, very tight on RAM | Qwen3.5 4B Q4 |
| Intel N95/N97, 16 GB | Qwen3.6 35B-A3B CPU-2, slow on bandwidth-limited CPU | Qwen3.5 4B Q4 |
| **Ryzen 8945HS, 32 GB** | **Gemma 4 26B-A4B Q4, opt-in GTT capacity** | **Gemma 4 E4B Q4, no kernel tuning** |

The Pi 4 GB automatically selects safe mode; `--mode best` is opt-in. It uses CPU only, builds with 2 parallel jobs and caps context at 4K. See [Pi 5 4 GB notes](docs/PI5_4GB.md).

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

## Development and checks

```bash
bash -n install.sh
bash tests/smoke.sh
python3 scripts/benchmark.py --output benchmark.json  # on a machine with a running server
```

Installation is currently validated by shell syntax and hardware-selection dry runs only. Measure actual throughput, prompt latency and model quality on your target before selecting the best profile.
