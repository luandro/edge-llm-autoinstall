# Workshop deployment readiness — feasibility-filtered action plan

Date: 2026-11-27. Evidence base: `WORKSHOP_READINESS.md` (Phase 3, commit `715babe`), `REPORT_PHASE_2.md`, `docs/WORKSHOP_USB.md`, `docs/HERMES_WORKSHOP.md`, `docs/PARTICIPANT_SETUP_PT.md`, `config/workshop-lean.yaml`. This plan lists **actions only**: no alternative models, no further prompt/Hermes optimization (explicit operator exclusion — see *Stop doing* 1–2). Standing honesty rule: laptop, directory-stand-in, container-fixture and QEMU results are **never** physical-target validation. Current decisions stand: x86-64 CONDITIONAL GO, ARM64 UNVERIFIED/NO-GO, physical target NO-GO, Cloudflare/OpenRouter UNVERIFIED-disabled.

Conventions — define before running anything (commands run from the repository root unless labelled operator/target):

```bash
KIT=/tmp/opencode/workshop/edge-llm-usb/edge-llm-usb   # verified Phase 3 directory stand-in kit (volatile /tmp)
EV="$HOME/edge-workshop-evidence"                       # operator: durable evidence dir (outside the repo)
mkdir -p "$EV"
```

## Feasible on this laptop now

### A1. Close the emulated-ARM64-STT gap with one bounded long-cap QEMU run (or reclassify it explicitly)

The rehearsal wrapper caps STT at 600 s (`scripts/usb-build/rehearse.py`) and a dedicated rerun already failed at 1,800 s; the gap is QEMU throughput, not a binary defect. Do not edit tracked scripts: run the kit's cross-built `whisper-cli` directly under QEMU with one explicit 5,400 s cap and capture everything.

Commands (laptop; read-only kit mount; no live service touched):

```bash
SYSROOT=/tmp/opencode/workshop/arm64-rootfs
test -x "$KIT/portable/aarch64/stt/whisper-cli" && test -f "$KIT/portable/aarch64/stt/ggml-base.bin" \
  && test -d "$SYSROOT" && command -v qemu-aarch64-static >/dev/null || { echo 'kit/sysroot/qemu missing'; exit 1; }
START=$SECONDS
timeout 5400 qemu-aarch64-static -L "$SYSROOT" \
  "$KIT/portable/aarch64/stt/whisper-cli" \
  -m "$KIT/portable/aarch64/stt/ggml-base.bin" \
  -f "$KIT/samples/sample-pt.wav" -l pt -t 4 >"$EV/arm-stt-qemu-pt.log" 2>&1
echo "exit=$? elapsed_s=$((SECONDS - START))" | tee -a "$EV/arm-stt-qemu-pt.log"
```

Repeat the same block with `-f "$KIT/samples/sample-en.wav" -l en` into `arm-stt-qemu-en.log`.

- **Evidence to record:** both logs, exit code, elapsed seconds, thread count; each log labelled "QEMU-emulated functional check — throughput is not target performance".
- **Acceptance criterion:** PASS branch — `grep -q '^exit=0' "$EV/arm-stt-qemu-pt.log"` and `grep -Eq '\] +[[:print:]]' "$EV/arm-stt-qemu-pt.log"` (a decoded segment exists). Reclassification branch — `grep -q '^exit=124'` on file and the readiness-table row is rewritten to "emulated STT unattainable on QEMU at ≤5,400 s; STT correctness deferred to target action T2".
- **Unlocks:** the ARM64 readiness row "emulated STT UNVERIFIED (QEMU timeout)" becomes a measured statement either way. Does **not** unlock ARM64 GO.
- **Main risk:** may still time out at 5,400 s (QEMU throughput); run plugged in; never quote elapsed time as a Pi 5 performance number.

### A2. Exercise `workshop-install.sh --dry-run` end-to-end in a fixture-CPU container

