# Evidence-backed compact agent models

Last research review: **2026-11-24**. This file is a **candidate selection and validation plan**, not proof of working Hermes automation on our devices. Research evidence is mostly publisher/author benchmarks on other hardware. No measurements on Pi 5 4/8/16 GB, N95/N97, or our GMKtec K11 yet.

## Keep general and agent models separate

STT in Brazilian Portuguese, EN→PT-BR translation, and grounded interview summarization remain the primary goals of this project. **Neither a tool fine-tune nor a Hermes LoRA is a better default translator, STT model, or summarizer just because it calls tools more accurately.** The specialized models here are for **Hermes agent tasks**: choosing a tool, deciding not to call one, Bash/Python operations, and interpreting small local data files.

Use `--mode safe` for ordinary workloads. The optional `--agent-model NAME` replaces **the single local LLM service** with an experimental tool specialist; the installer does not keep two models resident or automatically route jobs between them. Re-running the installer changes the active service, so preserve work and expect downtime. Do not expose the unauthenticated API outside localhost.

## Selected: two directly deployable GGUF candidates

| Model | Exact file | Where to test | Why selected | Limits |
| --- | --- | --- | --- | --- |
| **BotPsy 0.8B** ([model + quant benchmarks](https://huggingface.co/qvac/BotPsy-0.8B-GGUFs)) | Pi 4 GB: `botpsy-0.8b-q4_k_m-imat.gguf` (529 MB); others: `botpsy-0.8b-q8_0.gguf` (810 MB) | Pi 4/8 GB, Pi 16 GB, N95/N97, K11 | Real **llama.cpp GGUF** evaluation at Q4 and Q8; publisher reports BFCL v4 **43.5% Q4** and **44.2% Q8**, against BF16 44.0%; Apache-2.0. Useful for **simple routing / tool-use decisions**. | Benchmarks were **not on our hardware or in Hermes**; English training preferred; it uses thinking tokens and needs output budget. Not a standalone coding agent or default PT-BR model. |
| **mini-agent-v2 1.5B** ([model and GGUFs](https://huggingface.co/F-A-I-L/mini-agent-v2-GGUF)) | Pi 4 GB: `mini-agent-v2-Q4_K_M.gguf` (986 MB); others: `mini-agent-v2-Q5_K_M.gguf` (1.13 GB) | Pi 4/8/16 GB, N95/N97, K11 | Apache-2.0; standard Qwen2.5 tool template; author tests BFCL non-live **86.2% vs 52.7% base**, live **65.7% vs 56.9%**, Bash **50.3% vs 41.7%**, Python **66.2% vs 59.2%**. Strong shell/Python fit. | Those scores are **bf16**, not quantized GGUF. InterCode Bash gains overlap with training, and author cautions against long autonomous loops; English-oriented, 2048-token SFT. |

Commands:

```bash
bash install.sh --agent-model botpsy --dry-run
bash install.sh --agent-model botpsy
bash install.sh --agent-model mini-agent --dry-run
bash install.sh --agent-model mini-agent
# Restore the normal general-purpose model:
bash install.sh --mode safe
```

BotPsy uses the publisher's **thinking-enabled** template setting `--chat-template-kwargs '{"enable_thinking": true}'` via the generated launch script. Ensure the client gives it enough output tokens (publisher suggests ≥2048) and does not expect high-quality full-language summaries. mini-agent uses `--jinja` and the embedded Qwen tool template. To try either in Hermes, configure a **custom OpenAI-compatible provider** pointing at `http://127.0.0.1:8080/v1`, model ID `edge-llm`; do not assume a long-lived remote Hermes session can reach another machine's loopback without a private tunnel.

## Selected for **manual research only**, not an installer default

**[LFM3-1.7B-hermes](https://huggingface.co/harness-hub/LFM3-1.7B-hermes)** is genuine Hermes-harness RL, unlike the two general tool fine-tunes above. Author's 150 held-out data-analysis tasks: **62% base → 78% adapted**, with **38% fewer tool calls on mutually solved tasks**. But a harder set of 40 repository tasks went **25% → 17.5%** (uncertain difference). It trains for a **64K+ context Hermes workflow**, and its GGUF adapter was explicitly **not re-evaluated**. The base/adaptation has a custom **LFM-1.0 license**, so review use conditions before redistributing.

GGUF files to test manually, if appropriate:

```bash
hf download LiquidAI/LFM3-1.7B-GGUF LFM3-1.7B-Q8_0.gguf --local-dir .
hf download harness-hub/LFM3-1.7B-hermes-GGUF LFM3-1.7B-harbor-hermes-lora-F16.gguf --local-dir .
# Run on a separate port; this is NOT the repo installer:
llama-server -m LFM3-1.7B-Q8_0.gguf \
  --lora LFM3-1.7B-harbor-hermes-lora-F16.gguf \
  -c 8192 --jinja -ngl 0 -t 4 --host 127.0.0.1 --port 8081
```

**Caution:** `-c 8192` is only a small-hardware *functional experiment*, NOT the 64K+ Hermes condition used to obtain the published result. The adapter may lose its advantage. Use the original author's settings when feasible, verify `llama.cpp` architecture/LoRA compatibility before relying on it, compare **base without adapter** versus **same base with adapter**, and measure full task completion. Do not place it on the general-purpose "best" list until an actual Hermes benchmark on target hardware shows consistent gains.

## Evaluated and deferred

| Candidate | Decision | Why |
| --- | --- | --- |
| [Gemma 4 E4B Sol-Traces v4](https://huggingface.co/RedTeamLab/Gemma-4-E4B-Sol-Traces-v4) | **Research-only / K11** | Small routing test rises **50% → 60%** across versions, but only 5 queries per tool; `apply_patch` stays **0/5**. Weak evidence for changing the stable Gemma default. |
| [Argos Qwen3.5 4B](https://huggingface.co/sciencemj/argos-harness-qwen3.5-4b) | **Skip installer** | Impressive fixed-schema next-call metrics but 29 **Argos** tools, not the user's Hermes tool schema, and no verified end-to-end Hermes outcomes. Valuable as a fine-tuning **method reference**. |
| [LFM2.5 24B-A2B Hermes v2](https://huggingface.co/harness-hub/LFM2.5-24B-A2B-hermes-v2) | **Defer** | Published tool-call reduction does not establish a task-success gain. Much larger memory footprint than compact options. |
| [TwIL 8B Hermes](https://huggingface.co/harness-hub/TwIL-8B-hermes) | **Skip** | Hermes training did not improve held-out task success; non-commercial license. |
| [MiniCPM5 1B function-call fine-tune](https://huggingface.co/ewin-reg/MiniCPM5-1B-Agentic-Tooluse-v3-GGUF) | **Watch** | Narrow exact-argument evidence, without demonstrated wins over selected models under comparable evaluation conditions. |
| [SteraFunctionGemma 270M](https://huggingface.co/strykes/SteraFunctionGemma-270M) | **Skip** | Tiny specialized function router, no strong end-to-end evidence for our tools. |

## Acceptance test before promotion to a default

Use the same **50-task minimum** on each relevant hardware and compare the specialist to the **current device's safe model** using exactly the same tool schemas, temperature and context. Evaluate at least 3 runs for unstable tasks. Include:

- 15 valid tool-routing choices, 10 correct tool-argument construction tasks, 5 correct *no-tool* decisions.
- 10 read-only shell / inspection tasks (never destructive commands), 5 sandboxed Python tasks with unit tests.
- 5 PT-BR user instructions (including accents and technical terminology).
- Separate regression suite: 10 PT-BR summaries/EN→PT-BR translations to confirm the specialist is **not** mistakenly being used as the general assistant.
- Capture *completed-task* success, invalid JSON, denied/unsafe actions, unintended tool calls, token consumption including thinking, prompt processing time, peak RSS/VRAM, cold-load time and CPU temperature. Use a clean temporary working directory and allowlist read-only tools. Never trust shell suggestions without human/operator authorization.

**Promotion requirements:** measurable task-success improvement over the safe model (not just BFCL), no new safety or parsing regressions, reproducible GGUF output at target quantization and context, and acceptable latency on the actual hardware. Until then all entries stay optional, and the safe/best table remains unchanged.

Sources: [BotPsy GGUF measurements](https://huggingface.co/qvac/BotPsy-0.8B-GGUFs), [mini-agent evaluation details and limitations](https://huggingface.co/F-A-I-L/mini-agent-v2), [LFM3 Hermes LoRA and scope](https://huggingface.co/harness-hub/LFM3-1.7B-hermes), [Gemma Sol-Traces v4](https://huggingface.co/RedTeamLab/Gemma-4-E4B-Sol-Traces-v4).
