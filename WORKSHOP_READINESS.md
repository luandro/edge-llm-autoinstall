# Workshop deployment readiness — Phase 3

Date: 2026-11-27. Continues `REPORT_PHASE_2.md`. Evidence rule: **PASS** = measured on this laptop; **FAIL** = measured and broken; **UNVERIFIED** = cannot be measured without operator credentials or physical target hardware. Emulation and directory stand-ins are **not** physical target validation.

## 1. Phase 2 repository state (verified)

| Check | Result |
|---|---|
| Working tree / HEAD at start | clean, `10953da` |
| GitHub CI (`Shell smoke tests`) | success, run `46067258834` |
| Local `tests/smoke.sh` | exit 0 (34 PASS lines; `ERROR:` lines are intentional negative tests) |
| `python3 -m unittest discover -s tests -v` | exit 0 |
| Syntax (`bash -n` + `py_compile`) | exit 0 |
| Phase 2 docs/scripts present | `SKILL.md` v1.2.0, 6 `references/*.md`, `scripts/workshop-eval.py`, `scripts/mock-429.py`, `docs/HERMES_WORKSHOP.md`, `REPORT_PHASE_2.md` |

Phase 3 added commits (all pushed, CI green):
- `d012613` — consolidated Portuguese participant instructions.
- `0f14394` — fixed `prepare-usb.sh` abort under `pipefail` (see §4).

## 2. Adopted lean configuration and skill — PASS

`config/workshop-lean.yaml` was applied to a fresh profile. Measured with `hermes prompt-size --platform cli --json` in an **isolated** `HERMES_HOME`:

| Mode | Tools | Tool JSON | Skills index | Terminal-only bounded task |
|---|---|---|---|---|
| Terminal-only deployment (recommended) | 4 | 4,915 B | 0 (skill installed, not auto-loaded) | PASS: 1 tool call, 2 model requests, 7,433 cumulative input tokens |
| Skill-enabled customization (optional) | terminal + skills | — | skill body loaded | FAIL at 12,441 input tokens > Groq 8,000 TPM (413); documented limit, not a target |

The Edge skill installs from URL with all six bundled references and is discoverable via `hermes skills list`. Terminal-only deployment is the workshop path; skill-enabled customization is only for adapting the procedure and must stay within the 8K per-request ceiling.

## 3. Fresh participant install through the standard interface — PASS

Installer: `https://hermes-agent.nousresearch.com/install.sh` (sha256 `c73dad4d…493214`), pinned to release commit `8fc0374447313e276f6b9a2764bfc750190c966a`.

```bash
HERMES_HOME=/tmp/opencode/participant-hermes HOME=/tmp/opencode/participant-home \
  bash /tmp/opencode/participant-install.sh \
  --non-interactive --skip-browser --skip-computer-use --commit 8fc0374447313e276f6b9a2764bfc750190c966a
```

| Evidence | Result |
|---|---|
| Installer exit | 0, `✓ Install complete! [detached @ 8fc0374447]` |
| Version | `Hermes Agent v0.23.4 (2026.9.24)`, Python 3.14.9, SDK 2.54.0 |
| Isolation | Own `tools/`, `installs/` and checkout; no symlink to the live dependency store (only internal Python/npm links) |
| Live state | No live Hermes profile was created/overwritten and no service/gateway was restarted; the live `coder` gateway continued its own cron activity |
| Profile creation | `hermes profile create participant --no-skills --no-credentials --no-alias` → PASS |
| Skill install | URL install → PASS, all six references fetched |
| Lean profile | `platform_toolsets.cli: [terminal]`, 4 tools, skills index empty |

Note: the effective profile config is `$HERMES_HOME/profiles/participant/config.yaml` (created on first write); until then the root `$HERMES_HOME/config.yaml` applies.

## 4. USB kit preparation — IN PROGRESS

Environment: x86_64 Pop!_OS 24.04, Docker 29.9.3 + buildx 0.39.1 (rootless), 109 GB free, no mounted USB device. Operator approved directory stand-in and QEMU attempts.

