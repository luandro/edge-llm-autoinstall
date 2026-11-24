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

## Benchmark all candidate models with one command

```bash
bash benchmark.sh --dry-run --models small
bash benchmark.sh --models small --suite quick --runs 1
bash benchmark.sh --models edge --suite full --runs 3
```

- **small:** Qwen3.5 0.8B, BotPsy 0.8B, mini-agent-v2 1.5B and Qwen3.5 2B (all Q4).
- **edge:** those four plus Qwen3.5 4B and Gemma 4 E4B.
- **adapter:** LFM3 1.7B Q8 unchanged base versus GGUF Hermes LoRA; review LFM license.
- **large / all:** K11 and Pi experimental large models, requiring `--allow-large` and adequate RAM, storage and explicitly raised download budget.
- Specify exact candidates: `--models qwen08,botpsy,mini_agent`.

To test the existing installed model without changing it:

```bash
bash benchmark.sh --server-url http://127.0.0.1:8080 --suite full --runs 3
```

The runner launches each GGUF sequentially on a localhost-only llama.cpp server. It tests **native tool calls (without executing proposed commands)**, no-tool decisions, synthetic EN→PT-BR translation and PT-BR summaries; saves full JSON, CSV and Markdown reports. It records actual model load time, generation/prompt speed when supported and memory usage. The automated translation/summary scores measure **lexical terms and fact coverage**, not semantic accuracy or hallucinations; review outputs manually.

