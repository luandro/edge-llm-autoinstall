# Models and capability boundaries

## What is actually implemented

- One GGUF LLM via `llama.cpp` (experimental `ik_llama.cpp` on Pi 8 GB best), installed as `edge-llm.service`, OpenAI-compatible chat at `http://127.0.0.1:8080/v1`, model ID `edge-llm`, localhost only.
- Optional USB-only Whisper CLI (hardware validation pending).
- **Not implemented:** transcription endpoint, dedicated neural translation engine, unified multi-model pipeline, automated model unloading or benchmark-driven tuning. Do not claim they work or invent `--task`/`--tasks` flags. Request an implementation task before modifying the repository to add them.

See `references/installation.md` for the safe/best model table. Treat benchmark estimates as **unverified on the target** until measured.

## Optional tool-use models (explicit request only)

`bash install.sh --agent-model botpsy` and `--agent-model mini-agent` work on all supported machines as experimental alternatives. BotPsy 0.8B is an English-first thinking-enabled tool router; mini-agent-v2 1.5B is optimized for Bash, Python and small tool calls. On Pi 4 GB the installer uses Q4; on larger devices BotPsy Q8 and mini-agent Q5. They **replace**, rather than augment, the one local LLM service. No task router, simultaneous model loading or automatic delegation exists.

Before testing, read `docs/AGENT_MODELS.md` for quantified evidence, limits, licenses, safe test plan and rollback:

```bash
bash install.sh --agent-model botpsy --dry-run
bash install.sh --agent-model mini-agent --dry-run
# After approval, select exactly one:
bash install.sh --agent-model mini-agent
# Run read-only/sandboxed tool-call tests, including no-tool decisions and PT-BR prompts.
bash install.sh --mode safe   # restore the general-purpose baseline
```

The **LFM3-1.7B Hermes RL LoRA** is a **manual research experiment only**, not an installed option. Authors evaluated a 64K+ context workflow and did not re-evaluate the GGUF adapter. An 8K Pi run is not equivalent; do not promote a specialist as the default PT-BR summarizer/translator. See `references/troubleshooting.md`.

## K11 optional `--model` choices

`gemma4-e4b`, `gemma4`, `qwen36` (larger agent/coding MoE, ~24 GiB GTT), `inkling` (English-focused, unverified on this K11), `qwen38` (dense, likely slow), `gptoss20b`, `qwen35-9b`. Model/GPU override flags work **only** on K11. Do not apply NVIDIA CUDA/NInfer-all instructions to the AMD 780M.

## Lab transfer and hardware readiness

Read `docs/LOCAL_HERMES_TRANSFER.md` in a full checkout before experimenting with LFM3, Laya or ARM backends. The separate [local-hermes](https://github.com/luandro/local-hermes) repo is the active ThinkPad test lab. Transfer findings with their evidence status; do not promote defaults based on ThinkPad or third-party Pi measurements. The Q4 LFM3 base/adapter pair is benchmark-only, not an installer flag. Keep Pi 4 GB context cap and safe defaults; a 2K–4K standalone model test is not a full Hermes test. Collect memory PSI, RSS, major faults, swap deltas and thermal metrics where available. Never automatically adjust kernel/swap settings or load multiple neural models at once on 4 GB. Laya and multi-model scheduling remain unimplemented.