On this laptop the wrapper fails by design: it strips the fixture (`workshop-install.sh:21`), the i7-8650U is unsupported (`install.sh:114` real-detection branch), and port 8080 is occupied by the live facilitator. A container with fixture `/proc/cpuinfo` + `/proc/meminfo` and its own network namespace exercises the wrapper's real plumbing (USB selection, kit marker/portable checks, prerequisites, port check, dry-run exit) without touching live services or tracked files. The existing `edge-usb-rehearsal:amd64` image cannot be used (its runtime stage has no `systemctl`/`ss`), so build a one-off preview image.

Commands:

```bash
REV="$(cat "$KIT/.portable-complete")"
mkdir -p "$EV/build-ctx"
docker build -t edge-workshop-preview:amd64 -f- "$EV/build-ctx" <<'EOF'
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash coreutils systemd iproute2 curl sudo python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
EOF
printf 'model name\t: Intel(R) N95\n' > "$EV/cpuinfo.fixture"
printf 'MemTotal:       16000000 kB\n' > "$EV/meminfo.fixture"
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp \
  --mount "type=bind,source=$KIT,target=/kit,readonly" \
  --mount "type=bind,source=$EV/cpuinfo.fixture,target=/proc/cpuinfo,readonly" \
  --mount "type=bind,source=$EV/meminfo.fixture,target=/proc/meminfo,readonly" \
  --workdir "/kit/repo-$REV" edge-workshop-preview:amd64 \
  bash workshop-install.sh --usb /kit --dry-run \
  >"$EV/workshop-install-fixture-dryrun.log" 2>&1; echo "exit=$?"
```

- **Evidence to record:** the log plus the sentence "fixture CPU/RAM container — wrapper-plumbing evidence only, NOT hardware detection validation". The 8080 facilitator is never stopped; the container's own netns satisfies the port check.
- **Acceptance criterion:** recorded exit is `0`, and `grep -F 'Hardware:  nuc16' "$EV/workshop-install-fixture-dryrun.log"`, `grep -F 'Mode:      safe' …` and `grep -F 'portable/x86_64/llm/Qwen3.5-4B-Q4_K_M.gguf' …` all succeed.
- **Unlocks:** a new readiness checkbox "workshop-install.sh wrapper exercised end-to-end (fixture container)". x86-64 stays CONDITIONAL GO.
- **Main risk:** fixture output mistaken for hardware validation — keep the label in the log and the checklist entry. apt runs once during image build (network); the dry-run itself is `--network none`.

### A3. Preserve the kit, provenance and key-free config evidence before /tmp is lost

The kit and both isolated Hermes homes exist only under `/tmp/opencode/` (readiness report §15) and vanish on reboot. Copy the verified state to a durable operator location; never copy `.env`/key files.

Commands (operator — writes outside the repository):

```bash
DEST="$HOME/edge-workshop-kit-archive"
mkdir -p "$EV" "$DEST"
REV="$(cat "$KIT/.portable-complete")"
find "$KIT" -maxdepth 4 \( -name sources.lock -o -name base.lock -o -name models.lock \) -print \
  | xargs sha256sum >"$EV/kit-identity-$REV.txt"
sha256sum "$KIT/.portable-complete" >>"$EV/kit-identity-$REV.txt"
rsync -a "$KIT/" "$DEST/edge-llm-usb/"
tar -C "$KIT" -czf "$EV/kit-provenance-$REV.tar.gz" \
  .portable-complete .edge-llm-usb-v1 START-HERE.txt provenance samples hermes
sha256sum "$EV/kit-provenance-$REV.tar.gz" >"$EV/kit-provenance-$REV.tar.gz.sha256"
tar -C /tmp/opencode/participant-hermes --exclude='*.env' -czf \
  "$EV/participant-hermes-config-nokeys.tar.gz" config.yaml profiles 2>/dev/null
```

Verification:

