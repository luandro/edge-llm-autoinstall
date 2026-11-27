# Hermes Workshop Rehearsal — Phase 2

Date: 2026-11-27. Continues `REPORT.md` (Phase 1) at `/tmp/opencode/workshop/REPORT.md`.

## 1. Verified lessons folded into this repository

- **Skill refactored with progressive disclosure:** `SKILL.md` 20,270 B → 4,679 B (-77%). Detailed procedures moved to bundled `references/*.md` (installation, verification, models, cloud-and-colab, workshop-hermes, troubleshooting). All safety requirements preserved: preview → approve → install, no `--yes` without authorization, no secrets in USB/repo/cloud, local-only service, manual failover, Groq 120B primary, 20B not independent backup, no parallel requests per account, no blind retry after timeout, honest evidence.
- **`docs/HERMES_WORKSHOP.md` updated** with verified Hermes v0.23.4 config facts, the reasoning-effort bug, real Groq probe results, 429/retry facts and the bounded-task target.
- **Reproducible scripts added:** `scripts/workshop-eval.py` (3-trial bounded task runner), `scripts/mock-429.py` (local 429/SSE endpoint with request log).
- **Existing capabilities preserved:** install.sh, workshop-install.sh, cloud-probe.py, benchmark suite, Colab CLI, edge-task.py all unchanged.

## 2. Prompt-size: before/after with actual API usage

Measured through the **real Hermes agent core** (`run_agent.AIAgent`) in an isolated `HERMES_HOME`, with `skills.auto_load: [edge-llm-autoinstall]` and the skills toolset enabled (the only way a skill body enters the prompt). Same model, prompt and config in both arms; only SKILL.md swapped.

| Arm | SKILL.md size | Input tokens requested | Result |
|---|---|---|---|
| Before (old skill) | 20,270 B | **10,790** | **FAIL — HTTP 413**: `Requested 10790` exceeds Groq's 8,000 TPM ceiling |
| After (refactored) | 4,679 B | **6,715** | **PASS** — 1 model request, 39 output tok (29 reasoning), 4.53 s |

The refactor cut ~4,075 tokens (−38%) and flipped the task from an outright provider rejection to success. With the **lean workshop config** (terminal toolset only, skill not auto-loaded — the recommended participant setup) the simple PT task used **3,618** input tokens, 1 model request, 0 tools.

**8K TPM is a hard per-request ceiling on Groq's free tier**, not merely a rate: a request above it returns 413 and cannot be compressed away. Byte estimates from `prompt-size` are indicative; actual API usage is authoritative.

## 3. Isolated test environment

- Fresh `HERMES_HOME=/tmp/opencode/workshop/hermes-home` with symlinks to the existing read-only dependency store (`installs/`, `cache/`) — no copy of 12 GB, no writes to the live store.
- Config mirrors `config/workshop-lean.yaml`: `platform_toolsets.cli: [terminal]`, `plugins.enabled: []`, `mcp_servers: {}`, `memory.memory_enabled: false`, terminal-only, `max_turns: 6`, bounded `tool_output`, no fallbacks.
- Groq via `provider: custom`, `base_url: https://api.groq.com/openai/v1`, `api_key: ${GROQ_API_KEY}` (secret only in isolated `.env`, mode 0600; never printed).
- A second isolated home (`mock-home`) points at the local 429 mock. **No existing Hermes profile, gateway or local-hermes service was modified.** The live `lfm3-harbor-hermes` service on 8080 was only read via `curl`, never stopped or changed.

## 4. Lean config validation against Hermes v0.23.4

- **Registered and effective:** `tool_output.max_bytes/max_lines/max_line_length`, `memory.memory_enabled`, `skills.external_dirs`, `fallback_providers`, `agent.max_turns`.
- **Present in `config.yaml` but not CLI-registered (CLI warns; runtime reads them):** `agent.reasoning_effort` (via `hermes_constants.resolve_reasoning_config`), `platform_toolsets` (via `agent_init`/gateway), `gateway.standalone` (temporary multiplex shim).
- **Verified bug:** `plugins/model-providers/custom` rewrites any reasoning effort to `reasoning_effort: "default"` for `api.groq.com`, but Groq `gpt-oss` accepts only `low`/`medium`/`high`. Direct probe: `low`/`medium`/`high` → 200; `none`/`default` → 400 with "must be one of low, medium, or high". Hermes logs a rejection and retries once. **Minimal-wait choice:** keep `reasoning_effort: low` (one harmless extra request) or omit it; never set `none`. Do not patch the shared install for a workshop.
- **Gateway:** a named profile can be parked (`profile_parked`) when the host gateway is standalone for another profile. Use the isolated home / direct agent core; never migrate or force others' live gateways.

