#!/usr/bin/env python3
"""Direct offline text tasks; no Hermes, cloud keys, dependencies or automatic fallback."""
import argparse
import json
import sys
import urllib.error
import urllib.request
import pathlib

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def main():
    p = argparse.ArgumentParser(description="IA local: conversar, traduzir e resumir")
    p.add_argument("task", choices=["chat","summary","pt","en","health"])
    p.add_argument("text", nargs="?")
    p.add_argument("--file", type=pathlib.Path)
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--max-tokens", type=int, default=512)
    a = p.parse_args()
    if not 1 <= a.port <= 65535 or not 1 <= a.max_tokens <= 4096:
        p.error("invalid port or token limit")
    base = f"http://127.0.0.1:{a.port}/v1"
    # Disable environment proxies; never leave loopback.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(base + "/models", timeout=10) as response:
            model = json.load(response)["data"][0]["id"]
        if a.task == "health":
            print(f"API local: {model}"); return 0
        if a.file and a.text is not None:
            p.error("use text OR --file")
        text = a.file.read_text(encoding="utf-8") if a.file else a.text
        if text is None:
            if sys.stdin.isatty():
                p.error("provide text, --file or stdin")
            text = sys.stdin.read()
        if not text.strip() or len(text) > 10000:
            p.error("empty text or >10,000 characters; split into short chunks")
        instruction = {
            "chat":"Responda em português brasileiro. Não invente fatos.",
            "summary":"Resuma fielmente em português brasileiro. Preserve nomes, números e datas.",
            "pt":"Traduza para português brasileiro, preservando fatos. Apenas a tradução.",
            "en":"Translate into English faithfully. Output only the translation.",
        }[a.task]
        body = {"model":model,"messages":[{"role":"system","content":instruction},
                {"role":"user","content":text}],"max_tokens":a.max_tokens,"temperature":0.1}
        req = urllib.request.Request(base + "/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type":"application/json"})
        with opener.open(req, timeout=a.timeout) as res:
            obj = json.load(res)
        answer = obj["choices"][0]["message"].get("content")
        if not answer:
            raise RuntimeError("no final response; reduce input or inspect model logs")
        print(answer)
        if obj["choices"][0].get("finish_reason") == "length":
            print("Aviso: resposta truncada; revise.", file=sys.stderr)
        return 0
    except (OSError, ValueError, KeyError, IndexError, RuntimeError) as e:
        print(f"Falha na API local (sem fallback): {e}", file=sys.stderr)
        return 1
if __name__ == "__main__":
    sys.exit(main())