```bash
test "$(cat "$DEST/edge-llm-usb/.portable-complete")" = "$(cat "$KIT/.portable-complete")" && echo MARKER-OK
(cd "$DEST/edge-llm-usb" && find . -name SHA256SUMS -print0 |
  xargs -0 -n1 sh -c 'cd "$1" && sha256sum --strict -c SHA256SUMS' _)
tar -tzf "$EV/participant-hermes-config-nokeys.tar.gz" | grep -Ec '(^|/)\.env$'              # must print 0
tar -xzOf "$EV/participant-hermes-config-nokeys.tar.gz" | grep -Ec 'GROQ_API_KEY=|sk-[A-Za-z0-9]{20}'  # must print 0
```

- **Evidence to record:** `kit-identity-*.txt`, tarball sha256, the `MARKER-OK` line, the full `sha256sum --strict -c` transcript over the archived copy.
- **Acceptance criterion:** every `sha256sum --strict -c SHA256SUMS` exits 0 under `$DEST/edge-llm-usb`, the marker matches, and both secret greps print `0`.
- **Unlocks:** preserves the evidentiary basis of every kit-dependent readiness row beyond this session; changes no status itself.
- **Main risk:** the `/tmp` kit is lost on reboot (do this first); a mistyped `--exclude` would archive a secret key — the two `grep -Ec` checks are the mandatory guard.

### A4. Capture one full rehearsal log and obtain a human quality verdict on all 10 synthetic outputs

The Phase 3 quality caveats (0.8B/2B "Friday at nine" mistranslation, gemma verbosity, approximate eSpeak STT) exist only in session output; no durable per-output verdict exists. This is a quality review deciding pass / disclose / block per output — **not** a model-selection exercise.

Commands:

```bash
docker image inspect edge-usb-rehearsal:amd64 >/dev/null || { echo 'rehearsal image missing'; exit 1; }
LOG="$EV/rehearsal-x86-full-$(date +%F).log"
bash scripts/rehearse-usb.sh --usb "$KIT" 2>&1 | tee "$LOG"
test "$(grep -c '"answer"' "$LOG")" -eq 8 && test "$(grep -c '"stt"' "$LOG")" -eq 2 && echo 10-OUTPUTS-OK
```

Then create `$EV/quality-review-sheet.md` with one row per fixed ID — `qwen08-pt-summary`, `qwen08-en2pt`, `qwen2b-pt-summary`, `qwen2b-en2pt`, `qwen4b-pt-summary`, `qwen4b-en2pt`, `gemma-pt-summary`, `gemma-en2pt`, `stt-pt`, `stt-en` — each with the source sentence, the pasted output from `$LOG`, and a line `VERDICT: pass|disclose|block` plus notes. The human reviewer fills it; the header must state "synthetic eSpeak samples only; no real or Indigenous-language audio evaluated".

- **Evidence to record:** the rehearsal log and the completed review sheet.
- **Acceptance criterion:** `test "$(grep -c '^VERDICT:' "$EV/quality-review-sheet.md")" -eq 10` and `test "$(grep -c '^VERDICT:[[:space:]]*$' "$EV/quality-review-sheet.md")" -eq 0`.
- **Unlocks:** turns the checked box "rehearsal outputs reviewed for quality" into a durable artifact; `disclose` verdicts flow into `docs/PARTICIPANT_SETUP_PT.md`, `block` verdicts create new scope for the operator.
- **Main risk:** reviewer unavailability; conclusions are limited to synthetic inputs and must never be presented as real-workshop quality.

### A5. Verify no auxiliary, fallback or paid route is active (read-only)

Commands:

```bash
HERMES_ISOLATED=/tmp/opencode/participant-hermes
PCFG="$HERMES_ISOLATED/profiles/participant/config.yaml"
test -f "$PCFG" || PCFG="$HERMES_ISOLATED/config.yaml"
grep -F 'fallback_providers: []' "$PCFG"                                            # expect: 1 hit
grep -Ein 'cloudflare|openrouter|workers|api\.cloudflare' "$PCFG"                   # expect: no output
grep -Ein 'WORKSHOP_CF_KEY|OPENROUTER_API_KEY' -r "$HERMES_ISOLATED/profiles" 2>/dev/null  # expect: no output
"$HERMES_ISOLATED/hermes-agent/.hermes/bin/hermes" -p participant config get fallback_providers  # expect: empty/[]
grep -Ein 'cloudflare|openrouter' config/workshop-lean.yaml                         # expect: no output
```

