#!/usr/bin/env python3
"""Remote Colab job: runs the public benchmark and creates a downloadable ZIP.

Executed via the official Google Colab CLI's 'colab exec -f' mechanism.
No credentials, local private files, or model-proposed commands are uploaded.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback
import zipfile

REPO_URL = "https://github.com/luandro/edge-llm-autoinstall.git"
WORKSPACE = Path("/content/edge-llm-autoinstall")
RESULTS = Path("/content/edge-llm-cli-results")
ARCHIVE = Path("/content/edge-llm-cli-results.zip")


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def gpu_preflight() -> str:
    if not shutil.which("nvidia-smi"):
        raise RuntimeError("Colab has no visible NVIDIA GPU. Check GPU entitlement/quota.")
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not gpu:
        raise RuntimeError("nvidia-smi reports no GPUs")
    if not shutil.which("nvcc"):
        raise RuntimeError("Colab GPU is present but the CUDA compiler nvcc is unavailable. "
                           "Current llama.cpp benchmark requires the CUDA Toolkit; do not fall back silently to CPU.")
    print("Remote NVIDIA GPU:", gpu, flush=True)
    return gpu


def dependencies() -> None:
    missing = [x for x in ("git", "cmake", "g++", "pkg-config") if not shutil.which(x)]
    libcurl_ok = (subprocess.run(["pkg-config", "--exists", "libcurl"]).returncode == 0) if "pkg-config" not in missing else False
    if not missing and libcurl_ok:
        return
    if not shutil.which("apt-get") or os.geteuid() != 0:
        raise RuntimeError("Missing build prerequisites (git/cmake/g++/pkg-config/libcurl). "
                           "Use a stock Colab image with apt root access.")
    print("Installing system build prerequisites ...", flush=True)
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    subprocess.run(["apt-get", "update", "-qq"], check=True, env=env)
    subprocess.run(["apt-get", "install", "-y", "-qq", "git", "cmake", "build-essential",
                    "pkg-config", "libcurl4-openssl-dev", "python3-venv"], check=True, env=env)


def checkout(commit: str) -> str:
    if not WORKSPACE.exists():
        run(["git", "clone", "--depth", "1", REPO_URL, str(WORKSPACE)])
    if commit:
        current = subprocess.run(["git", "rev-parse", "HEAD"], cwd=WORKSPACE,
                                 check=True, capture_output=True, text=True).stdout.strip()
        if current != commit:
            run(["git", "fetch", "--depth", "1", "origin", commit], cwd=WORKSPACE)
            run(["git", "checkout", "--detach", commit], cwd=WORKSPACE)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=WORKSPACE,
                          check=True, capture_output=True, text=True).stdout.strip()


def execute_benchmark(a: argparse.Namespace) -> int:
    command = [
        "bash", "benchmark.sh", "--backend", "cuda", "--require-gpu",
        "--models", a.models, "--suite", a.suite, "--runs", str(a.runs),
        "--context", str(a.context), "--max-download-gb", str(a.max_download_gb),
        "--output-dir", str(RESULTS), "--yes",
    ]
    if a.allow_large:
        command.append("--allow-large")
    if a.allow_hybrid:
        command.append("--allow-hybrid")
    print("Benchmark command:", " ".join(command), flush=True)
    log_path = RESULTS / "runner.log"
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(command, cwd=WORKSPACE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            log.write(line)
            log.flush()
            # Keep CLI terminal readable; full per-case detail remains in runner.log.
            if any(t in line for t in ("Hardware:", "Selected:", "Running ", "SKIP ",
                                       "Error ", "Reports saved:", "Compiling ", "Cloning ",
                                       "MODEL ", "ERROR", "Traceback", "Benchmark command")):
                print(line.rstrip(), flush=True)
            elif line.lstrip().startswith("[") and ("1/" in line or "3/" in line):
                print(line.rstrip(), flush=True)
        return proc.wait()


def package() -> None:
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for file in sorted(RESULTS.rglob("*")):
            if file.is_file():
                out.write(file, arcname=file.relative_to(RESULTS))
    print("REMOTE_RESULTS_ARCHIVE=" + str(ARCHIVE), flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--models", default="small")
    p.add_argument("--suite", choices=("quick", "full"), default="quick")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--context", type=int, default=4096)
    p.add_argument("--max-download-gb", type=float, default=16)
    p.add_argument("--allow-large", action="store_true")
    p.add_argument("--allow-hybrid", action="store_true")
    p.add_argument("--git-commit", default="")
    a = p.parse_args(argv)
    if a.git_commit and not re.fullmatch(r"[0-9a-f]{40}", a.git_commit):
        p.error("--git-commit must be a 40-character SHA")
    if a.runs < 1 or a.runs > 10 or a.context < 512 or a.context > 32768 or a.max_download_gb <= 0:
        p.error("Invalid repetition/context/download limit")
    RESULTS.mkdir(parents=True, exist_ok=True)
    manifest = {
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "args": vars(a),
        "status": "failed",
        "note": "Synthetic tool/translation/summary checks; not end-to-end Hermes tasks",
    }
    rc = 1
    try:
        manifest["gpu"] = gpu_preflight()
        dependencies()
        manifest["git_commit"] = checkout(a.git_commit)
        rc = execute_benchmark(a)
        manifest["status"] = "completed" if rc == 0 else "benchmark_failed"
        manifest["exit_code"] = rc
    except Exception as exc:
        manifest["error"] = str(exc)
        (RESULTS / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        print("Remote benchmark failed:", exc, file=sys.stderr, flush=True)
    finally:
        manifest["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        (RESULTS / "colab_run.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        package()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
