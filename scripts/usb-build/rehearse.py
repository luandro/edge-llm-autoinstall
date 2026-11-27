"""Real offline model inference in disposable containers; not target performance."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

arch, mode = sys.argv[1:]
root = pathlib.Path("/kit/portable") / arch
expected = {"Qwen3.5-0.8B-Q4_K_M.gguf", "Qwen3.5-2B-Q4_K_M.gguf", "Qwen3.5-4B-Q4_K_M.gguf"}
if arch == "x86_64":
    expected.add("gemma-4-E4B-it-Q4_K_M.gguf")
assert {p.name for p in (root / "llm").iterdir() if p.is_dir()} >= expected
def verify(directory, names):
    found = {}
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        h, name = line.split()
        assert name in names and name not in found
        with (directory / name).open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        assert digest == h, f"checksum mismatch: {name}"
        found[name] = h
    assert set(found) == set(names)
def copied(source, dest):
    shutil.copyfile(source, dest)
    dest.chmod(0o755)
    return str(dest)
def run(args, timeout=120):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout).stdout
def infer(binary, model, work):
    log = work / "server.log"
    start = time.monotonic()
    with log.open("w+") as f:
        proc = subprocess.Popen([binary, "-m", str(model), "--host", "127.0.0.1",
                                "--port", "18080", "-c", "8192" if "gemma" in model.name else "4096", "-ngl", "0", "-t", "2",
                                "-np", "1", "--jinja"], stdout=f, stderr=f)
        try:
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(f"server exited {proc.returncode}: {log.read_text()[-3000:]}")
                try:
                    with urllib.request.urlopen("http://127.0.0.1:18080/v1/models", timeout=2) as res:
                        model_id = json.load(res)["data"][0]["id"]
                    break
                except OSError:
                    time.sleep(1)
            else:
                raise TimeoutError("model load")
            for prompt in ["Resuma em português: A reunião será sexta-feira às 9h. Três moradores confirmaram presença.",
                           "Translate to Brazilian Portuguese: The meeting is on Friday at nine."]:
                body = json.dumps({"model": model_id, "messages": [{"role":"user","content":prompt}],
                                   "max_tokens":256, "temperature":0}).encode()
                req = urllib.request.Request("http://127.0.0.1:18080/v1/chat/completions", body,
                                             {"Content-Type":"application/json"})
                with urllib.request.urlopen(req, timeout=600) as res:
                    out = json.load(res)
                answer = out["choices"][0]["message"]
                assert answer.get("content"), f"empty answer {answer}"
                print(json.dumps({"model":model.name,"prompt":prompt,"answer":answer,
                                  "usage":out.get("usage"),"elapsed_s":round(time.monotonic()-start,2)},ensure_ascii=False),flush=True)
        finally:
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
with tempfile.TemporaryDirectory() as d:
    work = pathlib.Path(d)
    for model in sorted(expected):
        bundle = root / "llm" / model
        verify(bundle, ["llama-server", model])
        binary = copied(bundle / "llama-server", work / "llama-server")
        print(arch, model, run([binary,"--version"]).strip(),flush=True)
        if mode == "full" or (mode == "small" and "0.8B" in model):
            infer(binary, bundle / model, work)
    bundle = root / "stt"
    verify(bundle, ["whisper-cli", "ggml-base.bin"])
    binary = copied(bundle / "whisper-cli", work / "whisper-cli")
    run([binary,"--help"])
    if mode != "version":
        for language in ["pt","en"]:
            start = time.monotonic()
            result = run([binary,"-m",str(bundle/"ggml-base.bin"),"-f",f"/kit/samples/sample-{language}.wav",
                          "-l",language,"-t","2"], timeout=600)
            print(json.dumps({"stt":language,"elapsed_s":round(time.monotonic()-start,2),"output":result[-2500:]},ensure_ascii=False),flush=True)
    print(f"PASS {arch} {mode}: binary/manifest checks; inspect any inference outputs for quality. Not physical target validation.",flush=True)