Re-confirm the live facilitator is untouched and loopback-only (read-only; never stop it):

```bash
curl --fail --silent http://127.0.0.1:8080/v1/models | grep -c lfm3-harbor-hermes   # expect: 1
ss -ltn | grep -F '127.0.0.1:8080'                                                  # loopback only
```

- **Evidence to record:** outputs into `$EV/no-fallback-route-check-$(date +%F).txt` with a date line.
- **Acceptance criterion:** the `fallback_providers: []` grep returns exactly one hit, all cloudflare/openrouter/key greps return nothing, the curl count is `1`, and `ss` shows `127.0.0.1:8080` only.
- **Unlocks:** keeps the "Cloudflare/OpenRouter UNVERIFIED (disabled)" and local-backup readiness rows honest at workshop time; re-run immediately before the workshop and after any config merge.
- **Main risk:** a later manual edit could add a fallback to the wrong profile; this check is the detector.

## Requires operator decision or credentials

### O1. Cloudflare Workers AI failover — needs token, account ID, cost and privacy check (operator only)

Operator commands (own shell; keys only in private environment, never printed):

```bash
# operator: export WORKSHOP_CF_KEY=... ; export CLOUDFLARE_ACCOUNT_ID=...
python3 scripts/cloud-probe.py cloudflare --yes
# operator: verify actual free allocation and zero charges in the Cloudflare dashboard; record the
# listed ZDR status of @cf/openai/gpt-oss-120b. Only after that: merge fallback_providers manually
# and run: hermes -p workshop fallback check
```

- **Evidence to record:** probe JSON (`tool_call_ok`, usage, rate-limit headers), dashboard note of free allocation, ZDR citation, and a dated enable/disable decision line.
- **Acceptance criterion:** probe output contains `tool_call_ok: true` and the dated decision line exists in `$EV/operator-decisions.md`; otherwise the route stays disabled.
- **Unlocks:** readiness checkbox "[ ] Cloudflare failover validated with operator credentials (deferred)".
- **Main risk:** accidental paid usage or privacy exposure — synthetic probe data only; availability alone is not a test.

### O2. OpenRouter second backup — verified `:free` tool-capable model with ZDR + deny-training, or keep disabled (operator only)

```bash
# operator: export OPENROUTER_API_KEY=...   (only after account-level ZDR / deny-training verification)
python3 scripts/cloud-probe.py openrouter --model VERIFIED_MODEL:free --yes
```

- **Evidence to record:** probe `tool_call_ok`, the verified model id, and the zero-price/ZDR/deny-training verification note.
- **Acceptance criterion:** `tool_call_ok: true` with the privacy note on file; if any check fails, the recorded decision is "disabled" (the default).
- **Unlocks:** the OpenRouter row of the failover table; no route is enabled on availability alone.
- **Main risk:** relaxing privacy to make the test pass is prohibited; random or paid routing stays forbidden.

### O3. Groq posture — re-attest ZDR and accept the documented reasoning-effort cost (operator decision)

- **Commands (operator, console + editor):** (a) re-verify in the Groq console that Zero Data Retention is enabled for the workshop account; write a dated line to `$EV/operator-decisions.md`. (b) Record acceptance of the known cost: `reasoning_effort: low` via the custom provider triggers one rejected request plus retry per session (Hermes maps it to `default`; Groq accepts only low/medium/high) — the shared install is not patched for the workshop.
- **Evidence to record:** `$EV/operator-decisions.md` lines "ZDR re-attested <date>" and "reasoning-effort extra request: ACCEPTED".
- **Acceptance criterion:** `grep -c 'ZDR re-attested' "$EV/operator-decisions.md"` ≥ 1 and the ACCEPTED line exists.
- **Unlocks:** closes Phase 2 blocker 3 as an accepted cost; keeps the 413/429 recovery procedures authoritative.
- **Main risk:** the attestation remains operator-attested only, not independently auditable.

