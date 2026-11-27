#!/usr/bin/env python3
"""Reproducible Hermes workshop evaluation through the real agent core.

Runs bounded Portuguese task cards against an isolated HERMES_HOME and records
actual input/output/reasoning tokens, model requests, tool calls, wall time,
rate-limit errors and task correctness. No secret is printed: the API key is
read from the isolated home's .env.

Usage (from the repository root):
  python3 scripts/workshop-eval.py --harness /path/to/harness.py --case hw --trials 3
  python3 scripts/workshop-eval.py --harness /path/to/harness.py --case all --trials 3

The harness must accept --task, --prompt, --cwd and emit one JSON object on stdout.
See REPORT_PHASE_2.md for a tested harness shape. This script only orchestrates;
it does not execute model-suggested commands.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CASES = {
    "pt": {
        "prompt": "Responda em português, em uma frase: qual é a capital do Brasil? Pare depois de responder.",
        "expect_tool_calls": 0,
        "expect_model_requests": 1,
    },
    "hw": {
        "prompt": (
            'Execute exatamente uma chamada de terminal com este comando: uname -m; free -h; '
            'df -h "$HOME". Resuma arquitetura, RAM e disco em uma frase e pare. '
            'Não inspecione arquivos antes de executar.'
        ),
        "expect_tool_calls": 1,
        "expect_model_requests": 2,
    },
    "usb": {
        "prompt": (
            "Execute exatamente uma chamada de terminal com este comando: "
            "bash workshop-install.sh --usb /CAMINHO/REAL --dry-run. "
            "Mostre apenas modelo e requisitos e pare. Não leia arquivos antes de executar."
        ),
        "expect_tool_calls": 1,
        "expect_model_requests": 2,
    },
    "svc": {
        "prompt": (
            "Execute exatamente uma chamada de terminal com este comando: "
            "curl --fail --silent http://127.0.0.1:8080/v1/models. Relate o resultado e pare."
        ),
        "expect_tool_calls": 1,
        "expect_model_requests": 2,
    },
}


def run_one(harness: str, case: str, prompt: str, cwd: str, trial: int, cooldown: float) -> dict:
    if cooldown:
        time.sleep(cooldown)
    cmd = [sys.executable, harness, "--task", f"{case}-{trial}", "--prompt", prompt, "--cwd", cwd]
    t0 = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=cwd)
    wall = time.monotonic() - t0
    # Last JSON object on stdout is the harness result.
    try:
        payload = json.loads([line for line in proc.stdout.splitlines() if line.startswith("{")][-1])
    except (IndexError, json.JSONDecodeError):
        payload = {"parse_error": True, "stdout_tail": proc.stdout[-500:]}
    stderr = proc.stderr
    payload["harness_wall_s"] = round(wall, 2)
    payload["rate_limited"] = "429" in stderr or "429" in str(payload.get("error") or "")
    payload["reasoning_rejected"] = "rejects reasoning effort" in stderr
    return payload


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--harness", required=True, help="path to the Hermes harness script")
    p.add_argument("--case", choices=[*CASES, "all"], default="all")
    p.add_argument("--trials", type=int, default=3)
    p.add_argument("--cwd", default=str(Path.cwd()))
    p.add_argument("--cooldown", type=float, default=45.0,
                   help="seconds between trials; stagger requests, never parallel per account")
    p.add_argument("--output", default="")
    a = p.parse_args()

    results = []
    cases = list(CASES) if a.case == "all" else [a.case]
    for case in cases:
        spec = CASES[case]
        for i in range(1, a.trials + 1):
            r = run_one(a.harness, case, spec["prompt"], a.cwd, i, a.cooldown if i > 1 else 0)
            r["case"] = case
            r["trial"] = i
            tool_calls = r.get("tools") or []
            # A terminal tool call with N shell commands is one model tool call.
            r["tool_call_count"] = len(tool_calls)
            r["correctness"] = (not r.get("failed") and not r.get("parse_error")
                                and r["tool_call_count"] <= spec["expect_tool_calls"] + 1)
            results.append(r)
            print(json.dumps({k: r.get(k) for k in (
                "case", "trial", "correctness", "failed", "rate_limited",
                "api_calls", "tool_call_count", "input_tokens", "output_tokens",
                "cache_read_tokens", "reasoning_tokens", "elapsed_s")}, ensure_ascii=False))
            sys.stdout.flush()

    out = a.output or f"workshop-eval-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    Path(out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    ok = sum(bool(r["correctness"]) for r in results)
    print(f"\nRESULT {ok}/{len(results)} correct; details in {out}", file=sys.stderr)
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
