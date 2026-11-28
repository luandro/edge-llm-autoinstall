# Raspberry Pi 5 — 4 GB (CPU-only)

The installer detects Raspberry Pi 5 with approximately 4 GB of RAM and installs one local LLM at `127.0.0.1:8080/v1`. Use **Raspberry Pi OS 64-bit**, an active cooler, and preferably a minimal/headless system.

| Mode | Model | Weight download | Default context |
| --- | --- | --- | --- |
| `auto` / `safe` | [Qwen3.5 0.8B Q4_K_M](https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF) | ~533 MB | 4096 tokens |
| `best` | [Qwen3.5 2B Q4_K_M](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF) | ~1.28 GB | 2048 tokens |

```bash
bash install.sh --dry-run
bash install.sh                 # safe by default on 4 GB
bash install.sh --mode best     # opt-in; more capable, less headroom
curl http://127.0.0.1:8080/v1/models
```

Both profiles are CPU-only, one request at a time. The build uses two parallel compiler jobs to avoid memory pressure. The installer caps context overrides at 4096 tokens on Pi 4 GB.

**Performance:** an 8 GB Pi 5 community measurement for Qwen3.5 2B Q4 reported ~7.1 tokens/sec and ~2.75 GB peak RAM. That is **not** a verified measurement on the 4 GB device. Watch memory pressure, thermal throttling and service logs; if the best model fails, rerun `bash install.sh --mode safe`.

```bash
free -h
vcgencmd get_throttled
journalctl -u edge-llm -n 100 --no-pager
python3 scripts/benchmark.py --output pi4-benchmark.json
```

## Planned offline audio and translation work

This repository **does not yet install STT or a dedicated NMT translation server**. For a later task-specific implementation:

- pt-BR STT: Parakeet TDT v3 multilingual ONNX INT8 + Silero VAD, or whisper.cpp small/tiny for a simpler fallback. Verify pt-BR accuracy on actual audio.
- EN→PT-BR: CTranslate2 INT8 + an OPUS-MT model; measure regional Portuguese quality. A future LLM alternative may use a small translation GGUF with sequential loading.
- Summaries: the installed Qwen3.5 model can summarize **short** texts using chat. For long interviews, chunk input and preserve names, timestamps and numbers.

**On 4 GB, never assume the STT, NMT and LLM engines can all stay loaded at once**. Unload between stages, preserve timestamped intermediate output and avoid relying on heavy microSD swap.

References: [Pi5-LLM](https://github.com/Jiaming-Liuu/Pi5-LLM), [4 GB Pi translator](https://github.com/koh43/pi-translator), [hardware and software options](TASK_RESEARCH_NOTES.md).

## New candidate: LFM3 and lessons from Potato OS (2026-11-27)

See [deployment readiness and evidence ledger](LOCAL_HERMES_TRANSFER.md). A [third-party Pi 5 2 GB test](https://peppe8o.com/install-llama-cpp-raspberry-pi/) reported about 9 generation tok/s and ~1.7–1.76 GiB peak for **base LFM3 Q4**, not the Hermes adapter or full agent. Test the Q4 base/LoRA pair via the explicit benchmark names, initially at 2048 context. Safe/best defaults and 4096 installer cap remain unchanged. Potato OS officially supports Pi 5 8/16 GB, not 4 GB. Borrow its diagnostics and ARM runtime testing, not its OS image or large MoE defaults. Start with rules/TF-IDF routing, no resident Laya by default, and measure sequential STT/NMT/LLM scheduling when implemented. Never misreport the physical context to Hermes; full agent support requires separate validation.

## 2026-11-28 LFM3 agent experiment

Use `bash install.sh --agent-model lfm3-hermes --dry-run` for the preferred 1.7B Hermes-specific experiment (4K context, one CPU slot), then approve the install; updated v2 USB supports the same command with `--offline`. This is not stock Hermes-compatible at 4K. Use direct API/validated lean harness only; retain Qwen3.5 0.8B safe for rollback. See [LFM3 profiles and evidence](LFM3_EDGE_AGENT.md).