### O4. Provide physical media, a reviewer and evidence-class approvals (operator resource decisions)

- **O4a — real USB media.** Provide a ≥64 GB (128 GB recommended) USB SSD, ext4 or exFAT (never FAT32), and approve writing the verified kit onto it. Operator commands:

```bash
# operator: mount the USB at /media/$USER/WORKSHOP (no formatting by scripts)
DEST="$HOME/edge-workshop-kit-archive"   # produced by A3
rsync -a "$DEST/edge-llm-usb/" /media/$USER/WORKSHOP/edge-llm-usb/
(cd /media/$USER/WORKSHOP/edge-llm-usb && find . -name SHA256SUMS -print0 |
  xargs -0 -n1 sh -c 'cd "$1" && sha256sum --strict -c SHA256SUMS' _)
EDGE_LLM_TEST_PROFILE=pi4 bash install.sh --offline \
  --usb /media/$USER/WORKSHOP/edge-llm-usb --mode safe --dry-run
```

  - **Evidence to record:** strict-checksum transcript on the mounted device and the dry-run output showing a detected `portable/x86_64/…` bundle and `Hardware:  pi4` (the test-profile override is dry-run-only by design, `install.sh:114`).
  - **Acceptance criterion:** all manifests verify on the mounted device and the dry-run exits 0 with a `Hardware:` line.
  - **Unlocks:** upgrades the readiness row "USB detection + install preview" from directory stand-in to physical media. Still **not** a target test.
  - **Main risk:** FAT32 media breaks the kit layout; the pi4 detection is fixture-based and stays labelled as such.

- **O4b — reviewer assignment** for A4. **O4c — approval that A1/A2 evidence classes** (one long-cap QEMU run; fixture-CPU container preview) are acceptable record-keeping. **Acceptance criterion:** one dated line each in `$EV/operator-decisions.md`.

## Requires physical target

No laptop, container-fixture, directory-stand-in or QEMU result counts toward this section. Each target run starts from the A3-archived kit written to real media (O4a), runs in the target's own terminal, and archives its artifacts under `$EV/target-<device>/`.

### T1. x86-64 real-target evidence set (Intel N95/N97 16 GB, or K11) — exact evidence to capture

Target commands (`USB=/media/<user>/WORKSHOP/edge-llm-usb`, from the kit checkout `repo-$REV`):

1. Hardware facts: `uname -m; grep -im1 "^model name" /proc/cpuinfo; awk "/^MemTotal:/{print \$2}" /proc/meminfo; getconf GNU_LIBC_VERSION; grep -E "^(ID|VERSION_ID)=" /etc/os-release; df -h /` — record all (glibc ≥ 2.36 required).
2. Kit identity on target: `cat "$USB/.portable-complete"` and the same `find … sha256sum --strict -c` sweep as A3 — every manifest must verify on the target.
3. Real detection preview: `bash workshop-install.sh --usb "$USB" --dry-run` — no fixture env; must exit 0 with `Hardware:` showing the real CPU (nuc16/k11).
4. Human-approved install: `bash workshop-install.sh --usb "$USB"` (interactive `sudo -v` by the human) — record exit 0 and the log path `~/.local/state/edge-workshop/install.*.log`.
5. Service and locality: `systemctl is-active edge-llm` → `active`; `curl --fail --silent http://127.0.0.1:8080/v1/models` → 200; `ss -ltn | grep 8080` → `127.0.0.1:8080` only; save `journalctl -u edge-llm -n 120`.
6. WAN-disabled inference: disconnect ethernet/Wi-Fi, then `python3 scripts/edge-task.py pt 'The meeting is on Friday at nine.'` — output must contain `sexta-feira` **and** `nove`; `python3 scripts/edge-task.py summary --file news.txt` must be non-empty; record wall time.
7. STT: `~/.local/bin/edge-transcribe -l pt -f "$USB/samples/sample-pt.wav"` and `-l en …sample-en.wav` — record transcript text and elapsed seconds (real RTF).
8. Independence and persistence: copy logs off the device, unplug the USB, rerun step 6; reboot, `systemctl is-active edge-llm` → `active` again.

