# Deep research brief: CPU-only speech, translation, and summarization on tiny Linux computers

You are an independent edge-AI researcher and systems engineer. Investigate real user deployments, open-source projects, reproducible benchmarks, model cards, and technical discussions. Your goal is to recommend **evidence-backed improvements** to the existing `edge-llm-autoinstall` repository, not to produce a generic model roundup.

## Repository and hardware

- Repository: `https://github.com/luandro/edge-llm-autoinstall` (if it is not online yet, use the supplied repository ZIP).
- Read the actual `install.sh`, `README.md`, and tests before proposing changes. Preserve the single-command installer, hardware autodetection, local API, and `--mode safe|best|auto` behavior unless you explain and test a better interface.
- Target 1: Raspberry Pi 5, 8 GB RAM, ARM64, CPU only, active cooling, microSD or optional USB 3/NVMe SSD.
- Target 2: Raspberry Pi 5, 16 GB RAM, ARM64, same constraints.
- Target 3: Intel N95 and N97 (Alder Lake-N), 16 GB RAM, x86-64 Linux, SSD, **CPU only**. Evaluate N95 and N97 separately when data permits; N100/N150 results are only proxies and must be labeled as such.
- No dedicated GPU, eGPU, Coral, Hailo, external inference API, cloud inference, or NPU dependency. Downloads during installation are fine; **inference must work fully offline**.
- Prefer an ordinary Linux installation (Raspberry Pi OS 64-bit/Debian/Ubuntu), with the fewest services and dependencies practical. The user should not need to flash a specialty OS unless there is a compelling, independently verified advantage.

## The three priority workloads

1. **Brazilian Portuguese speech-to-text (pt-BR).** Audio notes, interviews, meetings, spontaneous/conversational speech, regional accents, quiet and noisy recordings, long audio, proper nouns, numbers and punctuation. Prioritize accurate pt-BR recognition, not English-only WER. Consider file transcription first; streaming/near-real-time transcription is a bonus.
2. **English → Brazilian Portuguese translation.** Short sentences, paragraphs, longer transcripts, technical terms and named entities. Preserve meaning and formatting, avoid European Portuguese phrasing where possible, and do not invent or omit important information. Evaluate dedicated machine-translation models against LLM translation.
3. **Portuguese summarization.** Summaries of pt-BR recordings/transcripts and English source material; concise summaries, main points, decisions, action items and timestamps when available. Prefer factuality and reasonable end-to-end latency over sheer model parameter count. Design a robust long-transcript chunking/merge strategy that works in limited RAM.

Also test the **combined offline pipeline**: pt-BR audio → pt-BR transcript → pt-BR summary, and English audio/text → English transcript (if audio) → pt-BR translation → pt-BR summary. Avoid keeping all models resident if doing so creates OOM or swapping. Consider on-demand loading, model swapping, and structured intermediate files.

## Research process: actual deployments first

Search GitHub projects, issues, pull requests, release notes, Hugging Face model cards/discussions, Raspberry Pi forums, Reddit, homelab blogs, papers, benchmark repositories and practical user stories through the most recent available date. Inspect implementation details rather than trusting README headline speeds. Look for measured workloads on actual Pi 5 8/16 GB and N95/N97 16 GB hardware. When using N100/N150, Core i5 or cloud Xeon results, explicitly describe why they may not transfer.

For every promising result, capture: link, publication/update date, exact CPU/board, RAM, architecture, OS, model and quantization, runtime and version/commit, threads, batch/context, disk type, input length, accuracy/quality measure, latency, real-time factor or tok/s, peak resident RAM, CPU and temperature/power where available, and whether the code and procedure are reproducible. Distinguish **measured**, **author-reported**, **extrapolated**, and **untested** results. Reject or qualify impossible memory claims, English-only results presented as pt-BR, and speeds that require undocumented custom patches.

Review **at least three credible independent real-world projects or benchmark reports per workload**, and seek examples for both hardware families. Look at maintenance status, open issues, model licenses, architecture compatibility, and long-running stability. Cross-check surprising performance claims with a second source where possible. Do not call an option “the absolute best” unless comparative evidence supports it.

## Specific candidates to investigate (not predetermined winners)