**Deviation:** the real `prepare-usb.sh` requires a mountpoint (`:33`), which a directory stand-in cannot satisfy. The build runs the repository's own `prepare-usb.sh` logic with **only** `mountpoint`/`findmnt` stubbed and both architecture loops reduced to amd64; downstream steps (checksums, provenance, published bundles, marker) are untouched.

**Bug fixed during rehearsal:** the original script used `awk '$1=="Digest:" {print $2; exit}'` in a pipeline under `set -Eeuo pipefail`; the early `exit` sent SIGPIPE to `docker buildx imagetools inspect`, aborting before `base.lock` was written. Verified with `bash -x`, fixed in `prepare-usb.sh`, committed as `0f14394`, CI green.

Pinned revisions: `sources.lock` (llama/whisper HEADs) and `base.lock` (`debian:bookworm-slim@sha256:e67eeead…9ce0e`).

- **x86_64 kit: PASS.** `KIT_BUILD_EXIT=0`; 9.4 GB of portable bundles, provenance (`sources.lock`, `base.lock`, `models.lock`, build info, CMake caches, licenses), cached Hermes installer and samples, `START-HERE.txt`, marker `.portable-complete` = `0f143942d19c58dfdc4ec22372b3228202ffbb05`. All six HF model revisions pinned and verified against Hub size/LFS SHA where available; all bundle `SHA256SUMS`, `hermes/SHA256SUMS` and `samples/SHA256SUMS` verify with `sha256sum --strict -c`. Rehearsal image `edge-usb-rehearsal:amd64` built.
- **ARM64 kit: PASS (cross-compiled, not Docker-emulated build).** Docker `--platform linux/arm64` still returns `exec format error` under rootless Docker even after host `qemu-user-static` registration (daemon mount namespace does not see host binfmt). The working path cross-compiles with `g++-aarch64-linux-gnu` (`scripts/usb-build/Dockerfile.cross-arm64`, `scripts/build-arm64-cross.sh`) and verifies with `qemu-aarch64-static -L <arm64 sysroot>`. Both binaries are ELF `ARM aarch64`; `llama-server --version` reports `1.1.0-dev (build 1, commit 8e23278)` built for Linux aarch64; `whisper-cli --help` runs. Published into the same kit: three Pi model bundles + Whisper bundle + aarch64 provenance, all `SHA256SUMS` verified. (The first script run hit a `| head` SIGPIPE under `pipefail`, fixed with `sed -n`.) A script-side SIGPIPE is not a kit defect.

## 5. Native, emulated and network-disabled tests — PASS (with documented caveats)

