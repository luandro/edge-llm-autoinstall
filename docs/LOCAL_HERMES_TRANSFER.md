# Local Hermes → edge deployment: evidence and readiness

Reviewed 2026-11-27. **Hardware validation pending** for Pi 5 (4/8/16 GB), N95/N97 and K11. This repository prepares repeatable deployments. [local-hermes](https://github.com/luandro/local-hermes) is the live experiment lab on a CPU ThinkPad; do not duplicate its agent harness here. Transfer verified lessons in one direction, then independently validate on each target hardware class. The existing safe/best installation defaults are unchanged.

## Evidence ledger

| Finding | Evidence status | Deployment decision |
| --- | --- | --- |
| Local Hermes Q4 LFM3 + runtime LoRA, 64K context, one slot | ThinkPad reported in [LEARNINGS](https://github.com/luandro/local-hermes/blob/main/LEARNINGS.md) | Q4 base/adapter paired benchmarks; now selectable as experimental LFM3 agent profile (see update below). |
| Lean prompt 15,815 → 4,175 tokens; warm disk 58→39 s, catalog 41→35 s | Local reported individual runs, not statistical averages; some runs hit 600 s | Selective schemas, compact observations, bounded workflows. Do not generalize latency to Pi. |
| Hybrid checkpoints reduce repeated prefill | ThinkPad reported | Check model/runtime-specific support and measure actual uncached tokens; do not universally copy cache settings. |
| n-gram speculation and anonymous loading | Rejected in tested ThinkPad configuration; THP never engaged | Keep baseline mmap; speculation off on this model until new evidence. Not universal exclusions. |
| LFM3 base Q4 on Pi 5 2 GB | Independent [Nov 19 benchmark](https://peppe8o.com/install-llama-cpp-raspberry-pi/), ~62 prompt / ~9 generation tok/s; reported ~1.7–1.76 GiB peak, b12375; active cooling, 5 llama-bench repetitions, server tests mostly single runs | Prioritize compact candidate. Does not demonstrate LoRA, full Hermes, 64K agent context or combined STT/router RAM fit. |
| Potato OS dual runtime | [README](https://github.com/potato-os/core/blob/main/README.md) and [build script](https://github.com/potato-os/core/blob/main/bin/build_llama_runtime.sh); officially Pi 5 8/16 GB and Pi 4 8 GB, not 4 GB Pi 5 | Investigate ARM native/prebuilt and optional ik_llama on matched model. Keep upstream default. |
| MNN prefill | [Potato spike](https://github.com/potato-os/core/blob/main/benchmarks/mnn_spike_results.md): Pi 5 16 GB Qwen3.5-4B, 4 threads, MNN 27.6 pp / 4.1 tg vs IK ~11 pp / 3.2 tg, different quant formats, noisy cached prefill, no quality evaluation | Research only for prefill-heavy tasks; no verified LFM3 or tool/cache parity. |
| Laya Multilingual 322M | [Model card](https://huggingface.co/convaiinnovations/laya-multilingual), [training guide](https://nandhakishorm.github.io/laya/finetune/), [ONNX exporter](https://github.com/NandhaKishorM/laya/blob/main/scripts/export_onnx.py) | Decision classifier, not generative model. Zero-shot probabilities uncalibrated; compare rules/TF-IDF first; FP32 reference, INT8 only after quality and calibration checks. No installer integration yet. |

## Future deployment track

1. Start with the current safe profile and a 64-bit headless OS, active cooling, approved initial downloads and loopback API. Establish idle/loaded memory and temperature baseline. Retain existing 4K cap on 4 GB Pi; do not spoof context to Hermes. The current lab reports Hermes >=64K guard. Standalone 2K/4K tests are not full Hermes tests; verify real context and RAM before a separate 64K experiment.
2. Compare the same Q4 base and runtime LoRA with the existing sequential benchmark runner (license review required; LFM-1.0). Use explicit model names, not safe/best defaults:

       bash benchmark.sh --models lfm3_base_q4,lfm3_hermes_q4 --context 2048 --dry-run
       bash benchmark.sh --models lfm3_base_q4,lfm3_hermes_q4 --context 2048 --backend cpu --suite full --runs 3

   Approve downloads and confirm an idle inference workload first. This checks proposed tool calls, not actual agent execution. Repeat at 4096 if memory permits; keep Q8 adapter group for comparison. The runner may skip arms on its memory guard: record skipped/failed cases rather than bypassing it. Compare full Hermes via local-hermes separately.
3. ARM runtime candidates: official upstream aarch64 binary; native upstream with and without KleidiAI/OpenBLAS; ik_llama native IQK kernels. Compare 2/3/4 generation threads, 4 prefill threads, microbatch 64/128/256 where safe; one slot. Pin exact builds and model hashes. Confirm LFM3 graph, template, LoRA load, structured calls, reasoning flags and hybrid cache behavior before timing. The current ik_llama tree contains an LFM3 graph and template, not proof of complete compatibility. MNN later, only for compatible models with tested API and quality.
4. Use typed workflow steps and deterministic verifiers instead of repeated LLM calls; compact output before prompting. [Potato RIG validator](https://github.com/potato-os/core/blob/main/core/rig_envelope.py) and [OpenClaw installer](https://github.com/potato-os/core/blob/main/bin/install_openclaw.sh) are useful patterns, not a complete workflow engine or a Hermes config. Preserve permissions, approvals and fallback.
5. Start routing with rules, aliases and TF-IDF/BM25. Test a single multilingual Laya checkpoint only after the lab proves benefit. FP32 weights alone ~1.2 GiB; actual RSS may exceed this. Community [ONNX conversion](https://huggingface.co/onnx-community/laya-multilingual-ONNX) requires parity tests. Do not use classifier confidence as authorization or proof of completion. Optional noncommercial vegaml-learn is excluded. Fine-tune in the lab on verified PT-BR/EN examples only if simpler baselines lose.
6. STT, NMT, Laya and generative model must not all be resident by default on 4 GB. Test sequential stages versus keeping LFM3 warm; account for reload/cache loss, CPU contention and end-to-end voice time. Existing installer only provides one LLM service; these are proposed future capabilities. An offline LAN node can delegate to a separately authorized local inference machine; no silent cloud fallback.
7. Final hardware acceptance: zero OOM, no sustained full memory pressure or thermal throttling, verified task success, reproducible cold/warm p50/p95 with at least five paired smoke runs, eight-hour mixed workload and offline test. Do not change production settings just to pass a benchmark. Keep baseline/rollback. Colab GPU results assess quality/feasibility, not device CPU speed.

## Memory pressure diagnostics (read-only)

Borrow the approach from [Potato memory diagnostics](https://github.com/potato-os/core/blob/main/docs/memory-diagnostics-pi5.md), not its inconsistent model-size rows. High used RAM may be useful page cache. Record pressure and page faults as well as available RAM. On actual target, before and during each arm:

    free -h
    cat /proc/pressure/memory 2>/dev/null || true
    grep -E 'MemAvailable|SwapTotal|SwapFree' /proc/meminfo
    grep -E '^(pswpin|pswpout|pgmajfault) ' /proc/vmstat
    cat /proc/swaps
    cat /sys/block/zram*/mm_stat 2>/dev/null || true
    vcgencmd measure_temp 2>/dev/null || true
    vcgencmd get_throttled 2>/dev/null || true

For the actual inference PID and agent process tree: collect /proc/PID/status (VmRSS/RssAnon/RssFile), smaps_rollup PSS if readable, and major faults with a robust proc stat parser. Sample at modest intervals, distinguish process from host totals, report deltas and unavailable metrics as null. Check actual storage medium and model path. Never assume zram, swap changes, THP, root memory pinning, or a faster SSD fix RAM exhaustion. Do not change kernel/swap settings automatically.

## Transfer contract

Every lab experiment promoted or rejected should document date, baseline/candidate commits, hardware, OS, runtime/model/quant/context, config/dataset hashes, sample counts, cold/warm latency, verified success, total/new tokens, tool/model calls, memory/pressure and failure reasons; include reproduction, rollback and applicability. Label as local-measured, external-reported, hypothesis, target-measured or rejected. Default changes need independent target-class tests. Keep raw transcripts, credentials and community data private; preserve third-party license notices if copying code (Potato OS Apache-2.0). No source code from Potato OS is copied here. See also [Potato Inferno](https://github.com/potato-os/inferno) for future supervisor review.

No Pi hardware execution or full Hermes validation was performed by this documentation/catalog update.

## 2026-11-28 transfer update

See [LFM3 edge agent](LFM3_EDGE_AGENT.md). The ThinkPad lab adopted **merged Q4_K_M** (BF16 merge then quantization) after runtime LoRA produced 136 CPU_REPACK fallback warnings; merged produced zero, prefill 18.8→41.0 tok/s, 2/2 passes in both arms. This supersedes the earlier runtime-LoRA-only guidance. It also rejected Q4_0 and speculative decoding on that host; no blanket ARM conclusion. Prefer the merged model where supplied, keep the publisher's adapter path on USB, measure cold/warm separately. The lab's rules-first routing, TF-IDF/LogReg proposed escalation and Laya non-default decision are documented in its [decision-model research](https://github.com/luandro/local-hermes/blob/main/research/decision-models-and-deterministic-shortcuts.md). The existing safe general model remains rollback; no physical tests completed.

## Reopen the Pi harness experiment

The historical ~21.3K Pi prompt is not evidence of intrinsic upstream overhead; the unpublished local-pi configuration remains unavailable. See [Pi research](PI_AGENT_RESEARCH.md) for isolated CLI/Core comparisons and [next phase](PI_TELEGRAM_PLAN.md) for optional Telegram transport and evaluation. Keep local-hermes as lab; do not bypass its context guard or promote untested defaults.
