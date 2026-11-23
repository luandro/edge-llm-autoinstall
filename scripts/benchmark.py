#!/usr/bin/env python3
"""Tiny, dependency-free local text benchmark for edge-llm's OpenAI-style API."""
import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CASES = {
    "translation": (
        "Translate this to natural Brazilian Portuguese. Preserve names, numbers and factual meaning. Return only the translation.",
        "The team reviewed 18 audio recordings during a two-day workshop. Three files had missing timestamps, and two needed new transcripts. They agreed to review the remaining files before Friday."
    ),
    "summary": (
        "Summarize in Brazilian Portuguese in three bullets: main facts, decisions and next actions. Do not add claims not supported by the text.",
        "Na reunião, a equipe revisou 18 gravações de entrevistas. Três arquivos estavam sem marcações de tempo; duas transcrições precisavam ser refeitas. Foi decidido corrigir os cinco arquivos, manter os dados offline e validar as transcrições com os participantes antes da publicação."
    ),
    "instruction": (
        "Answer in Brazilian Portuguese, in a single short sentence, without inventing details.",
        "Um computador tem 32 GB de RAM compartilhada entre CPU e GPU. É correto chamar essa memória de 32 GB de VRAM dedicada?"
    ),
}


def bench(url, model, case, timeout, output_tokens):
    system, prompt = CASES[case]
    req = Request(
        url.rstrip("/") + "/chat/completions",
        data=json.dumps({
            "model": model, "stream": False, "temperature": 0,
            "max_tokens": output_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST"
    )
    start = time.monotonic()
    with urlopen(req, timeout=timeout) as r:
        resp = json.load(r)
    wall = time.monotonic() - start
    answer = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    timing = resp.get("timings", {})
    usage = resp.get("usage", {})
    return {
        "case": case, "wall_seconds": round(wall, 2),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "server_prompt_tokens_per_second": timing.get("prompt_per_second"),
        "server_decode_tokens_per_second": timing.get("predicted_per_second"),
        "response": answer,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8080/v1")
    p.add_argument("--model", default="edge-llm")
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--max-tokens", type=int, default=192)
    p.add_argument("--output", help="Optional destination .json file")
    args = p.parse_args()
    results = []
    for task in CASES:
        try:
            result = bench(args.url, args.model, task, args.timeout, args.max_tokens)
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as e:
            print(f"ERROR: {task}: {e}", file=sys.stderr)
            return 1
        results.append(result)
        print(f"\n[{task}] wall={result['wall_seconds']}s; "
              f"prompt tok/s={result['server_prompt_tokens_per_second']}; "
              f"decode tok/s={result['server_decode_tokens_per_second']}\n{result['response']}")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"base_url": args.url, "model": args.model, "results": results}, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {args.output}")
    print("\nTiming/quality benchmark only; responses require manual accuracy review. No STT is measured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