- Native: §1 checks PASS; missing-USB and path-with-spaces negative tests PASS; incomplete kit fails closed.
- Real provider: Phase 2 measured 3/3 per bounded task; Phase 3 re-ran terminal-only PASS and skill-enabled FAIL (8K ceiling).
- Mock 429 recovery: Phase 2 PASS (2×429 → 200, "OK", 8.35 s).
- **Emulated / `--network none` rehearsal: real failure found and repaired.**
  - First x86_64 full run: **FAIL** — `AssertionError: empty answer`; Qwen3.5 spent the entire 256-token `max_tokens` budget in `reasoning_content`.
  - Empirical probe on the prepared 0.8B bundle: baseline → empty content (reasoning length 1,071); `reasoning_effort: none` → final content, 0 reasoning; `chat_template_kwargs.enable_thinking: false` → final content; `reasoning_budget: 0` → still empty. Fix: `rehearse.py` now sends `reasoning_effort: none` (commit `84240a2`, CI green).
  - **Second x86_64 full run: PASS** (`REHEARSAL_EXIT=0`, `PASS x86_64 full`). All four models verified checksums and `--version`; both PT summary and PT/EN translation returned non-empty content; Whisper PT/EN sample transcription completed. Measured: 0.8B 6.35/7.72 s, 2B 11.21/14.21 s, 4B 26.44/31.40 s, gemma 42.82/111.03 s; STT 7.82/7.41 s. `--network none` and read-only kit mount, so no WAN and no host mutation.
  - **Quality caveats (human review required, not harness failures):** 0.8B and 2B mangled Friday/nine (`sábado às 19h`, `quinta-feira às nove`); 4B answered correctly; gemma answered correctly but verbosely. eSpeak-based STT outputs are approximate (`"free resident"`, accented-Portuguese distortions). These are synthetic samples, not human or Indigenous-language evaluation.
  - **ARM64 emulated checks under `qemu-aarch64-static -L <sysroot>`:** all three Pi bundles and the Whisper bundle passed checksum verification; all `llama-server --version` checks and `whisper-cli --help` passed; bounded 0.8B inference produced non-empty content in 62.34 s (12 completion tokens, same "Friday at nine" quality caveat). **Emulated Whisper STT: UNVERIFIED (time limit)** — transcription did not finish within 600 s and a dedicated rerun also hit 1,800 s; the ARM `whisper-cli` binary itself loads and `--help` runs, and x86_64 STT passed in 7–8 s. The cause is not established: native ARM behavior remains UNVERIFIED. Emulation speed is not target performance.

## 6. Successful USB detection and installation preview — PASS (directory stand-in)

Prepared directory stand-in: `/tmp/opencode/workshop/edge-llm-usb/edge-llm-usb`. Command:

```bash
EDGE_LLM_TEST_PROFILE=pi4 bash install.sh --offline --usb "$KIT" --mode safe --dry-run
```

Output includes the detected `portable/x86_64/llm/Qwen3.5-0.8B-Q4_K_M.gguf (safe CPU)`, `Hardware: pi4`, `Mode: safe`, `GGUF`, `Backend: cpu` and `API: http://127.0.0.1:8080/v1` — i.e. a successful detection and installation preview with a **prepared directory stand-in** — not mounted physical media and not a target test.

On this laptop `workshop-install.sh --dry-run` deliberately strips `EDGE_LLM_TEST_PROFILE` and therefore fails the unsupported-CPU check (Intel i7-8650U); that is expected and documents why the direct command was used. No physical target is implied.

## 7. Cloudflare / OpenRouter failover — UNVERIFIED

Operator deferred Cloudflare ("try without it for now, but keep it documented as next obvious choice"). No Workers AI token/account ID or OpenRouter key was supplied. Routes remain disabled; no untested or paid route enabled. Procedure is documented in `docs/HERMES_WORKSHOP.md` and `docs/PARTICIPANT_SETUP_PT.md`.

## 8. Local-hermes offline facilitator — PASS (bounded)

Read-only verification of the existing service (`llama-server`, pid 145019, model `lfm3-harbor-hermes`, 127.0.0.1:8080 only):

| Check | Result |
|---|---|
| `GET /v1/models` | 200; one local model, `owned_by: llamacpp` |
| Bounded `POST /v1/chat/completions` with `reasoning_effort: none`, `reasoning_budget: 0`, `max_tokens: 40` | `content: "PONG"`, `finish_reason: stop`, 3 completion tokens |
| Config routing | `model.provider: custom`, local URL, `fallback_providers: []`, no MCP, memory off |
| Service untouched | no restart/stop; gateway units only read (`coder` active, default failed) |

Caveat: without zero reasoning budget, a small `max_tokens` is consumed by `reasoning_content` and final content is empty. Do not promise arbitrary multistep autonomous installs from this model.

## 9. Manual fallback without Hermes or internet — PARTIAL

Verified here: `python3 scripts/edge-task.py health` → `API local: lfm3-harbor-hermes`; `pt 'The meeting is on Friday at nine.' --max-tokens 512` → `A reunião é na sexta-feira às nove.` (exit 0). `edge-task.py` uses only Python stdlib and the loopback API, fails closed, and sends nothing to the cloud. The offline installer path was verified by the successful `--dry-run` in §6, and the offline inference/STT path by the `--network none` container rehearsal in §5 — both without Hermes or WAN. A real systemd install still requires target hardware.

