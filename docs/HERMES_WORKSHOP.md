# Hermes workshop: lean cloud bootstrap and offline fallback

Source: [local-hermes LEARNINGS](https://github.com/luandro/local-hermes/blob/b706d83386d13954b451026ae83e1fdd4d06ca3c/LEARNINGS.md), [lean config](https://github.com/luandro/local-hermes/blob/b706d83386d13954b451026ae83e1fdd4d06ca3c/config/lean-config.yaml). On that ThinkPad a terminal-only CLI, disabled plugins and lean skills reduced first-turn prompt from 15,815 to 4,175 tokens (-74%), with both tested tasks passing. Bounded "run exactly once, report, stop" prompts avoided looping. These are local results, not measured Groq results. A merged LFM3 Hermes GGUF improved prefill 18.84 to 41.03 tok/s on that laptop (2 tested tasks); not a proven general agent or Pi deployment.

## Setup
Use the reviewed Hermes installer copied to USB (still needs internet for dependencies) or https://hermes-agent.nousresearch.com/docs/getting-started/installation. Run `hermes profile create workshop --no-skills` (check installed version's help), then `hermes -p workshop setup`; choose Blank Slate, configure terminal only. Install just the reviewed Edge skill into this profile, not every bundled skill. Inspect the profile's config, back it up, merge config/workshop-lean.yaml, never overwrite an existing live profile. Check actual keys against installed version; no plugins, MCP, memory, remote gateway or web tools during deployment. Run `hermes -p workshop prompt-size --platform cli --json` if supported; actual API usage is authoritative. Aim for <=5K input tokens first turn, 1–2 tool calls and short outputs; 6 turns is a safety cap, not a target. Do not shrink model context below actual Hermes requirement (local-hermes has a 64K floor in its tested version; Pi 4K is not full Hermes).

**Verified on Hermes v0.23.4 (2026-11-27):** no native `groq` provider exists — configure `provider: custom`, `base_url: https://api.groq.com/openai/v1`, `api_mode: chat_completions`, `api_key: ${GROQ_API_KEY}` (secret only in `.env`). Config keys registered and effective: `tool_output.*`, `memory.memory_enabled`, `skills.external_dirs`, `fallback_providers`, `agent.max_turns`. Keys present in `config.yaml` but not CLI-registered (CLI warns; runtime still reads them): `agent.reasoning_effort`, `platform_toolsets`, `gateway.standalone`. `gateway.standalone` is a temporary multiplex shim; a named profile can be parked when the host gateway is standalone for another profile — for a participant reproduction prefer a fresh isolated `HERMES_HOME` or the real agent core directly; never migrate or force others' live gateways without approval.

**Reasoning-effort bug:** the custom provider maps any effort to `reasoning_effort: "default"` on `api.groq.com`, but Groq `gpt-oss` accepts only `low`/`medium`/`high` and rejects `default`/`none` with HTTP 400. Hermes logs a rejection and retries, costing one extra model request. Direct test: `low`/`medium`/`high` -> 200; `none`/`default` -> 400. Keep `reasoning_effort: low` (harmless retry) or use the route default; do not set `none`.

## Cloud routes (verify accounts before workshop)
- Groq primary: https://api.groq.com/openai/v1, openai/gpt-oss-120b. **Operator must enable and verify Zero Data Retention in the Groq console** (https://console.groq.com/docs/your-data) — it cannot be toggled from Hermes config. Free limits https://console.groq.com/docs/rate-limits: published 30 RPM / 1K RPD / 8K TPM / 200K TPD; measured account headers were 1000 RPM / 8000 TPM. **8K TPM is a token rate limit, not the model context length.** GPT-OSS 20B passed a real tool-call probe but shared the same account quota counter (remaining tokens decremented from 7814 to 7612) — keep 120B primary and do **not** treat 20B as an independent quota backup. Groq caching can exclude cached tokens from rate limits after processing, not guaranteed (https://console.groq.com/docs/prompt-caching). Keep prefix stable, no parallel requests per account. For 429 respect retry-after/reset, wait or switch, never retry an already executed mutation blindly.
- Cloudflare Workers AI backup: custom OpenAI endpoint https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1, @cf/openai/gpt-oss-120b (function calling, listed ZDR: https://developers.cloudflare.com/ai/models/%40cf/openai/gpt-oss-120b/). Token with Workers AI permissions, account ID, verify actual free allocation/usage and no paid charges (https://developers.cloudflare.com/workers-ai/platform/pricing/). API https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/. Validate real Hermes tool calls; availability is not a test.
- OpenRouter second backup: exact verified :free tool-capable model, 50 requests/day published free plan. Require ZDR and deny training via account settings or verified provider routing; do not assume free account supports all policy controls. Verify cost zero and effective routing; if not possible, do not enable it. https://openrouter.ai/pricing/ and https://learn.openrouter.ai/courses/control-routing/provider-selection. Avoid random model routing or paid fallback.
- Separate real organizations' own accounts, no shared credentials or account rotation to evade quotas. No confidential community content or secret shell outputs sent to any cloud, even with ZDR. No keys in USB or repo.

Manual failover is the default. After provider setup, test both routes via actual Hermes. Optional explicit fallback for approved Cloudflare account, matching installed Hermes version (https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers):

```yaml
fallback_providers:
  - provider: custom
    model: "@cf/openai/gpt-oss-120b"
    base_url: https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1
    key_env: WORKSHOP_CF_KEY
```

Set key privately in profile environment, verify `hermes -p workshop fallback check`; never enable untested or paid routes. Pin auxiliary providers to main or disable auxiliary tasks as supported; check no unexpected discovery, fallback or paid routes. For offline profile remove ALL cloud routes/auxiliaries and test with WAN disabled. A failover invalidates prompt cache and sends history to a second provider, so use only approved public/synthetic data. Prefer separate fresh short sessions if failover is not proven safe. Use a local mock 429 endpoint to test cooldown and checkpoint/resume without intentionally exhausting cloud quota.

## Scripted task cards (Portuguese)
Avoid a single open-ended "install everything" prompt. Each new short session uses the known checkout path and the exact approved command. Do not rerun side effects after a timeout; inspect status and logs first.

1. "Execute uma vez: uname -m; free -h; df -h \"$HOME\". Resuma arquitetura, RAM e espaço em disco e pare."
2. "Use a skill edge-llm-autoinstall. Execute uma vez o dry-run com --offline --mode safe --usb CAMINHO. Mostre modelo e requisitos, pare antes de alterar."
3. After human approval, run the exact dry-run command without --dry-run. Prefer operator terminal for long sudo/build/install commands; redirect logs locally and show exit code + last 10 lines. Never bypass sudo or auto-approve. Report status and stop.
4. "Execute uma vez systemctl is-active edge-llm e consulte /v1/models via curl local. Relate resultado e pare." Then make one actual completion via local API.
5. Install Whisper separately with approval. Stop LLM first on Pi 4GB with permission; restart later. Test synthetic WAVs. No private input while any cloud is configured.

## WAN failure
If primary and backups fail, finish via direct USB CLI; no cloud needed for the installer itself. The facilitator's existing local-hermes merged LFM3 laptop is a bounded offline helper if actually tested, sufficient free RAM, no competing gateway/single-slot contention, no cloud auxiliary/fallback; do not alter or stop live services without approval. Do not promise arbitrary multistep autonomous installs on that model. The workshop still works using printed instructions without any agent. Check actual cloud quotas, prompt size, tool results, rounds, latency and backup success in rehearsal report. All live provider tests pending.

## Minimal provider probe

After confirming real free quota and privacy, run one synthetic function-call probe using keys already set securely in the shell (never print them):

```bash
python3 scripts/cloud-probe.py groq --yes
python3 scripts/cloud-probe.py cloudflare --yes
python3 scripts/cloud-probe.py openrouter --model VERIFIED_MODEL:free --yes
```

Reports tool call correctness, usage and rate-limit headers without executing the tool or retrying. This is not an end-to-end Hermes test. OpenRouter explicitly requests zero price, ZDR and deny training; if rejected do not relax privacy to make the test pass. Follow with the real lean-profile rehearsal. If all cloud providers fail, the standalone CLI described in WORKSHOP_USB.md works without Hermes.

**Verified probe results (2026-11-27, real Groq API):** 120B — `tool_call_ok: true`, prompt 132 tok, completion 54 tok (28 reasoning), ~0.12 s; 20B — `tool_call_ok: true`, prompt 132 tok, completion 62 tok (39 reasoning). The probe must send a normal `User-Agent` (e.g. `curl/8.0`): the default `Python-urllib/x` UA is rejected by the Cloudflare fronting Groq with HTTP 403 / error 1010.

## Verified 429 / checkpoint facts

A local mock endpoint returning 429 with `Retry-After: 1` then 200 exercised the real retry path: attempt 1 and 2 got 429 (parsed and capped to 1 s), attempt 3 succeeded. Hermes `provider_retry_after_seconds()` parses numeric `Retry-After`; `RETRY_AFTER_CAP_S = 600`, `LIVE_RETRY_WAIT_CAP_S = 60`; a `Retry-After: 9999` is capped to 600 s. Checkpoints are enabled by default (`max_snapshots: 50`, 7-day retention). Stagger groups, no parallel requests per account, never deliberately exhaust provider quota, and never blindly retry an executed mutation after a timeout.

## Bounded task target (measured)

For a hardware-inspection card aim for <3,000 initial input tokens, one terminal call and two model requests; prioritize correctness. A trial with the open-ended prompt "Não use ferramentas" still produced two `curl` tool calls — use the exact bounded card 1 above and verify tool count from the agent, not the prompt wording. Record actual input/output/reasoning tokens, model requests, tool calls, wall-clock time, rate-limit errors and correctness per trial; mark untested items unverified and do not declare readiness until a real Hermes session completes the bounded tasks.

Preferred bounded deployment: tell Hermes the approved USB path and have it run `bash workshop-install.sh --usb /actual/mount --dry-run` exactly once; ask approval, then run the same without --dry-run from the human's terminal (or --yes only after explicit approval and available sudo). Return only the exit code and concise status. Do not let a cloud agent read lengthy logs, credentials or sensitive content. This reduces tool rounds and preserves manual fallback.