- **Evidence to record:** all eight steps' outputs and logs under `$EV/target-n95/` (or `target-k11/`).
- **Acceptance criterion:** steps 1–8 all recorded; step 3 and step 4 exit 0; `grep -q sexta-feira` and `grep -q nove` succeed on step 6 output; `ss` shows loopback-only; both transcripts non-empty; post-reboot service active.
- **Unlocks:** readiness checkbox "[ ] Physical target install + service + inference" for that device class and moves x86-64 **CONDITIONAL GO → GO** for that class; without it CONDITIONAL GO stands.
- **Main risk:** unknown target OS (glibc < 2.36 fails closed by design); any failure is diagnosed from the saved log — never a blind retry of a side-effectful step.

### T2. ARM64 real-target evidence set (Raspberry Pi 5) — decides the current UNVERIFIED/NO-GO

Target commands: run the same eight steps as T1 on a Pi 5 using the kit's `portable/aarch64/` bundles, plus these ARM64-specific captures:

- Native (no QEMU) binary identity: `"$USB/portable/aarch64/llm/Qwen3.5-0.8B-Q4_K_M.gguf/llama-server" --version` must print the aarch64 build without any `qemu-aarch64-static` involvement, and `file` on both cross-built binaries must say `ARM aarch64`.
- Real Whisper timing — the item QEMU could not close: record elapsed seconds for both `-l pt` and `-l en` runs; this replaces the emulated number as the only citable performance datum.
- Memory/thermal: `free -h` before/after inference and `vcgencmd measure_temp` during it; on a Pi 4 GB the LLM service is stopped and restarted only with explicit human approval (per `docs/PARTICIPANT_SETUP_PT.md`).
- Which safe bundle was installed for the board's RAM (`pi4`/`pi8`/`pi16`) — record the profile line.

- **Evidence to record:** the T1 artifact set executed natively, plus the four ARM64-specific captures above, under `$EV/target-pi5/`.
- **Acceptance criterion:** the full T1 acceptance set passes natively on the Pi, `file` reports `ARM aarch64` for both binaries, and both STT runs complete with recorded elapsed time.
- **Unlocks:** moves ARM64 **UNVERIFIED/NO-GO → GO for Pi 5** only; any failure keeps NO-GO and the evidence defines the defect.
- **Main risk:** the cross-built Armv8-A binaries have never executed natively — a native-only failure (illegal instruction, runtime, timing) is exactly what this test exists to expose; A1's outcome must be on file so emulated vs real STT is interpretable.

## Stop doing