## 5. End-to-end evaluations (real Groq, real Hermes agent, 3 trials each)

Recorded fields: input / output / reasoning tokens, model requests (`api_calls`), tool calls, wall-clock, 429s, correctness. Full per-trial JSON in `/tmp/opencode/workshop/eval-results/`.

| Task | Trials | Tool calls | Model requests | Input tok (first call where separable) | Output tok | Reasoning tok | Wall (s) | 429s | Correct |
|---|---|---|---|---|---|---|---|---|---|
| PT simple conversation | 3/3 pass | 0 | 1 | 3,618 | 38 / 72 / 62 | 26 / 56 / 46 | 6.1 / 18.1 / 14.0 | 0 | 3/3 |
| HW inspection (bounded card) | 3/3 pass | 1 | 2 | ~3,600 (7,425 cumulative) | 178 / 185 / 143 | 87 / 93 / 45 | 14.2 / 48.6 / 50.4 | 0 | 3/3 |
| USB detection + dry-run (tight card) | 3/3 bounded | 1 | 2 | 7,366 / 5,062 / 217 (+ cached 7,168 in t3) | 304 / 259 / 604 | 210 / 183 / 506 | 7.7 / 5.0 / 4.8 | 0 | 3/3 bounded; answer wording varied |
| Local service check (`/v1/models`) | 3/3 pass | 1 | 2 | 5,250 / 642 / 3,970 (+ cached) | 220 / 461 / 189 | 76 / 51 / 66 | 4.7 / 4.5 / 4.8 | 0 | 3/3 |
| Mock 429 recovery | 1/1 pass | 0 | 1 (after 2 × 429) | 10 | 3 | 0 | 8.35 | 2 (mock) | PASS |

Notes:
- The **loose** card ("Execute uma vez: …") caused 6-iteration exhaustion or 429s in early trials; the **tight** card ("Execute exatamente uma chamada de terminal com este comando: … Não leia arquivos antes de executar.") produced exactly one terminal call and two model requests. Use the tight wording.
- Back-to-back trials hit a real Groq 429 (`Used 7107, Requested 3858`, reset ~23 s) — confirming that staggering/cooldown is required. The evaluation script defaults to a 45 s cooldown between trials; **no parallel requests per account**.
- Groq prompt caching is active: several trials show `cache_read_tokens` (e.g. 2,304 / 7,168) and correspondingly reduced fresh input tokens.

## 6. Tasks not fully executable here (marked UNVERIFIED, not claimed)

- **Authorized installation in isolated sandbox:** no target Pi/N95/K11 and no prepared USB media; a real service/systemd install would alter this host. Only the bounded dry-run was exercised (with an intentionally invalid fake USB path; exit 1, handled safely, no mutation).
- **Provider failover:** no Cloudflare Workers AI token/account or OpenRouter key. Operator confirmed none available; routes left disabled. Do not enable untested or paid fallbacks.
- **Complete WAN failure:** the offline path was exercised only as `edge-task.py health` against the existing loopback service; no network-disabled install rehearsal was possible. The standalone USB CLI remains the documented manual fallback.

## 7. Privacy / accounts

- **Groq ZDR:** operator confirmed **enabled and verified** in the Groq console. Recorded as status only; no key values captured.
- **Cloudflare:** no credentials → documented only, UNVERIFIED.
- **OpenRouter:** left disabled; no verified free tool-capable model with ZDR/deny-training. UNVERIFIED.
- Groq 120B remains primary. 20B passed tool calling earlier but shared the same account quota counter — **not** an independent backup. No secret was printed, copied to USB or committed.

## 8. Remaining blockers to "ready"

1. Real bounded tasks on an actual target device with prepared USB media (install + service + inference).
2. Real failover test with operator-provided Cloudflare/OpenRouter credentials that pass privacy + tool-call checks.
3. Resolve the Groq reasoning-effort mapping bug upstream (or document the one-extra-request cost as accepted).
4. Keep <3,000 initial tokens: current lean first call ≈3,600; acceptable per "correctness first", but can be reduced by disabling the skill entirely for non-skill tasks.

## 9. Files changed / added

- `SKILL.md` (refactored, v1.2.0), `references/*.md` (6 new)
- `docs/HERMES_WORKSHOP.md` (verified findings)
- `scripts/workshop-eval.py`, `scripts/mock-429.py` (new)
- `REPORT_PHASE_2.md` (this file)

## 10. Participant setup guide (minimal, pt-BR)

See `docs/PARTICIPANT_SETUP_PT.md`. One page: create the profile, install only the reviewed skill, merge the lean config, run one bounded hardware card, and stop. No keys in the guide; the operator sets them privately.
