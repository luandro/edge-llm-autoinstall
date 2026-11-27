# USB-first workshop

## Facilitator preparation

Use an ext4/exFAT mounted USB SSD, preferably 64 GB or larger (check actual free space). Never format from these scripts. Use the same USB to prepare **each distinct hardware/OS profile** while online; this is not an architecture-independent installer or OS image. If two Pis have identical CPU/RAM/OS, one bundle is enough. Install a matching 64-bit Linux/systemd baseline beforehand, with Bash, coreutils, sudo and Python 3 (for benchmarks). Preparation requires git, internet, sudo for build dependencies and local build storage.

```bash
git clone https://github.com/luandro/edge-llm-autoinstall.git
cd edge-llm-autoinstall
bash prepare-usb.sh --usb /media/$USER/WORKSHOP
```

The script uses an independent cache, builds safe CPU llama-server and multilingual whisper-cli (base), downloads their weights, checks SHA256, and copies a committed Git snapshot without local secrets. No service changes on the preparation host. The USB freezes downloaded bytes, not independently pinned upstream source/model revisions. Reruns verify and reuse existing bundles; deliberately remove a corrupt/outdated bundle before rebuilding. CPU-only avoids GPU driver dependencies; K11 Vulkan remains an online-install option. Static C++ linking minimizes dependencies but a compatible Linux runtime/CPU is required. Test actual devices, not just profile names. SHA256 detects corruption, not malicious replacement; use trusted media.

The bundle contains a text LLM and CLI STT. Bring authorized 16kHz mono PCM WAV samples and reference transcripts separately. Whisper base does not support every Indigenous language. Dedicated NMT, transcription API/UI, OS images, offline Hermes installer and arbitrary-model benchmark downloads are not included.

## Exercise 1: cloud-backed Hermes

Follow https://hermes-agent.nousresearch.com/docs/getting-started/installation. Download and review the installer before running:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o /tmp/hermes-install.sh
bash /tmp/hermes-install.sh
hermes model
```

Prefer Groq Free: https://console.groq.com/keys . Enable Zero Data Retention in Data Controls (https://console.groq.com/docs/your-data). Select custom OpenAI-compatible endpoint https://api.groq.com/openai/v1, model openai/gpt-oss-120b, and enter the key interactively. Check actual limits at https://console.groq.com/docs/rate-limits; published 8K TPM can be restrictive for Hermes tool schemas. Rehearse the full session with minimal toolsets and realistic context. No shared USB credentials or account rotation to evade quotas.

Backup: OpenRouter (https://openrouter.ai/settings/privacy and https://openrouter.ai/pricing) has 50 free requests/day; disable training, require ZDR and select a compatible free tool model. Cloudflare Workers AI (https://developers.cloudflare.com/workers-ai/platform/pricing/ and https://developers.cloudflare.com/workers-ai/platform/data-usage/) has 10K neurons/day free and no training on customer content; more account/token setup. Cerebras (https://www.cerebras.ai/pricing) advertises $5 starter credits, not a permanent free quota. Gemini free-tier content may be used for improvement; Mistral ZDR requires paid access. All cloud prompts leave the device. Only synthetic/public exercises; no private transcripts, credentials or secret shell output. Disable unnecessary tools, remote auxiliary providers and cloud fallback, use a dedicated workshop profile. Check provider docs before class.

Load our skill with the existing Hermes skill scanner while online:
```bash
hermes skills install https://raw.githubusercontent.com/luandro/edge-llm-autoinstall/main/SKILL.md
hermes skills list
```
Alternatively review and copy SKILL.md from the trusted USB into a new directory under the active profile's skills folder (default ~/.hermes/skills/edge-llm-autoinstall/); do not overwrite existing skills without approval. See https://hermes-agent.nousresearch.com/docs/user-guide/features/skills.

Prompt: "Use edge-llm-autoinstall. Inspect the authorized target, identify the mounted USB, use its local checkout and preview safe offline installation. Show the plan and ask before system changes. Install and verify a real local chat completion. Benchmark Portuguese summary/translation. Install the local Whisper CLI if bundled. Do not download anything or transmit our data."

## Exercise 2: local deployment

On the target, open the repo-COMMIT folder on USB (START-HERE.txt).
```bash
bash install.sh --offline --mode safe --dry-run
bash install.sh --offline --mode safe
bash install-stt.sh
curl --fail http://127.0.0.1:8080/v1/models
bash benchmark.sh --server-url http://127.0.0.1:8080 --suite quick --runs 1
~/.local/bin/edge-transcribe -l pt -f sample.wav
```

Pass --usb /actual/mount if ambiguous. The binaries and model files are copied to local disk. Remove USB after completion. Offline never falls back to online, and --online restores existing online behavior. Keep API loopback-only; use authorized SSH forwarding for a separate Hermes controller. On 4 GB Pi ask before stopping LLM for STT and restart afterward. The cloud-backed Hermes requires WAN during assisted setup even though installer downloads nothing; disconnect WAN only after setup, then use direct local services. Switching Hermes to local inference is optional and separately evaluated for context/tool use; inspect auxiliary providers and fallback before private tasks.

## Real hardware acceptance gate

- Prepare each actual OS/CPU; on a clean compatible target with no cached model, disable WAN and install. Check runtime compatibility, successful inference, and no network downloads. Test removal and reboot.
- Test missing/multiple USBs, explicit paths with spaces, bad checksum and wrong profile; fail closed. Measure installation duration.
- Run PT-BR summary, EN->PT-BR translation, and 30s PT/EN WAV transcription; record timing, RAM and human quality. Indigenous-language results require consent and fluent review.
- Rehearse full Hermes cloud session, restricted tools and approvals, actual quotas, SSH access and no secret logging. Have a direct CLI fallback if WAN fails.
- Record installed OS, versions and checksums. Hardware and provider API validation pending; do not label workshop ready until passed.