**STT:** `whisper.cpp` multilingual tiny/base/small and quantized builds; `faster-whisper`/CTranslate2 INT8; `sherpa-onnx`; ONNX Parakeet TDT 0.6B v3 multilingual; pt-BR fine-tunes such as `alefiury/parakeet-tdt-v3-ptBR-30s-onnx` and Tagarela; Qwen3-ASR 0.6B/1.7B if ARM64/CPU use is practical; Vosk Portuguese models; `onnx-asr`; and newer small speech models **only if Portuguese support is verified**. Check language-specific accuracy and real-time factor, not just demo responsiveness. Account for VAD, audio resampling, chunking, silence/hallucination handling, timestamps, code-switching and optional diarization.

**Translation:** Marian/OPUS-MT en→pt (verify the precise available model), CTranslate2 INT8, `translateLocally`/Bergamot, Argos Translate, NLLB-200 distilled 600M, Rust Candle implementations, and small specialized translation LLMs such as Hy-MT2 if they outperform compact NMT models in pt-BR with acceptable latency. Measure PT-BR quality, terminology retention, paragraph/chunk handling, batch throughput, RAM, cold start and model disk footprint. Verify licenses and offline redistributability.

**Summarization:** Qwen3.5 2B and 4B, Gemma 4 E2B via LiteRT-LM or llama.cpp, MiniCPM 2B-family alternatives, and other small quantized or summarization-specialized models that run comfortably on these CPUs. Revisit the repository's 30B/35B MoE choices: they may be interesting for occasional high-quality tasks but may be a poor default for combined STT/translation/summarization under 8/16 GB. Assess prompt throughput, Portuguese output quality, hallucinations, long-text chunking, factual consistency and context-memory cost. Test extractive or deterministic fallbacks where useful.

Start with these real projects/references, then discover newer or stronger alternatives:

- Pi 5 STT results: https://ai-tier.com/stt
- pt-BR Parakeet ONNX fine-tune: https://huggingface.co/alefiury/parakeet-tdt-v3-ptBR-30s-onnx
- Pi 5 offline translation project: https://github.com/TobyM-engineering/Real-Time-Speech-Translator-V2
- Pi 5 Parakeet + Hy-MT2: https://github.com/koh43/pi-translator
- Offline Marian/Candle pt-BR implementation: https://github.com/Anon5T4R/LocalTranslate
- CPU CTranslate2 translator: https://github.com/rozdaybeda/ct2_translator
- Pi 5 sherpa-onnx deployment: https://github.com/Seeed-Solution/openvoicestream
- Whisper runtime: https://github.com/ggml-org/whisper.cpp
- Faster Whisper: https://github.com/SYSTRAN/faster-whisper
- sherpa-onnx: https://github.com/k2-fsa/sherpa-onnx
- Pi 5 Gemma LiteRT-LM performance: https://www.raspberrypi.com/news/mastering-edge-ai-on-raspberry-pi-with-litert-and-gemma/
- Existing inference engine: https://github.com/ggml-org/llama.cpp

## Benchmarks and selection criteria

Design a **reproducible, hardware-specific** benchmark suite before final ranking:

- STT: at least 30-second, 5-minute and 20–30-minute recordings; clean/noisy pt-BR, conversational speech and named entities. Measure WER/CER, failure modes, processing time vs audio duration (RTF), peak RSS, cold start and quality of timestamps. Use consented, openly licensed or synthetic evaluation clips only, keeping private field recordings local.
- EN→PT-BR translation: at least 30 diverse segments and one longer document. Evaluate fidelity, fluency, terminology, PT-BR naturalness, names/numbers and format preservation using human review plus chrF/COMET when feasible. Report sentences/second and peak RAM.
- Summarization: short notes, 5k+ token transcripts and longer chunked transcripts; measure key-point coverage, actionable items, unsupported claims, processing time, peak RAM and degree of user editing required. If using an LLM judge, disclose the judge and independently spot-check examples.
- End-to-end: 5-minute and 30-minute samples, time from file import to useful summary, disk reads, RAM peak across the *whole pipeline*, simultaneous-request behavior, thermals/throttling and recovery after interruption.

Rank separately for **Pi 5 8 GB, Pi 5 16 GB, N95 16 GB and N97 16 GB**. For each task and hardware profile choose (a) **best practical quality/capability** and (b) **safe/lightweight default**. Exclude candidates that only fit on paper but require destructive swapping, run far slower than real time for ordinary usage, or leave insufficient RAM for the full pipeline; document them as experimental instead. Compare CPU-only performance, memory pressure, quality, installation complexity, maintenance, license and privacy. Do not fabricate missing numbers.

