# Hermes workshop: lean cloud bootstrap and offline fallback

Source evidence: [local-hermes LEARNINGS](https://github.com/luandro/local-hermes/blob/b706d83386d13954b451026ae83e1fdd4d06ca3c/LEARNINGS.md) and [lean config](https://github.com/luandro/local-hermes/blob/b706d83386d13954b451026ae83e1fdd4d06ca3c/config/lean-config.yaml). On that ThinkPad a terminal-only CLI, disabled plugins and lean skills reduced the first-turn prompt from 15,815 to 4,175 tokens (-74%), with both tested tasks passing. Bounded "run exactly once, report, stop" prompts avoided looping. These are **local** results, not Groq measurements and not a proven general agent or Pi deployment.

## Setup (verify flags against installed version)

```bash
hermes profile create workshop --no-skills     # check --help first
hermes -p workshop setup                        # Blank Slate, terminal only
```

Install **only** the reviewed Edge skill into this profile, not every bundled skill. Inspect the profile config, back it up, and merge `config/workshop-lean.yaml` into the **new dedicated profile only** — never overwrite a live profile. No plugins, MCP, memory, remote gateway or web tools during deployment. Run `hermes -p workshop prompt-size --platform cli --json` if supported; **actual API usage is authoritative**. Aim for <=5K first-turn input tokens, 1–2 tool calls and short outputs; 6 turns is a safety cap, not a target. Do not shrink model context below the installed Hermes requirement (local-hermes has a 64K floor; a Pi 4K model is not full Hermes).

### Verified configuration facts (Hermes v0.23.4)

- There is **no native `groq` provider**. Use `provider: custom` with `base_url: https://api.groq.com/openai/v1`, `api_mode: chat_completions`, and `api_key: ${GROQ_API_KEY}` (env reference; secret stays in `.env`).
- Config keys present in `config.yaml` but absent from CLI registration (CLI warns yet the runtime reads them): `agent.reasoning_effort` (via `hermes_constants.resolve_reasoning_config`), `platform_toolsets` (via `agent_init`/gateway), `gateway.standalone` (temporary multiplex shim). `tool_output.*`, `memory.memory_enabled`, `skills.external_dirs`, `fallback_providers` and `agent.max_turns` are registered and effective.
- **Broken 429 recovery bug:** `plugins/model-providers/custom` maps any reasoning effort to `reasoning_effort: "default"` on `api.groq.com`, but Groq `gpt-oss` models accept only `low`/`medium`/`high` and reject `default`/`none` with HTTP 400. Hermes then logs "rejects reasoning effort ... using route default" and retries, costing one extra model request. Tested directly: `low`, `medium`, `high` -> 200; `none`, `default` -> 400. Keep `reasoning_effort: low` in config (the retry is harmless) or accept the route default; do not set `none`.
- Gateway multiplex: a named profile can be parked (`profile_parked`) when the host gateway is standalone for another profile. For a participant reproduction, prefer a **fresh isolated `HERMES_HOME`** (default profile, no shared gateway) or run the real agent core directly; do not migrate or force other people's live gateways without authorization.

## Provider facts (measured)

| Model | Tool call | Prompt tok | Completion tok (reasoning) | Quota |
| --- | --- | --- | --- | --- |
| `openai/gpt-oss-120b` | PASS (1 exact `report_disk` call) | 132 | 54 (28) | account 1000 RPM / 8000 TPM |
| `openai/gpt-oss-20b` | PASS (1 exact call) | 132 | 62 (39) | **same account counter**, not independent |

Keep **GPT-OSS 120B primary**. 20B is only an experimental quality alternative; its quota counter decremented the same account bucket, so it is **not** an independent backup. Ask the operator to enable and verify **Groq ZDR** in the console — it cannot be toggled from Hermes config.

## Bounded task cards (Portuguese)

Each new short session uses the known checkout path and the exact approved command. Do not rerun side effects after a timeout; inspect status and logs first.

1. "Execute uma vez: uname -m; free -h; df -h \"$HOME\". Resuma arquitetura, RAM e espaço em disco e pare."
2. "Use a skill edge-llm-autoinstall. Execute uma vez o dry-run com --offline --mode safe --usb CAMINHO. Mostre modelo e requisitos, pare antes de alterar."
3. After human approval, run the exact dry-run command without `--dry-run`. Prefer the operator terminal for long sudo/build/install commands; redirect logs locally and show exit code + last 10 lines. Never bypass sudo or auto-approve. Report status and stop.
4. "Execute uma vez systemctl is-active edge-llm e consulte /v1/models via curl local. Relate resultado e pare." Then make one actual completion via the local API.
5. Install Whisper separately with approval. Stop the LLM first on a 4 GB Pi with permission; restart later. Test synthetic WAVs. No private input while any cloud is configured.

**Target for a hardware-inspection task:** <3,000 initial input tokens, one terminal call, two model requests. Prioritize correctness over the number. A measured trial that used an open-ended prompt ("Não use ferramentas") still produced two `curl` calls; use the exact bounded card above and verify tool count from the agent, not from the prompt wording.

## 429, checkpoint and retry

Local mock endpoint pattern (`mock_429.py`): return 429 with `Retry-After: 1` for the first N requests, then 200; log every request locally. Verified with the real Hermes agent: `provider_retry_after_seconds()` parses numeric `Retry-After`, `RETRY_AFTER_CAP_S = 600`, `LIVE_RETRY_WAIT_CAP_S = 60`, and a 9999s header is capped to 600s. Checkpoints are enabled by default (`max_snapshots: 50`, 7-day retention). Stagger groups; **no parallel requests per account**; never deliberately exhaust provider quota.

## WAN failure

If primary and backups fail, finish via direct USB CLI; no cloud is needed for the installer itself. The facilitator's merged LFM3 laptop is a bounded offline helper only if actually tested, with free RAM and no competing gateway/single-slot contention; do not alter or stop live services without approval. The workshop still works from printed instructions alone. Record actual cloud quotas, prompt size, tool results, rounds, latency and backup success in the rehearsal report; mark untested items **unverified**.
