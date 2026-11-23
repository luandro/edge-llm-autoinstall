# Deep research agent prompt — GMKtec K11 edge AI

You are an expert in local inference on AMD APUs, model quality benchmarking, offline speech processing, Linux GPU drivers and reproducible open-source deployment. Your deliverable is **actionable research and a draft patch plan** for `edge-llm-autoinstall`, not a generic model list.

## Required inputs

1. Read the repository's actual current `README.md`, `install.sh`, `tests/smoke.sh`, `scripts/benchmark.py`, `docs/K11.md`, and `docs/TASK_RESEARCH_NOTES.md`. The source may be a supplied ZIP; `https://github.com/luandro/edge-llm-autoinstall` may not be published yet. Do not assume a public repository exists without checking.
2. Read and independently verify the findings of the previous research report: `https://share.gemini.google/7Qfa2CQS836x`. If unavailable, report that fact and request a PDF/Markdown export; do not invent or silently incorporate supposed findings.
3. Search research literature, GitHub issues/PRs and code, Hugging Face model repositories, hardware forums, Reddit, and primary/first-hand user benchmarks. Prioritize results from **September–November 2026** but use relevant older baseline data. Link exact evidence and distinguish date of testing from date of publication.

## Target hardware — do not substitute a different machine

- GMKtec K11 with **AMD Ryzen 9 8945HS**, 8 cores / 16 threads, Radeon 780M integrated graphics (`gfx1103`), **32 GB DDR5-4800** RAM and **1 TB NVMe SSD**.
- Linux first (Ubuntu 24.04/26.04 and Manjaro/Arch as practical); local/offline inference, single user and one active task at a time. The 780M shares memory with the CPU: no separate 8–32 GB VRAM.
- Do not infer K11 speed from faster DDR5-5600, 64 GB or discrete-GPU tests without caveats. Record package power, kernel, Mesa/RADV/ROCm driver, BIOS UMA settings, effective GTT and disk speed.
- Prefer stable, maintainable upstream components, minimal manual steps, reproducible installs and local-only network APIs.

## The three tasks that must drive the decisions

**A. Speech-to-text in Brazilian Portuguese:** in-person/remote conversations, noisy interviews, Portuguese regional accents, code-switching, names and long audio. Evaluate dedicated STT implementations such as `whisper.cpp` multilingual base/small/medium, faster-whisper/CTranslate2, sherpa-onnx, Parakeet TDT 0.6B multilingual and `alefiury/parakeet-tdt-v3-ptBR-30s-onnx`, Qwen3-ASR 0.6B/1.7B and new credible contenders. Benchmark CPU-only and optional Vulkan acceleration if actually supported. Measure WER/CER on *pt-BR* audio, RTF, memory, timestamps, no-speech behavior, chunking and real-time feasibility. Do not mistake English/German WER for pt-BR evidence.

**B. English → Brazilian Portuguese translation:** compare OPUS-MT/Marian with CTranslate2 INT8, Argos Translate, NLLB-200 distilled, Hy-MT2 and other small optimized MT models against local generative models. Verify natural pt-BR (not generic `pt` or European Portuguese), preservation of meaning/format/names/terminology, throughput, peak RAM and long-text consistency. Consider glossary support.

**C. PT-BR/EN summarization:** recorded meetings, multi-hour transcripts, decision/action-item extraction, source timestamps and technical notes. Compare quality, unsupported claims, long-context prompt processing and latency. Explore chunk/map-reduce strategies and sequential unloading of STT/MT/LLM to avoid RAM contention.

Also benchmark agent/tool-call/coding usefulness as a **secondary task**, since the repo currently installs general LLMs.

## Models to evaluate seriously (discover new ones too)

- Inkling 2 Mini (ggml-org IQ4_NL and suitable mixed quants); check any special repeated-layer or expert placement considerations, chat template and tool-call correctness.
- Qwen3.8 27B dense (Q3/Q4); test whether higher quality compensates for severe bandwidth-limited decode.
- Qwen3.6 35B-A3B and Qwen3-Coder 30B-A3B (sparse MoE); verify quantization-specific quality and extended-context performance.
- Gemma 4 26B-A4B with Q4_0/Q4_K_M and optional compatible MTP draft head.
- Gemma 4 E4B and E2B, Q4_0, with and without compatible MTP; establish a reliable lightweight/safe path.
- LFM2.5 24B-A2B (Liquid AI QAD Q4_0, Q4_K_M, QAD Q2_K_L), with a focus on speed/quality tradeoffs. Do not equate timings from different quantizations.
- gpt-oss 20B MXFP4, Qwen3.5 9B and 4B, plus any superior November 2026 smaller MoE/CPU-friendly models.

For each model record **exact existing HF repo, file, revision, checksum, disk bytes, RAM, offloaded layers, KV cache, chat template, license, measured prefill/decode and task-quality score**. Reject or flag unverified or changed file identifiers.

## Engine and system investigation

