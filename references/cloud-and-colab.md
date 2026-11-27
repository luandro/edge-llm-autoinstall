# Cloud benchmark and cloud routes

Read this before any quota-consuming or privacy-sensitive cloud use. Cloud is optional; the standalone USB CLI works without Hermes or internet.

## Official Google Colab CLI benchmark

For cross-model quality comparisons when the target cannot efficiently load every model, use `colab-benchmark.sh`. Read `docs/COLAB_CLI.md` in a full checkout before any paid or quota-consuming runtime allocation.

```bash
git clone https://github.com/luandro/edge-llm-autoinstall.git
cd edge-llm-autoinstall
bash colab-benchmark.sh --dry-run
# Only after the operator authorizes GPU allocation and OAuth authentication:
bash colab-benchmark.sh --models small --suite quick
# Once initial results are verified:
bash colab-benchmark.sh --models small --suite full --runs 3
```

The official `google-colab-cli` (Linux/macOS) provisions a T4 by default, forwards the remote benchmark script, downloads `reports/colab/<session>/comparison.md` + JSON/CSV in a ZIP, and stops the VM in a `finally` block. It can bootstrap the CLI via `uv` or Python 3.12, but **never auto-grant OAuth permissions, secretly allocate compute or impersonate an account**. A Colab account with available quota is required; a ChatGPT subscription does not provide this entitlement. For authorized headless use, perform Google ADC login with proper scopes and use `--auth adc --yes` only after explicit approval. Treat a failed stop command as an outstanding billable runtime and alert the operator.

Tests are synthetic proposed-tool-call, translation and summary comparisons; the runner never executes model-suggested commands. Colab CUDA throughput must never be presented as Raspberry Pi, N95/N97 or Radeon 780M performance. All 4+ large models require explicit memory/download checks and approval. Do not upload community recordings or private datasets to Colab without consent.

## Cloud routes (verify accounts before the workshop)

- **Groq primary:** `https://api.groq.com/openai/v1`, `openai/gpt-oss-120b`. Enable Zero Data Retention in the Groq console (https://console.groq.com/docs/your-data). Published free limits: 30 RPM / 1K RPD / 8K TPM / 200K TPD; **actual account limits may differ**. 8K TPM is a token **rate limit**, not the model context length. Groq prompt caching can exclude cached tokens from rate limits after processing — not guaranteed. Keep the prefix stable; no parallel requests per account. On 429 respect `Retry-After`/reset, wait or switch, and never blindly retry an already executed mutation.
- **Cloudflare Workers AI backup:** custom OpenAI endpoint `https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1`, `@cf/openai/gpt-oss-120b` (function calling, listed ZDR). Use a token with Workers AI permissions plus the account ID; verify actual free allocation/usage and no paid charges. API: https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/. Validate real Hermes tool calls; availability alone is not a test.
- **OpenRouter second backup:** only an exact verified `:free` tool-capable model. The free plan publishes 50 requests/day. Require ZDR and deny training via account settings or verified provider routing; do not assume a free account supports all policy controls. Verify zero cost and effective routing; if not possible, do not enable it. Avoid random model routing and paid fallback.

Use separate real organizations' own accounts. **No shared credentials or account rotation to evade quotas. No confidential community content, private files, credentials, raw transcripts or secret shell output to any cloud, even with ZDR. No keys in USB media or repository.**

## Manual failover is the default

After provider setup, test both routes through actual Hermes. Optional explicit fallback for an approved Cloudflare account, matching the installed Hermes version:

```yaml
fallback_providers:
  - provider: custom
    model: "@cf/openai/gpt-oss-120b"
    base_url: https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1
    key_env: WORKSHOP_CF_KEY
```

Set the key privately in the profile environment and verify `hermes -p workshop fallback check`; never enable an untested or paid route. Pin auxiliary providers to main or disable auxiliary tasks where supported; check for unexpected discovery, fallback or paid routes. For an offline profile remove **all** cloud routes and auxiliaries, then test with WAN disabled. A failover invalidates the prompt cache and sends history to a second provider — use it only with approved public/synthetic data. Prefer fresh short sessions if failover is not proven safe. Use a local mock 429 endpoint to test cooldown and checkpoint/resume without exhausting cloud quota (see `references/workshop-hermes.md`).

## Minimal provider probe

After confirming real free quota and privacy, run one synthetic function-call probe with keys already set securely in the shell (**never print them**):

```bash
python3 scripts/cloud-probe.py groq --yes
python3 scripts/cloud-probe.py cloudflare --yes
python3 scripts/cloud-probe.py openrouter --model VERIFIED_MODEL:free --yes
```

This reports tool-call correctness, usage and rate-limit headers without executing the tool or retrying. It is **not** an end-to-end Hermes test. OpenRouter explicitly requests zero price, ZDR and deny training; if rejected, do not relax privacy to make the test pass. Follow with the real lean-profile rehearsal. If all cloud providers fail, the standalone CLI in `docs/WORKSHOP_USB.md` works without Hermes.

**Verified note:** `cloud-probe.py` must send a normal `User-Agent` (e.g. `curl/8.0`). The default `Python-urllib/x` UA is rejected by Cloudflare fronting Groq with HTTP 403 / error 1010.