## 10. Consolidated participant instructions — PASS

`docs/PARTICIPANT_SETUP_PT.md` (committed `d012613`, updated in this phase) covers both modes, fresh isolated install, profile creation, skill install, lean config with backup, bounded cards, offline/manual commands, local-hermes caveat, failover status and recovery.

## 11. Status summary

| Item | Status |
|---|---|
| Phase 2 committed/documented/CI | PASS |
| Skill + lean config, terminal-only vs skill-enabled | PASS |
| Fresh standard-interface Hermes install, isolated | PASS |
| x86-64 USB kit in directory stand-in | PASS |
| ARM64 kit (cross-build + emulated version/inference) | PASS; emulated STT UNVERIFIED (QEMU timeout) |
| Native tests | PASS |
| Network-disabled container rehearsal (x86_64 full) | PASS |
| Successful USB detection + install preview | PASS (directory stand-in) |
| Cloudflare/OpenRouter failover | UNVERIFIED (deferred, no credentials) |
| Local-hermes bounded backup | PASS |
| Manual CLI fallback | PARTIAL — loopback CLI and offline rehearsal pass; combined install + service lifecycle unverified |
| Portuguese instructions | PASS |
| Physical target install/service/inference | UNVERIFIED (no Pi/N95/K11) |

## 12. Remaining risks

1. No physical target device or mounted USB: kit correctness on real Pi 5 / N95 / K11 is unproven.
2. ARM64 relies on cross-compilation plus emulation because rootless Docker cannot use host binfmt; physical Armv8-A execution is unproven, and emulated Whisper STT did not complete within 1,800 s (QEMU throughput only).
3. Groq 8,000 TPM hard per-request ceiling: skill-enabled or uncompressed prompts fail with 413; terminal-only path stays under it.
4. Real 429s occur on back-to-back trials; serial requests with 45 s cooldown are required.
5. Port 8080 is occupied on this laptop by the live facilitator service; real `edge-llm` install cannot be exercised here.
6. Cloudflare/OpenRouter fallback has no validated free+ZDR+tool-capable route; enabling any untested route is prohibited.

## 13. Recovery procedures

- **413 / 429**: reduce prompt and confirm no skill auto-load; wait `Retry-After` or 45 s; never run parallel requests on one account.
- **Reasoning-effort 400**: keep `low`; never set `none`; accept one extra request.
- **Timeout**: verify state, logs and checkpoints before any retry; never re-run side-effectful commands blindly.
- **USB not detected**: pass explicit `--usb`; marker must be `edge-llm-usb v2` and `.portable-complete` must exist.
- **8080 busy**: inspect with `ss -ltnp`; do not stop another service automatically.
- **Unsupported CPU**: offline install fails closed; supported hardware only.
- **LFM3 empty answer**: set zero reasoning budget and score only final `content`.
- **ARM `exec format error`**: use cross-built binaries with `qemu-aarch64-static -L sysroot`, or test on the target; do not register host binfmt without approval.

## 14. Readiness checklist and decision

- [x] Lean config adopted and measured
- [x] Edge skill install/invocation verified; two modes distinguished
- [x] Fresh participant install via standard interface, isolated
- [x] Native checks green; CI green
- [x] x86-64 kit complete with checksums and provenance
- [x] ARM64 kit complete; emulated version/inference checks green (emulated STT UNVERIFIED on QEMU time limit)
- [x] `--network none` rehearsal outputs reviewed for quality (caveats recorded)
- [x] Successful USB detection + install preview on prepared media (directory stand-in)
- [ ] Cloudflare failover validated with operator credentials (deferred)
- [ ] Physical target install + service + inference (no device)
- [x] Local-hermes bounded backup verified, untouched
- [x] Manual CLI fallback verified on loopback
- [x] Portuguese participant instructions consolidated

