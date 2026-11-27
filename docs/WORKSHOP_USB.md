# Belém workshop: build everything on one laptop

No Raspberry Pi, NUC or K11 is available beforehand. Use a Linux laptop, Docker/buildx, git, curl, Python 3 and a mounted 128 GB USB SSD (ext4 preferred, exFAT supported, no FAT32). The laptop may have little free space: downloads and output cache live on USB, but Docker build cache is separate. Inspect actual Docker storage and free space; do not automatically prune unrelated images, install privileged binfmt or format media. Use Docker's documented QEMU/binfmt setup with approval if ARM emulation is missing. The build can be slow; both architectures are mandatory.

```bash
git clone https://github.com/luandro/edge-llm-autoinstall.git
cd edge-llm-autoinstall
bash prepare-usb.sh --dry-run
bash prepare-usb.sh --usb /media/$USER/WORKSHOP
bash scripts/rehearse-usb.sh --usb /media/$USER/WORKSHOP
# optional emulated real ARM inference:
bash scripts/rehearse-usb.sh --usb /media/$USER/WORKSHOP --full-arm
```

Builder resolves and locks upstream llama/whisper commits, Debian Bookworm multiarch image digest and model revisions; compiles portable CPU binaries for amd64 and arm64; caches all four safe GGUF files and multilingual Whisper base; copies checksummed per-architecture bundles, committed repo snapshot, synthetic PT/EN WAVs, reference text, licenses for executables, build info and reviewed Hermes installer snapshot (Hermes dependencies still online). It does not require any supported hardware on the preparation host. Re-run to resume; remove a corrupt or obsolete cache deliberately after verifying why. Source versions frozen per kit; apt dependency versions may vary. Do not use untrusted USB; SHA256 detects corruption, not adversarial replacement. No secrets.

Target baseline: Linux 64-bit + systemd, glibc >=2.36 (Debian 12/Bookworm or newer, Raspberry Pi OS 64-bit Bookworm or newer, Ubuntu 24.04+), Bash, coreutils, sudo, curl and Python 3 for benchmarks. No GPU or compiler needed on target; portable build CPU only, laptop-native optimizations deliberately disabled. Pi/NUC/K11 actual OS unknown: confirm with organizers if possible, prepare verified official recovery images separately if needed (do not flash any device automatically). USB is not a bootable OS image or universal Linux runtime. No dedicated NMT, GUI, audio conversion endpoint, or complete offline Hermes bootstrap. If target OS or CPU incompatible, stop; use compatible baseline or another machine. Existing v1 per-hardware media still supported; portable v2 takes precedence only when complete.

## At workshop (Portuguese quick start)

1. Conecte o USB e abra a pasta repo-COMMIT indicada em START-HERE.txt.
2. Rode `bash install.sh --offline --mode safe --dry-run`. Confirme o computador e modelo.
3. Com autorização, rode `bash install.sh --offline --mode safe`. Se necessário indique `--usb /ponto/de/montagem`.
4. Rode `bash install-stt.sh` para Whisper local.
5. Verifique `systemctl is-active edge-llm`, `curl --fail http://127.0.0.1:8080/v1/models` e uma resposta real. Compare tradução/resumo via `bash benchmark.sh --server-url http://127.0.0.1:8080 --suite quick --runs 1`.
6. Transcreva `~/.local/bin/edge-transcribe -l pt -f /caminho/sample-pt.wav`. No Pi 4GB, pare o serviço LLM com autorização antes de usar Whisper, reinicie depois. Teste também inglês. Amostras sintetizadas não avaliam sotaques, línguas indígenas ou entrevistas reais.
7. Desconecte a internet, mantenha LAN, repita testes. O USB pode ser removido após copiar arquivos. Não exponha API sem autenticação; use túnel SSH autorizado.

First exercise Hermes: [lean provider setup, quota mitigation, task cards and fallback](HERMES_WORKSHOP.md). WAN needed while cloud-backed Hermes operates; direct local scripts are the backup. No automatic online fallback after USB selection. For explicit online install use --online.

## Rehearsal and target gate
Laptop rehearsal verifies SHA256, correct binary execution and actual x86 safe-model text completions/Whisper STT under Docker --network none, read-only USB, no host model cache. ARM version/help under QEMU by default, optional small-model and Whisper inference. Logs must be reviewed manually; synthetic tests do not measure actual quality. Use separate VM with systemd for service activation if feasible. Run all repo CI and unit tests, test corrupt/missing bundles, path spaces and recovery; do not claim physical performance. See [laptop agent handoff](WORKSHOP_LAPTOP_REHEARSAL_PROMPT.md). Record pass/fail/not-run and duplicate USB backup. On arrival: confirm RAM/arch/OS/disk/refrigeration, test each physical machine with WAN disabled, real chat/transcription, unplug USB and reboot; measure latency/RAM/thermal and human quality. No claim of target readiness until actual tests pass.