## Improvements to propose for the repository

Keep the **one-command experience** and small dependency surface. Design the simplest coherent extension of `install.sh` for task selection (for example `--task stt|translate|summarize|all`) and model tier (`--mode safe|best|auto`), while preserving existing options or providing a documented migration path. Automatic hardware detection should choose defaults based on real available RAM, SSD, thermal and disk constraints, not merely the device name. Show one clear confirmation summarizing downloads, approximate space, services and expected performance.

Provide stable, local-only APIs for transcription, text translation, summarization and the complete pipeline, while keeping `/v1` LLM compatibility. **Do not misuse** OpenAI's `/v1/audio/translations` semantics (which translate audio to English) for English→Portuguese. Propose appropriate endpoint names and JSON schemas, input size limits, privacy safeguards and simple `curl` examples. Use systemd or an equally lightweight supervisor, resumable and integrity-checked downloads, sensible model caching, memory-aware model switching, startup/health checks, progress logs, idempotent reinstall, rollback/uninstall, and no remote telemetry. Never expose unauthenticated services to the public network by default.

Audit existing scripts for broken download paths, unverified model names, incompatible build flags, Pi ARM64 wheels, dependency pinning, RAM and disk thresholds, thread counts, test coverage, shell quoting, OOM, low disk space, and run-as-root safety. Check whether specialty runtimes (`ik_llama.cpp`, LiteRT-LM, sherpa-onnx, CTranslate2) justify their complexity and ensure exact executable install commands work on both ARM64 and x86-64. Prefer fewer, proven components over speculative peak-speed hacks.

## Deliverables

1. **Evidence matrix** with direct URLs, precise hardware, model/runtime versions, performance and limitations. Clearly label unverified benchmarks.
2. **Decision table** for all four hardware profiles × three tasks, plus combined workflows: best and safe choices, why each wins, memory budget, expected speed/range, quantization, exact model download and license.
3. **Short user stories** from at least 8 independently documented projects/users, describing what worked, what failed, and lessons applicable to this repository.
4. **Architecture proposal** for an offline CPU-only pipeline, process and memory lifecycle, local APIs, and minimal UI/CLI controls, including a diagram.
5. **Implementation roadmap** with small ordered phases and explicit acceptance tests. Prioritize reliable pt-BR transcription, EN→PT-BR translation, then summarization and combined workflows. Include lightweight fallback pathways.
6. **Validated commands and test plan**, including exact pinned links, downloads, hashes if available, shell commands for both architectures, benchmark scripts and a realistic matrix of tests on actual hardware. Clearly distinguish commands you executed from those you only inspected.
7. **Repository review** identifying specific bugs, risks, and outdated claims in the current README/install script; propose concrete diffs. If authorized to write to GitHub, create a **draft PR** rather than directly modifying `main`, and do not claim that code was hardware-tested without evidence.
8. **Final recommendation**: the two or three highest-impact changes to implement first, expected benefits, unknowns and the minimal follow-up hardware test needed to validate them.

Be skeptical, comparative and practical. This project is for small, low-power, occasionally disconnected computers. **Actual Brazilian Portuguese accuracy, offline usefulness, reliable installation and end-to-end latency matter more than spectacular token-per-second headlines.**


## Additional hardware profile: AMD mini PC

- GMKtec K11, AMD Ryzen 9 8945HS (8C/16T), Radeon 780M integrated graphics, 32 GB DDR5-4800, 1 TB NVMe.
- Include **Vulkan shared-memory GPU inference** as well as CPU-only benchmarks for this machine. Compare Inkling 2 Mini, Qwen3.8 27B, Qwen3.6 35B-A3B, Gemma 4 26B-A4B and Qwen3.5 9B.
- Separately measure pt-BR STT, EN→PT-BR translation, summarization and total sequential-pipeline latency on this profile.
- Record the usable GPU-addressable memory/GTT, Mesa/kernel, RAM frequency and power limits. Avoid automatic kernel parameter changes and compare with the safe CPU-only backend.
- Benchmark full GPU offload, partial offload, context 8K/16K, Q8 KV, MTP where available, and task-specific quality.