- Compare latest **upstream llama.cpp with Vulkan/Mesa RADV** against CPU-only. Compare ROCm only where reproducible on 780M gfx1103 without unsafe driver overrides. Check current Vulkan/ROCm compatibility, unsupported kernels, model correctness and stability.
- Test `-ngl 99` against partial offload; 4/8/16/32K context; `-t 4/6/8/12`, `--threads-batch`; `-ub 128/256/512`; flash attention; `q8_0`, `f16` and lower-KV precision. Measure prompt ingestion and completion speed **separately**.
- Check DDR5-4800 bandwidth, memory pressure, UMA/GTT limits, temperature, power/performance governor and whether a particular BIOS/firmware setting helps. Never auto-change boot parameters, GTT, swap, thermal controls or BIOS. Specify rollback and remote-recovery risks for opt-in tuning.
- Investigate **MTP / draft decoding** only where the exact target-model draft file and llama.cpp version are verified. Report accept rate and net throughput on realistic prompts; drafting is not always a win.
- Explore server startup, sequential model loading, warm-cache behavior, systemd restarts, OOM recovery and safe local API exposure. Compare whether a lightweight local model router is worth its operational complexity.
- Check if a published K11 benchmark exists; otherwise identify closest 8945HS / 8845HS / 8745HS / 7840U analogues and state why they are only proxies.

## Starting sources (not predetermined winners)

- Reproducible Radeon 780M benchmarks: https://github.com/cyberpuffin-digital/amd-ryzen-inference-testing
- llama.cpp 780M discussion: https://github.com/ggml-org/llama.cpp/discussions/24222
- Vulkan vs ROCm report: https://github.com/ggml-org/llama.cpp/discussions/32165
- Radeon 780M community reports: https://llamaperf.com/gpu/radeon-780m
- 32 GB GMKtec K8 Plus Qwen3.8 report: https://shino.dev/posts/tower-defense-harness-27b/
- Official Liquid AI QAD GGUF files: https://huggingface.co/LiquidAI/LFM2.5-24B-A2B-GGUF
- Gemma E4B GGUF & draft heads: https://huggingface.co/ggml-org/gemma-4-E4B-it-GGUF
- Pi 5 ASR CPU comparisons (quality limited to the displayed languages): https://ai-tier.com/stt
- Brazilian Portuguese Parakeet ONNX: https://huggingface.co/alefiury/parakeet-tdt-v3-ptBR-30s-onnx
- Pi 5 ASR + MT project: https://github.com/koh43/pi-translator
- whisper.cpp: https://github.com/ggml-org/whisper.cpp
- sherpa-onnx: https://github.com/k2-fsa/sherpa-onnx
- CTranslate2: https://github.com/OpenNMT/CTranslate2

## Benchmark plan — run on the actual K11 if available

Establish a **baseline before changing Linux configuration**. Include installed kernel, Mesa/ROCm, CPU and memory clocks, effective RAM capacity, power setting, `vulkaninfo --summary`, `free -h`, model SHA, llama.cpp commit, exact launch command, OS/process RSS and thermal conditions. Save reproducible logs, not just screenshots.

- Text: identical PT-BR summarization, EN→PT-BR translation, coding/tool call and 512/4096/12000-token long-context prompts; 128–512 output tokens, 3 cold/warm trials. Record time-to-first-token, prompt tok/s, decode tok/s, peak RAM, accuracy scores and errors.
- Audio: >=30s clean, 5-min conversational and >=20-min noisy pt-BR excerpts; WER/CER against consented human references, real-time factor, peak RAM and timestamps. Test diarization as separate optional cost.
- Translation: >=50 segments including names, numbers, regionalisms and technical terms; human evaluation plus chrF/COMET as supplementary measures. Blind-compare output without knowing model labels.
- End-to-end: 30-min audio → transcript → EN/PT translation if needed → structured PT-BR summary; report total wall time, RAM peaks, model switch cost and quality. Keep inference fully offline after downloads.
- Measure under sustained use: 30-minute load, thermal throttling, OOM behavior, service restart and one-click recovery.

## Deliverables

1. **Evidence matrix** (source URL, hardware precision, date, runtime/quantization/flags, speed, quality, RAM, reliability, confidence level).
2. **Ranked K11 model profiles:** fastest responsive, best quality/capability, best PT-BR summarizer, best English→PT-BR translator, safe/small, and strongest coding/tool-use candidate. Distinguish models already installed by our script from new recommendations.
3. **Task architecture:** when to use specialized ASR/MT versus an LLM; memory-aware sequencing and local API contracts, preserving `/v1` compatibility and privacy.
4. **Safety/installation audit** of the existing `install.sh`; verify precise HF filenames, download paths, CMake flags, Vulkan discovery, context/headroom, service and rollback semantics.
5. **Small ordered implementation phases**, with focused changes and automated tests. Keep the single `bash install.sh` interface; do not introduce multiple management frameworks without compelling evidence.
6. **Reproducible commands and benchmark artifacts** (machine-readable JSON/CSV), an optional benchmark script/PR patch and exact changed files. Do not change the existing defaults without quality and reliability evidence.
7. A **brief final recommendation** with two best and one safe option, the major unknowns and the one experiment that would reduce uncertainty most.

If GitHub write access exists, prepare a **draft PR**. If not, provide an organized patch/ZIP with a precise changelog. Never claim an unrun script or untested model is validated. Explicitly mark any Gemini report content that could not be accessed.