1. **No further model swapping.** Trying other GGUFs, LoRAs or provider-side models is excluded by operator decision; the benchmark tables in `README.md`/`docs/AGENT_MODELS.md` are reference data, not a work queue.
2. **No further Hermes prompt or skill-size optimization.** The terminal-only path already measures PASS (1 tool call, 2 model requests, 7,433 cumulative input tokens); skill-enabled mode exceeding the 8,000-token ceiling is a documented non-workshop path, not a target to fix.
3. Do not re-run ARM STT emulation at 600/1,800 s caps expecting a different result — use A1's single bounded 5,400 s run or record the reclassification.
4. Do not retry `docker run --platform linux/arm64` or register host binfmt/QEMU for rootless Docker on this host (the daemon mount namespace does not see host binfmt). Approved ARM paths: cross-build + QEMU checks (A1) and the real target (T2).
5. Do not re-run `workshop-install.sh --dry-run` directly on this laptop expecting success — the wrapper strips the fixture by design and the CPU is unsupported. Use A2 (fixture container) or T1 (real target).
6. Do not stop, restart or reconfigure the live facilitator on `127.0.0.1:8080` or the `coder` gateway; they are read-only dependencies.
7. Do not enable Cloudflare, OpenRouter or any paid/untested route before O1/O2 complete; `fallback_providers` stays `[]`.
8. Do not present directory-stand-in, container-fixture or QEMU results as physical-target validation, and do not build further stand-ins as substitutes for hardware.
9. Do not commit, push or archive secret values; never print keys (A3's exclusion plus the two secret greps are mandatory).
10. Do not use `--yes` for real installs without the operator's explicit prior authorization; preview → approve → install remains the invariant.

## How each action changes the readiness decision

| Action | Readiness item / decision touched | Movement on completion |
|---|---|---|
| A1 | ARM64 row "emulated STT UNVERIFIED (QEMU timeout)" | Becomes a measured functional PASS (emulated) or an explicit "unattainable ≤5,400 s; deferred to T2". ARM64 stays UNVERIFIED/NO-GO either way. |
| A2 | New checkbox: wrapper exercised end-to-end (fixture container) | Adds a checked plumbing item; x86-64 stays CONDITIONAL GO. |
| A3 | Evidentiary basis of all kit-dependent rows | No status change; prevents silent loss of evidence after a `/tmp` reset. |
| A4 | Checked box "rehearsal outputs reviewed for quality" | Durable verdict artifact; `disclose` items flow into participant instructions; `block` items create new operator scope. No GO change by itself. |
| A5 | Failover row + local-backup row | Confirms "disabled, not silently enabled" at workshop time. |
| O1 / O2 | "[ ] Cloudflare failover validated (deferred)"; OpenRouter row | Checked only after probe `tool_call_ok: true` plus privacy/cost evidence; otherwise stays disabled/UNVERIFIED. |
| O3 | Privacy caveat; Phase 2 blocker 3 | Closed as an accepted, documented cost. |
| O4a | "USB detection + install preview (directory stand-in)" row | Upgrades to physical media; still not a target validation. |
| T1 | "[ ] Physical target install + service + inference"; x86-64 CONDITIONAL GO | GO for the tested N95/N97/K11 class once the full evidence set passes on that real device. |
| T2 | ARM64 UNVERIFIED / NO-GO for workshop | GO for Pi 5 only after native execution plus real STT timing evidence. |

Standing rule: nothing outside `## Requires physical target` may flip "Physical target deployment: NO-GO"; A1/A2 close laptop-side gaps as explicitly-labelled evidence, they do not validate hardware.

## Senior review notes (added after GLM-5.3-flash delegation)

- The plan was produced through the bundled `senior-engineer-delegation` runner; model provenance reported exactly `glm-5.3-flash` (the skill text mentions 5.4, the installed launcher pins 5.3-flash). Runner integrity checks passed, no destructive action was requested, and only this file was added.
- **A4 command correction:** `bash scripts/rehearse-usb.sh --usb "$KIT"` inspects both `edge-usb-rehearsal:amd64` and `edge-usb-rehearsal:arm64`. The ARM64 Docker image could not be built here (rootless Docker binfmt gap), so that command will fail. Use the Phase 3 direct x86-only rehearsal instead:
  ```bash
  REV="$(cat "$KIT/.portable-complete")"
  LOG="$EV/rehearsal-x86-full-$(date +%F).log"
  docker run --rm --pull never --platform linux/amd64 --network none \
    --mount "type=bind,source=$KIT,target=/kit,readonly" \
    --mount "type=bind,source=$PWD,target=/repo,readonly" \
    edge-usb-rehearsal:amd64 python3 /repo/scripts/usb-build/rehearse.py x86_64 full \
    2>&1 | tee "$LOG"
  ```
  The `8 "answer"` + `2 "stt"` acceptance check still applies.
- **A1 cost note:** a single 5,400 s QEMU run is a deliberate, bounded experiment; it needs an operator decision on compute time before being started, and a 124 exit must be recorded as "unattainable under QEMU", never as a Pi result.
- **A2 feasibility note:** bind-mounting fixture `/proc/cpuinfo` and `/proc/meminfo` may be rejected by rootless Docker; if so, record it as a failed plumbing attempt and use T1 on the real target rather than relaxing the isolation.
