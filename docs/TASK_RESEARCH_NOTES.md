# Evidence-backed research notes: speech, translation and summarization

Updated 2026-11-23. These findings come from the linked public sources. **The shared Gemini report was not accessible through the research environment**, so this file does not attribute any conclusions to that report. Treat model choices below as benchmark candidates, not validated installation profiles.

## Brazilian Portuguese STT

- **Do not select solely by an English-language WER table.** ai-tier's Raspberry Pi 5 16 GB benchmark reports Parakeet TDT v3, Whisper, Qwen3-ASR and others but its displayed WER is primarily English/German. Its Parakeet result (RTF 0.112, peak memory 2,271 MiB) is interesting for *speed/memory*, not a pt-BR accuracy result. [Source](https://ai-tier.com/stt).
- **Parakeet TDT V3 pt-BR 30s ONNX** is a focused Brazilian Portuguese fine-tune. Verify accuracy across conversational pt-BR accents, noise and multi-minute sessions; test VAD, chunk stitching, timestamps and ONNX Runtime ARM64 availability. Its model card is publisher-authored, not independent validation. [Model card](https://huggingface.co/alefiury/parakeet-tdt-v3-ptBR-30s-onnx).
- **Whisper.cpp base/small multilingual** is a comparatively mature low-complexity fallback with explicit Portuguese transcription settings. Smaller models may trade accuracy for performance. [Runtime](https://github.com/ggml-org/whisper.cpp).
- **sherpa-onnx** is an alternative for ARM64 and CPU edge ASR; compare actual pt-BR recognition instead of assuming English benchmark results transfer. [Runtime](https://github.com/k2-fsa/sherpa-onnx).
- A documented Raspberry Pi 5 speech-translation project combines Parakeet ASR and a local translation model. Reuse lessons from its audio preprocessing and deployment, but reproduce pt-BR and en→pt-BR tests independently. [Pi translator](https://github.com/koh43/pi-translator).

**First experiments:** benchmark Whisper.cpp multilingual base against Parakeet pt-BR ONNX on Pi 8/16 GB, N95/N97 16 GB and K11 32 GB with real, consented pt-BR clips. Measure WER/CER, speech/audio-duration ratio (RTF), peak RSS, cold-start and silence hallucinations.

## English → Brazilian Portuguese translation

- Compare a **dedicated MT model first** (Marian/OPUS-MT en→pt, CTranslate2 INT8, Argos Translate / Bergamot, NLLB-200 distilled) against a local LLM. A dedicated MT runtime may produce better latency and use less RAM, but it must be evaluated for Brazilian (rather than European) Portuguese output. Do not imply `pt` language labels automatically mean pt-BR.
- For conversational speech-translation, compare segmented translation against full-paragraph translation for names, terminology and punctuation. [Pi translator](https://github.com/koh43/pi-translator); [CTranslate2](https://github.com/OpenNMT/CTranslate2).
- No EN→PT-BR model/runtime is integrated into `install.sh` yet. The `/v1/chat/completions` LLM endpoint can *be prompted* to translate, but it is not a dedicated translation service and no fidelity guarantee is made.

## Summarization and end-to-end pipelines

- Begin with **Qwen3.5 2B/4B** for constrained devices and a larger model on the K11, but score factual faithfulness and prompt-processing latency as well as decode speed. Larger MoE models can look impressive at token generation yet still take a long time to ingest a 20–30-minute transcript.
- For long recordings: VAD → ASR chunking with timestamps → merge and deduplicate → paragraph/chunk summaries → final grounded summary with timestamp references and explicit unknowns. Load large models **sequentially**, especially on Pi 8 GB, instead of leaving ASR+MT+LLM processes simultaneously resident.
- The local API in this repository presently implements **text generation only**. Implementing STT and a purpose-built translation endpoint requires a separate tested phase. Do not call the existing API an audio transcription service.
- For K11, benchmark **Gemma 4 E4B**, **LFM2.5 24B-A2B QAD**, **Gemma 4 26B-A4B**, **Inkling 2 Mini**, and **Qwen3.8 27B** on the same Portuguese summarization and translation examples. Strong decode numbers reported for Radeon 780M do not establish which model has the best accuracy. [Reproducible Radeon 780M measurements](https://github.com/cyberpuffin-digital/amd-ryzen-inference-testing); [llama.cpp discussion](https://github.com/ggml-org/llama.cpp/discussions/32165).

## Implementation order

1. Collect a small openly licensed or consented pt-BR test corpus and a human-reviewed en→pt-BR translation set.
2. Add offline ASR and MT scripts only after exact ARM64/x86-64 runtime versions, model filenames and sizes are verified. Keep both opt-in; use local-only endpoints.
3. Benchmark text generation with `python3 scripts/benchmark.py` and record actual machine specs, Vulkan version, GGUF commit/hash and task scores.
4. Add short and long transcript summarization, timestamp preservation, sequential model loading and OOM recovery.
5. Run full integration tests on the Pi 8/16 GB, N95/N97 16 GB and K11 32 GB before changing any automatic default.

**Research limitations:** no third-party pt-BR figure or Radeon 780M decode figure in this document is a measurement performed on the user's exact machines. The Gemini share `https://share.gemini.google/7Qfa2CQS836x` needs a text/Markdown/PDF export for reliable comparison against this shortlist.
