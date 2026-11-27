# Hermes workshop: lean cloud bootstrap and offline fallback

Source: [local-hermes LEARNINGS](https://github.com/luandro/local-hermes/blob/b706d83386d13954b451026ae83e1fdd4d06ca3c/LEARNINGS.md), [lean config](https://github.com/luandro/local-hermes/blob/b706d83386d13954b451026ae83e1fdd4d06ca3c/config/lean-config.yaml). On that ThinkPad a terminal-only CLI, disabled plugins and lean skills reduced first-turn prompt from 15,815 to 4,175 tokens (-74%), with both tested tasks passing. Bounded "run exactly once, report, stop" prompts avoided looping. These are local results, not measured Groq results. A merged LFM3 Hermes GGUF improved prefill 18.84 to 41.03 tok/s on that laptop (2 tested tasks); not a proven general agent or Pi deployment.

## Setup
Use the reviewed Hermes installer copied to USB (still needs internet for dependencies) or https://hermes-agent.nousresearch.com/docs/getting-started/installation. Run `hermes profile create workshop --no-skills` (check installed version's help), then `hermes -p workshop setup`; choose Blank Slate, configure terminal only. Install just the reviewed Edge skill into this profile, not every bundled skill. Inspect the profile's config, back it up, merge config/workshop-lean.yaml, never overwrite an existing live profile. Check actual keys against installed version; no plugins, MCP, memory, remote gateway or web tools during deployment. Run `hermes -p workshop prompt-size --platform cli --json` if supported; actual API usage is authoritative. Aim for <=5K input tokens first turn, 1–2 tool calls and short outputs; 6 turns is a safety cap, not a target. Set reasoning low if supported; test correctness. Do not shrink model context below actual Hermes requirement (local-hermes has a 64K floor in its tested version; Pi 4K is not full Hermes).

## Cloud routes (verify accounts before workshop)
- Groq primary: https://api.groq.com/openai/v1, openai/gpt-oss-120b, enable Zero Data Retention (https://console.groq.com/docs/your-data). Free limits https://console.groq.com/docs/rate-limits: published 30 RPM / 1K RPD / 8K TPM / 200K TPD. Account limits may differ. GPT-OSS 20B is a candidate only after testing quality and its actual model quota; do not assume independent quotas. Groq caching can exclude cached tokens from rate limits after processing, not guaranteed (https://console.groq.com/docs/prompt-caching). Keep prefix stable, no parallel requests per account. For 429 respect retry-after/reset, wait or switch, never retry an already executed mutation blindly.
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
