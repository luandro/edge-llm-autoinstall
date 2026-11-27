#!/usr/bin/env python3
"""One synthetic tool-call request; no real execution, retries or secret output."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
p=argparse.ArgumentParser(description=__doc__)
p.add_argument("provider",choices=["groq","cloudflare","openrouter"])
p.add_argument("--model")
p.add_argument("--yes",action="store_true",help="Confirm provider privacy/quota and one synthetic API call")
a=p.parse_args()
if not a.yes:
    p.error("check free quota and privacy, then explicitly approve with --yes")
if a.provider=="groq":
    url="https://api.groq.com/openai/v1"; key=os.getenv("GROQ_API_KEY"); model=a.model or "openai/gpt-oss-120b"
elif a.provider=="cloudflare":
    account=os.getenv("CLOUDFLARE_ACCOUNT_ID","")
    if not account.isalnum(): p.error("set CLOUDFLARE_ACCOUNT_ID")
    url=f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1"; key=os.getenv("WORKSHOP_CF_KEY"); model=a.model or "@cf/openai/gpt-oss-120b"
else:
    url="https://openrouter.ai/api/v1"; key=os.getenv("OPENROUTER_API_KEY"); model=a.model or ""
    if not model.endswith(":free"): p.error("select an exact :free model")
if not key: p.error("missing private environment key")
body={"model":model,"messages":[{"role":"user","content":"Call report_disk exactly once with path /; do not run a shell."}],
      "tools":[{"type":"function","function":{"name":"report_disk","description":"Synthetic disk report",
      "parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}}],
      "max_tokens":256,"temperature":0}
if a.provider=="openrouter":
    body["provider"]={"data_collection":"deny","zdr":True,"allow_fallbacks":False,"max_price":{"prompt":0,"completion":0}}
req=urllib.request.Request(url+"/chat/completions",json.dumps(body).encode(),
                           {"Authorization":"Bearer "+key,"Content-Type":"application/json"})
def headers(h):
    return {k:v for k,v in h.items() if k.lower().startswith("x-ratelimit") or k.lower()=="retry-after"}
try:
    with urllib.request.urlopen(req,timeout=60) as response:
        result=json.load(response); rate=headers(response.headers)
    calls=result["choices"][0]["message"].get("tool_calls") or []
    ok=len(calls)==1 and calls[0]["function"]["name"]=="report_disk" and json.loads(calls[0]["function"]["arguments"])=={"path":"/"}
    print(json.dumps({"provider":a.provider,"model":model,"tool_call_ok":ok,"usage":result.get("usage"),"rate":rate},indent=2))
    sys.exit(0 if ok else 1)
except urllib.error.HTTPError as e:
    print(json.dumps({"provider":a.provider,"status":e.code,"rate":headers(e.headers)}))
    sys.exit(1)
except (OSError, ValueError, KeyError, IndexError):
    print("Provider probe failed (no retries; inspect local configuration).",file=sys.stderr)
    sys.exit(1)
