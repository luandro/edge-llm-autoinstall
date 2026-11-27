# Pitfalls, recovery and report back

## Pitfalls and recovery

- **OOM / service crash:** inspect `journalctl -u edge-llm`, `free -h`, `dmesg` (permission permitting) and `df -h`. Reduce context / choose safe; on K11 reduce GPU layers or use `--backend cpu`. If changing models failed, reinstall the known-good safe profile — the installer has **no automatic rollback**.
- **GPU Vulkan failure:** ensure Mesa RADV, working `/dev/dri` permissions and GTT headroom; never force ROCm or kernel tuning past a failed safety check.
- **Wrong hardware profile / unsupported system:** stop and report diagnostics; do not spoof production hardware through the dry-run-only `EDGE_LLM_TEST_PROFILE` variable.
- **Service started but chat fails:** wait for model load; check `/v1/models`, run an actual completion, review logs and file sizes. A nonempty downloaded file is not proof of integrity; verify before retrying a suspected truncated download.
- **Remote agent:** local-only means the API is reachable from the target's own loopback. Use an SSH tunnel/private VPN for Hermes access; never publish an unauthenticated listener on the internet.
- **429 / quota:** respect `Retry-After` and reset windows; wait or switch to an approved backup. Never blindly retry a side-effectful command (install, download, service change) after a timeout — inspect logs and status first. No parallel requests per account.

## Lab transfer and hardware readiness

Read `docs/LOCAL_HERMES_TRANSFER.md` in a full checkout before experimenting with LFM3, Laya or ARM backends. Transfer findings with evidence status; do not promote ThinkPad or third-party Pi measurements as defaults. Keep Pi 4 GB context caps and safe defaults; a 2K–4K standalone model test is not a full Hermes test. Never automatically adjust kernel/swap settings or load multiple neural models on 4 GB.

## Verification / report back

Return a concise result with: target identifier (no secrets), detected hardware, RAM/channel and storage, OS, chosen model + quantization, safe/best choice, backend, threads/context/microbatch, service status, loopback API URL, one successful chat response, measured throughput and temperature, manual overrides, and outstanding STT/NMT tasks. Mark missing hardware tests **unverified** and leave a clear safe fallback. Keep logs/transcripts on the target unless the operator explicitly authorizes sharing.

Workshop direct fallback: `python3 scripts/edge-task.py health`, `summary --file PATH`, `pt TEXT` or `en TEXT` on the target. This needs neither Hermes nor internet — only loopback. Report incompatibilities; never silently fall back online.

For a Hermes workshop rehearsal also record, per task and per trial: actual input/output/reasoning tokens, model request count, tool-call count and arguments, wall-clock time, rate-limit errors and task correctness. Do not declare readiness until a real Hermes session completes the bounded workshop tasks successfully.