**[Open benchmark on Google Colab](https://colab.research.google.com/github/luandro/edge-llm-autoinstall/blob/main/notebooks/benchmark_colab.ipynb)** · [Benchmark guide and platform comparisons](docs/BENCHMARKING.md)

In Colab, select a GPU runtime if available and run the notebook cells. Free GPU access is not guaranteed and can be interrupted; start with `small`. Kaggle Notebooks offers another free option. A ChatGPT Pro subscription does **not** itself provide Colab compute. **Cloud GPU results are not hardware benchmarks for the Pi 5, Intel N95/N97 or Radeon 780M K11**; repeat the same test locally for performance claims.

## Models

| Hardware | Best (`--mode best`) | Safe (`--mode safe`) | Optional **tool-use** model (`--agent-model`) |
| --- | --- | --- | --- |
| **Pi 5, 4 GB** | **Qwen3.5 2B Q4 (~1.28 GB), 2K context** | **Qwen3.5 0.8B Q4 (~0.53 GB), 4K context** | BotPsy 0.8B Q4 for routing; mini-agent 1.5B Q4 for shell (experimental) |
| Pi 5, 8 GB | Qwen3 30B-A3B Q3_K_S, SSD-backed experimental | Qwen3.5 2B Q4 | BotPsy 0.8B Q8; mini-agent 1.5B Q5 (experimental) |
| Pi 5, 16 GB | Qwen3.6 35B-A3B CPU-3, very tight on RAM | Qwen3.5 4B Q4 | mini-agent 1.5B Q5; BotPsy 0.8B Q8 (experimental) |
| Intel N95/N97, 16 GB | Qwen3.6 35B-A3B CPU-2, slow on bandwidth-limited CPU | Qwen3.5 4B Q4 | mini-agent 1.5B Q5; BotPsy 0.8B Q8 (experimental) |
| **Ryzen 8945HS, 32 GB** | **Gemma 4 26B-A4B Q4, opt-in GTT capacity** | **Gemma 4 E4B Q4, no kernel tuning** | mini-agent 1.5B Q5; BotPsy 0.8B Q8 (experimental) |

### Optional post-trained models for Hermes and local tools

These are **experimentally selectable**, not new safe/best defaults. They optimize a narrow set of tool tasks and should **not replace** the general models for pt-BR summarization, EN→PT-BR translation or offline STT. See [model research, measured benchmarks, limitations, and validation plan](docs/AGENT_MODELS.md).

| Model | Select | Best fit | Evidence and status |
| --- | --- | --- | --- |
| [BotPsy 0.8B](https://huggingface.co/qvac/BotPsy-0.8B-GGUFs), Q4 on Pi 4 GB / Q8 elsewhere | `--agent-model botpsy` | Simple, English-first tool routing and choosing not to call tools | **Publisher's GGUF tests**: BFCL v4 43.5% Q4 / 44.2% Q8. Not Hermes or Pi/N95/K11-tested. Enables its evaluated thinking template. |
| [mini-agent-v2 1.5B](https://huggingface.co/F-A-I-L/mini-agent-v2), Q4 on Pi 4 GB / Q5 elsewhere | `--agent-model mini-agent` | Bash, Python, tool invocation; guided short tasks | **Author's bf16 tests**: BFCL 86.2% non-live, 65.7% live, Bash 50.3%, Python 66.2%. GGUF quants *not* re-benchmarked; no long autonomous loops. |
| [LFM3 1.7B Hermes LoRA](https://huggingface.co/harness-hub/LFM3-1.7B-hermes) | **Research only; not automated** | Hermes data-analysis tasks; compare adapter to unchanged base | 78% vs 62% on 150 data tasks; worse on 40 harder repository tasks; author used **64K+ context** and did **not** evaluate GGUF. [Manual test instructions](docs/AGENT_MODELS.md). |

```bash
bash install.sh --agent-model botpsy --dry-run
bash install.sh --agent-model botpsy
bash install.sh --agent-model mini-agent
bash install.sh --mode safe             # restore general-purpose profile
```

**What installation does:** changes the **one** active local `edge-llm` service at `127.0.0.1:8080/v1`; it does **not** run simultaneous specialist/general models or set up automatic routing. These specialists use English-oriented training and require real PT-BR/Hermes evaluations before any default promotion. The published scores come from **different benchmark suites** and are not directly comparable with each other or with the safe-model task success.

### Expected LLM performance by hardware

*Updated 2026-11-24.* These numbers are for **output generation** (new tokens per second, **tok/s**) on one local request, **not** prompt processing, full agent-task duration, transcription or translation speed. They are planning ranges, not minimum-performance guarantees. They depend on quantization, CPU/memory bandwidth, cooling, context, runtime and GPU offload. A long prompt can take considerably longer to read than the generated answer takes to write.

**Evidence:** **M** = published measurement on the named hardware/model (range around the result); **P** = measurement on closely related hardware or the same Pi 5 CPU with a different RAM size, used as a proxy; **E** = rough estimate without a comparable direct test; **X** = special experimental configuration, not a result reproduced with this installer. **Safe/best** are options supported by the current script; **optional** means *not selectable with the current installer* unless explicitly described as a K11 `--model` choice.

| Machine | Model / configuration | Availability | Expected output | Evidence | Most realistic uses |
| --- | --- | --- | ---: | --- | --- |
| **Pi 5, 4 GB** | BotPsy 0.8B Q4 (agent) | Optional / experimental | **Unmeasured locally** | Publisher GGUF tool benchmarks | Restricted tool routing; not PT-BR summarization |
| **Pi 5, 4 GB** | mini-agent-v2 1.5B Q4 (agent) | Optional / experimental | **Unmeasured locally** | Author bf16 task benchmarks | Shell/Python in isolated tests |
| **Pi 5, 4 GB** | Qwen3.5 0.8B Q4 | **Safe / auto** | **12–16 tok/s** | P (Pi 5 16 GB: 15.1) | Quick classification, simple routing, very short drafts; weak for autonomous coding |
| Pi 5, 4 GB | Qwen3.5 2B Q4, 2K context | **Best** | **6–8 tok/s** | P (Pi 5 8/16 GB: 7.1–7.7) | Better short summaries, basic EN→PT-BR drafts, tiny code changes; watch RAM |
| **Pi 5, 8 GB** | Qwen3.5 2B Q4 | **Safe** | **7–8 tok/s** | M (8 GB Pi 5: 7.1–7.8) | Lightweight agent/tool calls, short PT-BR summaries and writing |
| Pi 5, 8 GB | Qwen3.5 4B Q4 | Optional, not in installer | **3–5 tok/s** | P (16 GB Pi 5: 3.4) | Better instruction-following and text quality, but less memory headroom |
| Pi 5, 8 GB | Qwen3 30B-A3B Q3 + fast SSD | **Best / experimental** | **6–9 tok/s** | X (Potato OS: 8–9) | Higher-capability chat/writing; long prompts and SSD paging are the bottleneck |
| **Pi 5, 16 GB** | Qwen3.5 4B Q4 | **Safe** | **3–5 tok/s** | M (16 GB Pi 5: 3.4) | Short PT-BR writing, translation via chat, grounded summaries |
| Pi 5, 16 GB | Gemma 4 E2B Q4 | Optional, not in installer | **6–8 tok/s** | M (16 GB Pi 5: 7.4) | Faster general writing and multilingual responses |
| Pi 5, 16 GB | Qwen3-Coder 30B-A3B CPU-6 | Optional, not in installer | **7–9 tok/s** | M (publisher: 7.91) | Coding experiments; assess long-prompt latency and tool-call accuracy |
| Pi 5, 16 GB | Qwen3.6 35B-A3B CPU-3 | **Best / memory-tight** | **4–6 tok/s** | M (publisher: 5.05) | Deeper reasoning and complex writing only if it loads without swapping |
| **Intel N95/N97, 16 GB** | Qwen3.5 2B Q4 | Optional, not in installer | **6–10 tok/s** | P (N100: 8.3) | Faster small agent tasks and short summaries |
| Intel N95/N97, 16 GB | Qwen3.5 4B Q4 | **Safe** | **2–5 tok/s** | P (N100: 3.2) | Better PT-BR writing and summaries; modest coding assistance |
| Intel N95/N97, 16 GB | Qwen3.6 35B-A3B CPU-2 | **Best / experimental** | **~2–6 tok/s?** | E (no exact N95/N97 test) | Maximum model capability, but long-context agent work may be impractically slow |
| **K11 / Ryzen 8945HS, 32 GB** | Gemma 4 E4B Q4 (Vulkan) | **Safe / auto** | **18–28 tok/s** | P (other Radeon 780M: ~19–24 without MTP) | Daily chat, writing, short translation and summaries |
| K11 / 8945HS | gpt-oss 20B MXFP4 (Vulkan) | **`--model gptoss20b`** | **20–33 tok/s** | P (other 780M: 28.9) | Tool calls, orchestration and assistant workflows; benchmark correctness |
| K11 / 8945HS | Gemma 4 26B-A4B Q4 (Vulkan) | **Best; GTT-dependent** | **18–26 tok/s** | P (other 780M: ~23–25 without MTP) | Strong multilingual writing, summaries and EN→PT-BR drafts |
| K11 / 8945HS | Qwen3.6 35B-A3B Q4 (Vulkan) | **`--model qwen36`; GTT-dependent** | **16–28 tok/s** | P (other 780M, differing quants: ~18–33) | Most promising complex coding, reasoning and multi-step agents |
| K11 / 8945HS | Inkling 2 Mini IQ4_NL (Vulkan) | **`--model inkling`; experimental** | **12–18 tok/s** | P (other 780M: ~17, quant unspecified) | English-focused coding; **not** the first choice for PT-BR/factual summaries |
| K11 / 8945HS | Qwen3.8 27B dense Q4 (Vulkan) | **`--model qwen38`; slow** | **3–8 tok/s** | P (other 780M: ~3–8) | Quality comparisons / offline batch work; poor interactive throughput |
| K11 / 8945HS | LFM2.5 24B-A2B Q4 | Research candidate, **not in installer** | **~30–40 tok/s** | P (other 780M reports: ~37–40) | Fast low/mid-complexity task execution; still needs quality/runtime checks |

For the two new agent-model rows, **no generation-speed estimates are supplied**: benchmark output speed, prompt processing, memory and *task completion* on the physical Pi/N95/K11 first. On larger machines the installer uses BotPsy Q8 or mini-agent Q5, but these are still not independently measured there. See [agent evidence](docs/AGENT_MODELS.md).

**Important qualifications:** the Pi 5 **4 GB** rows extrapolate from the same Pi 5 CPU on 8/16 GB boards, not measurements on a 4 GB system. N95/N97 estimates use **N100**, which is related but not identical (RAM type, memory channel and thermal limit matter). All K11 rates come from **other Radeon 780M computers**, often with faster memory or larger GTT. Full offload of a 26–35B MoE on a stock K11 may fail; partial CPU offload can reduce these speeds greatly. The Pi 8 GB 30B result comes from **Potato OS + optimized ik_llama + SSD**, not an end-to-end benchmark of this repo. The K11 numbers are **without MTP speculative decoding** unless stated otherwise; MTP can increase generation speed but is **not enabled** by this installer.

Sources: [Pi 5 measured text models](https://ai-tier.com/devices/raspberry-pi-5/), [Pi 5 8 GB agent benchmark](https://github.com/Jiaming-Liuu/Pi5-LLM), [Potato OS Pi 5 SSD benchmark](https://github.com/potato-os/core), [ByteShape Pi 5 Qwen3.6](https://byteshape.com/blogs/Qwen3.6-35B-A3B/), [ByteShape Pi 5 Qwen3-Coder](https://byteshape.com/blogs/Devstral-Small-2-24B-Instruct-2512/), [N100 16 GB measurements (RigBench)](https://rigbench.hleli.com/), [780M Vulkan measurements](https://github.com/cyberpuffin-digital/amd-ryzen-inference-testing), [780M single-script benchmark](https://github.com/tomasastary/llama-amd-alpine), [780M community reports](https://llamaperf.com/gpu/radeon-780m).

### Which machine and model for which task?

These are **practical recommendations**, not directly measured task-accuracy rankings. The appropriate model depends on whether you prioritize speed, output quality, tool-call reliability or offline memory headroom.

| Task | Pi 5 4 GB | Pi 5 8 GB | Pi 5 16 GB | Intel N95/N97 16 GB | K11 32 GB |
| --- | --- | --- | --- | --- | --- |
| **Simple routing / classification** | 0.8B; verify outputs | 2B | 4B or 2B (optional) | 4B; 2B would be faster | E4B; gpt-oss for tools |
| **Agent orchestration / tool calling** | **BotPsy** optional for routing; no unsupervised loops | **mini-agent** optional for short shell/Python; BotPsy routing | **mini-agent** optional; 4B general model for reasoning | **mini-agent** optional; 4B general model for reasoning | **gpt-oss 20B / Qwen3.6** for complex plans; mini-agent for tiny delegated jobs |
| **Coding / software agents** | Tiny edits only with 2B | Small code tasks; 30B SSD experiment | **Qwen3-Coder 30B** (optional); 35B best | 4B for small edits; bigger MoE too slow for most loops | **Qwen3.6 35B**; **Inkling 2 Mini** for English coding |
| **Writing in Portuguese** | 2B: short/simple | 2B: short drafts; 30B experimental | 4B for routine, 35B for demanding texts | 4B for routine | **Gemma 4 26B-A4B**; E4B for quick drafting |
| **Summarizing meetings/interviews** | 2B, short chunks, strict fact checks | 2B; chunk long transcripts | 4B routinely; 35B for quality tests | 4B with chunking | **Gemma 4 26B-A4B**; E4B for fast summaries |
| **English → Brazilian Portuguese** | Dedicated OPUS-MT planned; 2B chat for short text | Dedicated OPUS-MT planned; 2B chat | Dedicated OPUS-MT planned; 4B chat for style | Dedicated OPUS-MT planned; 4B chat | Dedicated OPUS-MT planned for throughput; **Gemma 4 26B** for nuanced language |
| **Portuguese speech → text** | Whisper tiny/base or Parakeet, **one model at a time** | Parakeet/Whisper + VAD, planned | Parakeet/Whisper + VAD, planned | Parakeet/Whisper + VAD, planned | Parakeet/Whisper + VAD, planned |
| **Audio → transcript → translated summary** | Sequential stages only, **not implemented** | Sequential stages, **not implemented** | Sequential stages, **not implemented** | Sequential stages, **not implemented** | Sequential/on-demand large models, **not implemented** |
| **Text-to-speech (PT-BR)** | Piper ONNX voice candidate; not installed | Piper candidate; not installed | Piper candidate; not installed | Piper candidate; not installed | Piper candidate or richer TTS model; not installed |
| **Embeddings / local RAG** | Tiny embedding model candidate; not installed | Small embedding model candidate; not installed | Small embedding model candidate; not installed | Small embedding model candidate; not installed | Embedding model with separate retrieval/index; not installed |

For speech synthesis, [Piper](https://github.com/rhasspy/piper) offers offline **pt_BR** voices and is designed for Raspberry Pi-class CPUs; voice-specific memory, quality and real-time factor need measurement. Embeddings/RAG require a separate embedding model and indexing/retrieval process; the script does not provide them. Neither uses ordinary LLM generation tok/s as a useful performance measure.

**Reality check for agents:** tok/s is only *generation* speed. Tool-calling accuracy, valid JSON, context quality, prompt-prefill delay and total time per completed task matter more than a high headline figure. Tiny models are better used as classifiers/routers for tightly controlled actions than as unattended multi-step coding agents. A Pi or N95 should not be treated as equivalent to a workstation just because a 30B GGUF can load.

### Speech-to-text and translation: different performance units

**STT is measured using real-time factor (RTF)**: processing seconds / audio seconds. **Lower is better**; RTF 0.10 means about 10× faster than audio playback. These measurements are on a **Pi 5 with 16 GB**, using particular model/runtime builds—not validated pt-BR accuracy, and not measured on N95/N97 or K11.

| Speech model (CPU) | Pi 5 measured RTF | Peak memory | Realistic fit | Notes |
| --- | ---: | ---: | --- | --- |
| **Whisper Tiny multilingual** | **0.191** (~5.2× realtime) | ~0.94 GB | Pi 5 4 GB+, N95/N97, K11 | Lightweight fallback; lower accuracy |
| **Whisper Base multilingual** | **0.365** (~2.7× realtime) | ~1.48 GB | Pi 5 4 GB+, N95/N97, K11 | Better quality tradeoff; verify pt-BR |
| **Parakeet TDT 0.6B v3 multilingual** | **0.112** (~8.9× realtime) | ~2.22 GB | Pi 5 8/16 GB, N95/N97, K11; *tight on Pi 4 GB* | Excellent general CPU candidate, but test pt-BR and model swapping |
| **Whisper Small multilingual** | **1.255** (~0.8× realtime) | ~3.68 GB | Pi 5 8/16 GB, N95/N97, K11 | Too large for comfortable concurrent Pi 4 GB use |

The [Pi 5 STT benchmark](https://ai-tier.com/stt) reports **English/German WER**, not Brazilian Portuguese WER. For pt-BR, additionally evaluate [Parakeet pt-BR ONNX fine-tunes](https://huggingface.co/alefiury/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx) against Whisper with real recordings; **TAGARELA-derived weights may inherit non-commercial dataset restrictions** and should not be installed for unrestricted commercial use without license review. [Pi translator](https://github.com/koh43/pi-translator) demonstrates that Pi 5 4 GB needs **sequential loading/unloading** for STT + translation.

For dedicated **EN→PT-BR translation**, the leading small CPU candidate is [OPUS-MT en→pt in CTranslate2 INT8](https://huggingface.co/gow-solucoes/opus-mt-en-pt-ct2), which supports the **`>>pob<<` Brazilian Portuguese** target-language tag. **No verified per-device throughput** was found for the Pi 5, N95/N97 or K11, so the README deliberately does not invent translation tok/s. Benchmark actual sentence latency, character/word throughput, chrF/COMET and preservation of names, dates and technical terms. LLM translation tok/s above is **not comparable** with encoder–decoder translation tokens/s.

**Implementation status:** the current one-script installer still installs **one local text LLM**, not specialized STT, TTS, dedicated NMT, embedding, multi-model orchestration or audio pipelines. The table lists **workload candidates and future integrations**, not currently working endpoints. In particular, `/v1/audio/transcriptions`, `/v1/translate`, and an audio pipeline are **not available** yet.

### Measure your own machine

```bash
bash install.sh --mode safe --dry-run    # detected plan, no changes
# After installing, on the target:
python3 scripts/benchmark.py --output benchmark.json       # existing single-model test
bash benchmark.sh --models small --suite full --runs 3   # multi-model comparison
curl http://127.0.0.1:8080/v1/models
```

Record exact model file/quantization, backend, number of threads, RAM channels, GPU GTT, context and input length. Compare at least **three warm runs** and measure both prompt processing and generated tok/s before changing the automatic profile. The supplied script tests text tasks; **STT and dedicated translation require separate benchmarks**.

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
