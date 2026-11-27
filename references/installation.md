# Installation procedure

Read this only when actually installing or preparing an install. Keep the operator in control: preview, approval, then one installation. Never use `--yes` without explicit prior authorization.

## 1. Establish the target and read-only inspection

Use Hermes' terminal (locally or through an authorized SSH tunnel/VPN). Do not confuse the Hermes controller's hardware with the remote **target**. Confirm which host will be changed. Ask only for genuinely missing access/permission information.

Run on the target (one bounded terminal call where possible):

```bash
uname -sm
cat /proc/device-tree/model 2>/dev/null || true
lscpu | grep -E 'Model name|Architecture|CPU\(s\)|Thread|Core' || true
free -h
lsblk -o NAME,SIZE,TYPE,TRAN,FSTYPE,MOUNTPOINTS
df -h "$HOME"
command -v systemctl && command -v sudo
```

For Pi: `vcgencmd get_throttled` and `vcgencmd measure_temp` if available. For K11: `vulkaninfo --summary`, `cat /sys/class/drm/card*/device/mem_info_gtt_total 2>/dev/null`, and `sudo dmidecode -t memory` **only with permission** to check channel population, configured DDR speed and GTT. Note actual RAM, storage medium, kernel/Mesa versions, CPU governor, temperature and free disk. Do not infer dual-channel from total GB alone.

Require Linux, systemd, sufficient writable storage, initial internet access for online installation OR a matching prepared USB, and ability to run authorized sudo. Use Raspberry Pi OS **64-bit** and active cooling on Pi. A remote target must be reachable through an authorized SSH tunnel/VPN, never a public unauthenticated API.

## 2. Choose a safe starting point

| Target | Safer starting model (`--mode safe`) | Highest-capability *experimental/opt-in* (`--mode best`) |
| --- | --- | --- |
| Pi 5, 4 GB | Qwen3.5 0.8B Q4, 4K context | Qwen3.5 2B Q4, 2K context (tight memory) |
| Pi 5, 8 GB | Qwen3.5 2B Q4, 4K context | Qwen3 30B-A3B Q3 via `ik_llama`, SSD-backed, 2K context |
| Pi 5, 16 GB | Qwen3.5 4B Q4, 4K context | Qwen3.6 35B-A3B CPU-3, 1K context, very tight fit |
| Intel N95/N97, 16 GB | Qwen3.5 4B Q4, 4K context | Qwen3.6 35B-A3B CPU-2, 4K context, often slow |
| GMKtec K11, 32 GB | Gemma 4 E4B Q4, 8K context, Vulkan if RADV works | Gemma 4 26B-A4B Q4, 8K context, ~22 GiB GPU-addressable GTT |

**Default to safe for first deployment**, especially on headless nodes. `--mode auto` is not uniformly safe (selects **best** on Pi 16 GB, N95/N97, and Pi 8 GB with detected SSD). Pi 4 GB and K11 select safe automatically. Large profiles are opt-in experiments, never guaranteed fast installs. See `references/models.md` for optional agent models and K11 choices.

## 3. Review, preview, approve once, install

```bash
git clone --depth=1 https://github.com/luandro/edge-llm-autoinstall.git
cd edge-llm-autoinstall
bash -n install.sh
bash tests/smoke.sh
bash install.sh --mode safe --dry-run
```

If the checkout already exists: inspect `git status --short`; do not overwrite local changes. Update with `git pull --ff-only` only when clean and after reviewing what changed.

Review `install.sh` from the trusted source before running it with sudo. Show the operator the detected profile, chosen model, download size, target model directory, memory/disk constraints, potential service changes and missing requirements. Preserve any existing service configuration before replacing it (requires approval). Get **one** approval for installation/package downloads and systemd changes. **Never use `--yes` without prior explicit authorization for unattended deployment.**

```bash
bash install.sh --mode safe
# After a successful safe baseline, only if requested and resources permit:
bash install.sh --mode best
# K11 choices:
bash install.sh --model qwen36 --backend auto
bash install.sh --model inkling --gpu-layers 16
```

`--model-dir /absolute/path` directs weights to a mounted disk. For Pi 8 GB `--mode best`, first ensure SSD/NVMe with >=13 GB free and verify weights live there; microSD paging is not equivalent. On Pi 4 GB use `--mode safe` first, keep other services small, do not raise context above the installer's 4K cap. Online installation compiles and downloads; USB installation copies verified prebuilt artifacts. Both create a persistent local-only `edge-llm.service`. Do **not** call an install complete until the service and a real inference request work.

## USB-first workshop procedure (prefer when media is available)

Read `docs/WORKSHOP_USB.md` in a full checkout. On the target, inspect mounted disks with `lsblk -o NAME,SIZE,TRAN,FSTYPE,MOUNTPOINTS`. Use the committed `repo-*` checkout inside `edge-llm-usb`, not git clone/pull. **Never format or mount arbitrary devices.** Preview `bash install.sh --offline --usb /actual/mount --mode safe --dry-run`; request approval before executing without `--dry-run`. USB v2 is prepared entirely on the facilitator laptop, contains ARM64 and x86-64 safe CPU bundles, requires glibc >=2.36, and never falls back online; missing, corrupt or incompatible bundles must stop. Legacy v1 supported. Install local Whisper CLI with `bash install-stt.sh --usb /actual/mount` if bundled. Test `~/.local/bin/edge-transcribe -l pt -f sample.wav` with an authorized 16 kHz mono PCM WAV. Avoid concurrent LLM/STT on 4 GB Pi; ask before stopping/restarting services.

For the bounded participant flow prefer `bash workshop-install.sh --usb /actual/mount --dry-run` as **one** task, then the same command without `--dry-run` after human approval (human terminal for sudo). Return only exit code and concise status; do not automatically retry a mutation after failure. Existing service backups are local; there is no automatic rollback. Use individual installers for recovery.

## Safety invariants while installing

- Never send confidential files, credentials, raw transcripts or secret shell output to any cloud provider.
- No keys in USB media or repository; no shared credentials or account rotation to evade quotas.
- Never publish an unauthenticated listener on the internet; local API stays on `127.0.0.1`.
- Never automatically adjust kernel/swap settings, BIOS, modprobe or GTT/TTM.
- Do not use the dry-run-only `EDGE_LLM_TEST_PROFILE` to spoof production hardware.
