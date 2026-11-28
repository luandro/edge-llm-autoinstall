# LFM3-1.7B Hermes: edge agent profile

Updated 2026-11-28. **Recommended first experimental agent on Pi 5 and Intel N95/N97, not a validated production default.** General-purpose Qwen safe/best and specialist alternatives remain available. This repo is hardware deployment; [local-hermes](https://github.com/luandro/local-hermes) owns harness experiments.

## Install and rollback

    bash install.sh --online --agent-model lfm3-hermes --dry-run
    bash install.sh --online --agent-model lfm3-hermes
    # From freshly prepared portable v2 USB (no target network/build):
    bash install.sh --offline --agent-model lfm3-hermes --dry-run
    bash install.sh --offline --agent-model lfm3-hermes
    bash install.sh --mode safe --dry-run
    bash install.sh --mode safe

Approve after reviewing plan and [LFM-1.0 license](https://huggingface.co/LiquidAI/LFM3-1.7B-GGUF). USB includes both [base Q4_K_M](https://huggingface.co/LiquidAI/LFM3-1.7B-GGUF) and [F16 LoRA](https://huggingface.co/harness-hub/LFM3-1.7B-hermes-GGUF); checksums and immutable revisions recorded during preparation. One service, localhost only, alias edge-llm. No automatic cloud escalation. Do not treat a local tool call as authorization.

| Device | Agent profile starting settings | Stock Hermes |
| --- | --- | --- |
| Pi 5 4 GB | Q4_K_M, 4096 ctx, 4 threads max, batch 512, ubatch 128, one slot | Not compatible with stock 64K guard; direct API / validated lean harness only |
| Pi 5 8/16 GB | Q4_K_M, 8192 ctx, 4 threads max, batch 512, ubatch 256, one slot | 65536 only as separate measured experiment (prefer 16 GB) |
| N95/N97 16 GB | Q4_K_M, 65536 ctx, 4 threads max, batch 512, ubatch 256, one slot | Experimental, verify actual server metadata and memory before agent use; reduce context for standalone tests if needed |

The launcher preserves mmap default, no speculation, conservative hybrid checkpoints (four, minimum step 256, cache RAM 128 MiB) when supported by exact runtime. These limits are hypotheses, not copied blindly from the lab's 1024 MiB cache. No automatic kernel, swap or governor changes. Active cooling, headless OS, one request, memory headroom. Try 2/3/4 CPU threads, 64/128/256 microbatch, compare uncached prefill and decode separately. Flash attention, larger checkpoint cache, optimized ARM CPU kernels, KV quantization are A/B candidates, not assumed compatible. No context spoofing.

### Prefer a merged model

If a trusted `LFM3-1.7B-hermes-merged-Q4_K_M.gguf` is already in the selected model directory, the installer uses it without runtime LoRA. Otherwise it downloads/copies base and adapter and serves them with --lora. Local merged model is not shipped by this change: the publisher distributes a LoRA, not this lab-generated merged binary. Build on laptop/strong host, not Pi: pin original BF16 base and PEFT adapter revisions, merge with `PeftModel.from_pretrained(...).merge_and_unload()`, convert using matching upstream llama.cpp convert_hf_to_gguf.py, quantize to Q4_K_M (optional imatrix using consented calibration text), record all hashes and exact commands, compare tool-call parity before copying to target. Follow [lab recipe and measurements](https://github.com/luandro/local-hermes/blob/main/LEARNINGS.md). Copy trusted file into ~/.local/share/edge-llm/models or --model-dir; base/adapter still retained for baseline and USB integrity. Do not download an unknown merged model. The lab's exact calibration artifacts are not committed; do not claim bit-identical reproduction.

## Evidence and candidate ordering

- [Publisher RL report](https://huggingface.co/harness-hub/LFM3-1.7B-hermes): 78% vs 62% on 150 held-out data tasks, 38% fewer calls on jointly solved tasks; harder repo tasks 17.5% vs 25%, uncertain. Not GGUF or Pi-tested, not general coding superiority.
- [Local lab](https://github.com/luandro/local-hermes/blob/main/LEARNINGS.md): merged Q4 prefill 18.8→41.0 tok/s on ThinkPad, 136→0 CPU_REPACK fallbacks, 2/2 each; Q4_0 not faster there, n-gram speculation off, hybrid checkpoints avoid repeated prefill. Lean toolset measured 15,815→4,175 input tokens. Not Pi/N95 performance.
- [Independent Pi 5 base benchmark](https://peppe8o.com/install-llama-cpp-raspberry-pi/): Pi 5 2 GB Q4 base ~62 prompt/~9 generation tok/s, ~1.7–1.76 GiB peak as reported. Different runtime/context/host from this profile. [AI Tier Pi 5](https://ai-tier.com/devices/raspberry-pi-5/) reports base LFM3 ~10 tok/s generation, not Hermes adapter. Memory depends heavily on context and runtime. Do not infer 64K fit from 4K figures.
- Qwen3/3.5 0.6–2B: baseline general text and tools; keep current Qwen3.5 0.8B safe Pi4 and Qwen3.5 4B safe NUC. Compare 1.7B Qwen3 where a verified GGUF is available. LFM3 QAD Q4_0 base is research-only (not the same as merged fine-tune).
- BotPsy 0.8B and mini-agent-v2 1.5B stay installable as specialized tool-call baselines. FunctionGemma 270M is a fine-tuning candidate for fixed schemas, not general agent. Laya multilingual 322M is a classifier experiment only, not a zero-shot trusted router; use TF-IDF/BM25/linear classifiers first.
- Potato OS [core](https://github.com/potato-os/core) targets Pi 5 8/16 GB, not 4 GB. Borrow typed workflow envelopes, deterministic verifiers, memory pressure diagnostics and runtime comparisons; retain upstream llama.cpp until matched ARM evidence justifies alternative. No large SSD-paged MoE as a 4 GB agent default.

## Agent workflow and testing

Start deterministic read-only commands only for unambiguous approved intent; mixed/write/conditional instructions fall through. Rules → TF-IDF/BM25 shortlist → calibrated small linear classifier if needed → LLM with bounded tool set, not a resident Laya on 4 GB. Validate arguments, permissions, results, cap iterations and tokens; no shell execution from benchmark. Prefer compact observations, a terminal-only lean config for controlled tests and progressive disclosure; avoid repeated model calls, unrelated plugins, redundant tool-search loops. Never silently drop requested actions. For stock Hermes use the verified >=64000 context path, then measure true end-to-end tasks. Reference [local-hermes lean configuration](https://github.com/luandro/local-hermes/blob/main/config/lean-config.yaml) and [decision research](https://github.com/luandro/local-hermes/blob/main/research/decision-models-and-deterministic-shortcuts.md).

    bash benchmark.sh --models lfm3_base_q4,lfm3_hermes_q4 --context 4096 --backend cpu --suite full --runs 3
    bash benchmark.sh --server-url http://127.0.0.1:8080 --suite full --runs 3

First command compares runtime adapter vs base; second measures installed merged/adapter profile, separately record which. Include Qwen/BotPsy/mini-agent baseline under same context and decoding. Keep Q8 quality reference on NUC if memory permits. Use paired PT-BR/EN native tool calls, no-tool routing, error recovery, task success, argument correctness, token count, turns, cold/warm p50/p95, prompt and generation tok/s, peak RSS/PSS and host memory PSI, faults, swap, temperature; at least five smoke repetitions and sustained offline workload. Evaluate full Hermes with local-hermes eval separately, no fabricated stock-Hermes compatibility. Stop if OOM, sustained paging or unacceptable accuracy; restore safe. Review translated/summarized text manually (source-grounded facts, names, numbers). [Task models](TASK_RESEARCH_NOTES.md).

**Unverified:** no physical Pi/NUC benchmark or full Hermes on these profiles; portable kit builds and full rehearsal need rerunning after this change. LFM3 fine-tune is not yet validated for PT-BR or general summarization. Dedicated MT and STT alternatives are research only; sequence models on 4 GB. No promise of production readiness.
