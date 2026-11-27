---
name: edge-llm-autoinstall
description: Deploy and benchmark offline AI on Pi 5, N95/N97 and K11
compatibility: Hermes Agent with terminal or SSH access to Linux with systemd; internet for online installs; matching prepared USB for offline safe deployment.
metadata:
  author: luandro
  version: "1.2.0"
---

# Edge AI Fleet Installer

## When to Use

Install, troubleshoot, benchmark or tune local/offline AI on Raspberry Pi 5 (4/8/16 GB), Intel N95/N97 (16 GB), or GMKtec K11 (Ryzen 9 8945HS / Radeon 780M, 32 GB). Also choose models for pt-BR summarization, STT, EN→PT-BR translation and lightweight local agent workflows.

This is a deployment procedure, not a claim that every workload is implemented. Read the target repository's current `README.md` and `install.sh --help` before any install.

## Source of Truth

- Public project: https://github.com/luandro/edge-llm-autoinstall
- Installer `install.sh`; syntax/scope tests `tests/smoke.sh`; text benchmark `scripts/benchmark.py`.
- **Implemented:** one GGUF LLM via `llama.cpp` (experimental `ik_llama.cpp` on Pi 8 GB best), `edge-llm.service`, OpenAI-compatible chat at `http://127.0.0.1:8080/v1`, model ID `edge-llm`, localhost only; optional USB-only Whisper CLI (hardware validation pending).
- **Not implemented:** transcription endpoint, dedicated NMT, multi-model pipeline, automatic unloading or benchmark-driven tuning. Do not invent `--task`/`--tasks` flags. Treat benchmark estimates as unverified until measured on the target.

## Routing — load the matching reference before acting

| Need | Read |
|---|---|
| Inspect target, choose safe model, **preview → approve → install**, USB-first workshop | [references/installation.md](references/installation.md) |
| Verify service, run benchmarks, tune stable settings, route workloads | [references/verification.md](references/verification.md) |
| Model tables, optional agent models, K11 choices, capability boundaries | [references/models.md](references/models.md) |
| Colab benchmark, Groq/Cloudflare/OpenRouter routes, ZDR and privacy rules | [references/cloud-and-colab.md](references/cloud-and-colab.md) |
| Hermes lean profile, Groq config, bounded PT task cards, 429/checkpoint, measured facts | [references/workshop-hermes.md](references/workshop-hermes.md) |
| Failures, recovery, report-back format, lab transfer | [references/troubleshooting.md](references/troubleshooting.md) |

These reference files are bundled with this skill when installed by URL. Files under `docs/` (e.g. `docs/WORKSHOP_USB.md`, `docs/AGENT_MODELS.md`, `docs/BENCHMARKING.md`, `docs/COLAB_CLI.md`) exist in a full checkout and are referenced from the relevant pages above.

## Quick start (only after reading the relevant reference)

```bash
git clone --depth=1 https://github.com/luandro/edge-llm-autoinstall.git
cd edge-llm-autoinstall
bash -n install.sh && bash tests/smoke.sh
bash install.sh --mode safe --dry-run      # show operator; get ONE approval
bash install.sh --mode safe                # only after explicit approval
```

For the bounded workshop install use `bash workshop-install.sh --usb /actual/mount --dry-run`, then the same command without `--dry-run` from the operator's terminal after approval.

## Hard invariants (never violate)

- **Preview → approve → install.** Never use `--yes` without the operator's explicit prior authorization. Never retry a side-effectful command after a timeout; inspect status/logs first.
- **No secrets anywhere but the local environment.** Never print an API key, put one in the repository or USB media, or send credentials, confidential content, raw transcripts or secret shell output to any cloud. No shared credentials or account rotation to evade quotas.
- **Local-only service.** `127.0.0.1:8080` only; never expose an unauthenticated listener. Never format/mount arbitrary devices; never auto-adjust kernel/swap/BIOS/GTT settings.
- **Manual failover is the default.** Groq GPT-OSS 120B is primary. GPT-OSS 20B is **not** an independent quota backup (same account counter). Enable and verify Groq ZDR in the console. Test Cloudflare/Backups for real tool calling before enabling; require verified free access + ZDR/deny-training for OpenRouter or leave it disabled.
- **No parallel requests per account.** Respect `Retry-After`; use a local mock 429 to rehearse cooldown/checkpoint/resume without exhausting provider quota.
- **Honest evidence.** Never execute model-suggested commands during tests, never present another machine's throughput as target hardware results, and mark untested items unverified. Do not declare readiness until a real Hermes session completes the bounded workshop tasks.
