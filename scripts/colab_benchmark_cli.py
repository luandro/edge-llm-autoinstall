#!/usr/bin/env python3
"""One-command orchestration of the official Google Colab CLI benchmark runner.

Public synthetic fixtures only. No secret files or model-suggested commands are sent/executed.
No Colab allocation is performed in --dry-run mode.
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
import zipfile

ROOT = Path(__file__).resolve().parent.parent
WORKER = ROOT / "scripts" / "colab_benchmark_job.py"
CATALOG = json.loads((ROOT / "scripts" / "model_catalog.json").read_text(encoding="utf-8"))["models"]
GROUPS = ("small", "edge", "adapter", "large", "all")
GPUS = ("T4", "L4", "G4", "A100", "H100")
ARCHIVE = "/content/edge-llm-cli-results.zip"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run edge-llm GGUF benchmarks automatically on Google Colab via Google's official CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--models", default="small", help="small, edge, adapter, large, all or comma-separated model IDs")
    p.add_argument("--suite", choices=("quick", "full"), default="quick")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--gpu", choices=GPUS, default="T4")
    p.add_argument("--context", type=int, default=4096)
    p.add_argument("--max-download-gb", type=float, default=16)
    p.add_argument("--allow-large", action="store_true")
    p.add_argument("--allow-hybrid", action="store_true", help="Permit slow CPU/GPU shared offload")
    p.add_argument("--high-mem", action="store_true", help="Request more RAM; requires appropriate Colab entitlement")
    p.add_argument("--auth", choices=("oauth2", "adc"), default="oauth2")
    p.add_argument("--session", help="Optional unique Colab runtime name")
    p.add_argument("--results-dir", default=str(ROOT / "reports" / "colab"))
    p.add_argument("--yes", action="store_true", help="Approve VM provisioning and possible compute-unit charges")
    p.add_argument("--dry-run", action="store_true", help="Print all steps without installing CLI or provisioning GPU")
    p.add_argument("--leave-running", action="store_true", help="Do not stop the Colab runtime after results retrieval")
    a = p.parse_args(argv)
    if not (1 <= a.runs <= 10 and 512 <= a.context <= 32768 and a.max_download_gb > 0):
        p.error("Invalid runs, context or max download limit")
    if a.session and not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,45}", a.session):
        p.error("--session must be 1-46 characters, beginning with a letter")
    return a


def model_ids(spec: str) -> list[str]:
    chosen = []
    for key in (t.strip() for t in spec.split(",")):
        if not key:
            raise ValueError("Empty model name")
        if key == "all":
            names = list(CATALOG)
        elif key in GROUPS:
            names = [n for n, d in CATALOG.items() if key in d["groups"]]
        elif key in CATALOG:
            names = [key]
        else:
            raise ValueError(f"Unknown model/group {key!r}. Valid: {', '.join(GROUPS)} / {', '.join(CATALOG)}")
        for name in names:
            if name not in chosen:
                chosen.append(name)
    return chosen


def planned_gb(models: list[str]) -> float:
    unique = set()
    size = 0.0
    for name in models:
        model = CATALOG[name]
        for repo, filename, gb in (
            [(model["repo"], model["file"], model["size_gb"])]
            + ([(model["adapter_repo"], model["adapter_file"], model.get("adapter_gb", 0))]
               if model.get("adapter_file") else [])
        ):
            if (repo, filename) not in unique:
                unique.add((repo, filename))
                size += float(gb)
    return round(size, 2)


def find_colab() -> str | None:
    found = shutil.which("colab")
    if found:
        return found
    local = ROOT / ".venv-colab-cli" / "bin" / "colab"
    if local.is_file():
        return str(local)
    for candidate in (Path.home() / ".local" / "bin" / "colab",):
        if candidate.is_file():
            return str(candidate)
    return None


def install_colab_cli() -> str:
    found = find_colab()
    if found:
        return found
    print("\nOfficial Colab CLI not found; installing locally (no sudo).", flush=True)
    if shutil.which("uv"):
        subprocess.run(["uv", "tool", "install", "google-colab-cli"], check=True)
        found = find_colab()
        if found:
            return found
    python = shutil.which("python3.12") or (sys.executable if sys.version_info >= (3, 12) else None)
    if not python:
        raise RuntimeError(
            "Official google-colab-cli needs Python 3.12+. Install 'uv' and run "
            "'uv tool install google-colab-cli', or install Python 3.12."
        )
    env = ROOT / ".venv-colab-cli"
    subprocess.run([python, "-m", "venv", str(env)], check=True)
    subprocess.run([str(env / "bin" / "python"), "-m", "pip", "install", "--upgrade", "google-colab-cli"], check=True)
    found = find_colab()
    if not found:
        raise RuntimeError("Colab CLI installation succeeded but colab executable was not found")
    return found


def git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                            capture_output=True, check=False)
    sha = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("Run from a Git checkout of edge-llm-autoinstall (need a committed revision).")
    diff = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True,
                          capture_output=True, check=False).stdout.strip()
    if diff:
        print("Note: local uncommitted changes are not uploaded; remote job checks out commit", sha[:12])
    return sha


def invoke(args: list[str], *, quiet_failure: bool = False) -> int:
    print("+", " ".join(args), flush=True)
    rc = subprocess.run(args, check=False).returncode
    if rc and not quiet_failure:
        print(f"Command returned {rc}", file=sys.stderr, flush=True)
    return rc


def retrieve(colab: list[str], session: str, directory: Path) -> Path | None:
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / f"{session}.zip"
    if invoke([*colab, "download", "-s", session, ARCHIVE, str(archive)], quiet_failure=True):
        print("Results archive not available (remote startup/build may have failed).", file=sys.stderr)
        return None
    target = directory / session
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            output = (target / member.filename).resolve()
            if not output.is_relative_to(target.resolve()):
                raise RuntimeError("Unsafe ZIP member path")
        z.extractall(target)
    print(f"\nDownloaded: {archive}\nExtracted:  {target}", flush=True)
    summary = target / "comparison.md"
    if summary.exists():
        print("\n" + summary.read_text(encoding="utf-8")[:6000], flush=True)
    else:
        print("No comparison.md in archive; inspect error.txt and colab_run.json", file=sys.stderr)
    return archive


def main(argv: list[str] | None = None) -> int:
    a = parse_args(argv)
    selected = model_ids(a.models)
    total = planned_gb(selected)
    if total > a.max_download_gb:
        raise SystemExit(f"Selected weights total ~{total} GB > {a.max_download_gb} GB limit. "
                         "Select fewer models or increase --max-download-gb explicitly.")
    if any(CATALOG[n]["size_gb"] > 8 for n in selected) and not a.allow_large:
        raise SystemExit("Large models require --allow-large. Do not use them on a free T4.")
    session = a.session or ("edgebench-" + dt.datetime.now(dt.timezone.utc).strftime("%y%m%d-%H%M%S")
                            + "-" + str(os.getpid()))
    print(f"Colab: {a.gpu} GPU | models: {', '.join(selected)} | {a.suite} x{a.runs} | "
          f"~{total} GB weights | session: {session}")
    if a.dry_run:
        print("DRY RUN: check/install official google-colab-cli, authenticate, allocate GPU, "
              "run scripts/colab_benchmark_job.py, download ZIP, stop session.")
        return 0
    if not a.yes:
        if not sys.stdin.isatty():
            raise SystemExit("Noninteractive mode: pass --yes after explicit approval of GPU allocation.")
        print("Colab may charge compute units or enforce quota; accelerator allocation is not guaranteed.")
        answer = input("Provision Colab GPU and run benchmark? [y/N] ").strip().casefold()
        if answer not in ("y", "yes"):
            print("Cancelled")
            return 0
    commit = git_head()
    cli = install_colab_cli()
    colab = [cli] + (["--auth=adc"] if a.auth == "adc" else [])
    worker_cmd = [*colab, "run", "--gpu", a.gpu, "--keep", "--timeout", "0", "-s", session]
    if a.high_mem:
        worker_cmd.append("--high-mem")
    worker_cmd += [str(WORKER), "--models", a.models, "--suite", a.suite,
                   "--runs", str(a.runs), "--context", str(a.context),
                   "--max-download-gb", str(a.max_download_gb), "--git-commit", commit]
    if a.allow_large:
        worker_cmd.append("--allow-large")
    if a.allow_hybrid:
        worker_cmd.append("--allow-hybrid")
    run_code = 1
    downloaded = None
    try:
        run_code = invoke(worker_cmd)
        try:
            downloaded = retrieve(colab, session, Path(a.results_dir).expanduser().resolve())
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            print(f"Could not extract results: {exc}", file=sys.stderr)
    finally:
        if a.leave_running:
            print(f"Colab session retained (uses quota): {session}\nStop manually: colab stop -s {session}")
        else:
            stop_code = invoke([*colab, "stop", "-s", session], quiet_failure=True)
            if stop_code:
                print(f"Colab stop returned {stop_code}. Check manually: colab sessions; colab stop -s {session}",
                      file=sys.stderr)
    if not downloaded:
        return run_code if run_code else 2
    return run_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)