**GO / CONDITIONAL GO / NO-GO by architecture**
- **x86-64 (N95/N97/K11): CONDITIONAL GO** — laptop rehearsal and kit checks pass; physical validation still required.
- **ARM64 (Pi 5): UNVERIFIED / NO-GO for workshop** — cross-build/emulation only; no physical Pi and no Docker binfmt emulation.
- **Physical target deployment: NO-GO** until a real device completes install + service + inference with prepared USB media.
- **Cloudflare failover: UNVERIFIED** — next obvious choice once credentials and privacy checks are provided.

## 15. Files changed in Phase 3

- `prepare-usb.sh` — pipefail/SIGPIPE fix while resolving the base image digest.
- `scripts/usb-build/rehearse.py` — send `reasoning_effort: none` so reasoning models return final content.
- `docs/PARTICIPANT_SETUP_PT.md` — consolidated instructions plus both reasoning knobs.
- `scripts/usb-build/Dockerfile.cross-arm64`, `scripts/build-arm64-cross.sh` — reproducible ARM64 cross-build path for rootless Docker hosts.
- `WORKSHOP_READINESS.md` — this report.

All changed scripts pass `bash -n` / `py_compile`; all commits were pushed and GitHub CI rerun green (`46079341182`, `46083151442`, `46084967841`, `46091156698`). No credentials, private config or sensitive logs were committed.

**Post-session evidence loss (2026-11-28):** a harness server restart cleared `/tmp/opencode/workshop/`, including the prepared kit, both isolated Hermes homes, raw per-trial JSON, Phase 1 `REPORT.md` and the mock logs. Only the committed summaries in this report and `REPORT_PHASE_2.md` survive. Any action that references `$KIT`, the ARM sysroot or the isolated homes requires rebuilding that state first; this is why preserving a sanitized, verified kit outside `/tmp` is now the highest-value laptop action.

## 16. Senior review outcome (Codex `gpt-6.2-sol`, low effort, 2026-11-28)

Called after the GLM delegation because the installed launcher pinned `glm-5.3-flash` instead of the intended 5.4. Codex reviewed `WORKSHOP_READINESS.md`, `docs/GLM_ACTION_PLAN.md` and the installer/scripts read-only; job `task-mwzyl7q2-u78qa1`, no edits or network calls, verdict: **the NO-GO for physical deployment is justified**.

**Adopted corrections**
- `prepare-usb.sh` now generates a `START-HERE.txt` that starts with `--dry-run`, human approval, and only then install/STT — previously it opened with the install commands.
- Participant guide now uses the exact isolated Hermes executable with both isolated home variables, a function `participant()`, and a pinned skill revision instead of `main` and a bare `hermes`.
- Claims narrowed: emulated Whisper cause is "not established", preview media is a "directory stand-in", fallback status stays `PARTIAL`, and PT↔EN direction is stated explicitly.
- The lost `/tmp` evidence is recorded above; A3 (durable kit preservation) is now a prerequisite, not an optional improvement.

**Rejected / still open from Codex's blockers**
- A1 is not a prerequisite; A2 is not a required gate. Both need corrected acceptance criteria (exact exit status, both languages, real decoded segments, redacted evidence).
- Original A4 wrapper command rejected; use the x86-only rehearsal with exit status captured through `tee` and a `PASS x86_64 full` marker.
- A3's original `rsync`/`tar` and checksum sweep rejected (could archive credentials; `cd` into a file). Preserve a sanitized inventory with an allowlist instead.
- A5 must use the isolated binary and record only redacted effective values; raw recursive greps can print credential lines.
- T1/T2 gates must bind approval to an identified device and kit revision, require full translation/summary quality against fixed references, verify service ownership and post-reboot persistence, and use a Pi-specific run sheet.
- Cloudflare/OpenRouter stay disabled until cost/privacy approval precedes any live probe.
