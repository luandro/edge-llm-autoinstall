#!/usr/bin/env python3
"""Reproducible, non-executing edge model comparison. Python stdlib + Hugging Face Hub for downloads.

Only models' *proposed* tool calls are scored: no model-provided command is ever executed.
The benchmark starts one localhost llama-server at a time, and never alters systemd.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CATALOG = json.loads((ROOT / 'scripts/model_catalog.json').read_text(encoding='utf-8'))['models']
CASES = json.loads((ROOT / 'scripts/benchmark_cases.json').read_text(encoding='utf-8'))['cases']
TOOLS = [
    {'type':'function','function':{'name':'read_file','description':'Read a file at an exact path. Read-only.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},
    {'type':'function','function':{'name':'list_directory','description':'List the contents of a directory. Read-only.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},
    {'type':'function','function':{'name':'search_text','description':'Search for exact text in a directory. Read-only.','parameters':{'type':'object','properties':{'path':{'type':'string'},'query':{'type':'string'}},'required':['path','query']}}},
    {'type':'function','function':{'name':'calculator','description':'Calculate a simple numerical expression.','parameters':{'type':'object','properties':{'expression':{'type':'string'}} ,'required':['expression']}}},
]
TOOL_SYSTEM = 'You are a careful local assistant. Use exactly one offered read-only tool when needed. If the question can be answered without a tool, answer directly. Never guess file contents. Return native function calls, not XML or Markdown tool calls. Never execute commands.'
TRANSLATE_SYSTEM = 'Translate English into natural Brazilian Portuguese (pt-BR). Preserve meaning, names, numbers and technical terms. Only output the translation.'
SUMMARY_SYSTEM = 'Resuma o texto fornecido em português brasileiro. Liste fatos, decisões e próximos passos de modo conciso. Não invente detalhes. Não omita números e prazos importantes.'


def command(cmd, **kwargs):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs)


def gb(b): return round(b / 1_000_000_000, 2)


def mem_total_gb():
    try:
        t = Path('/proc/meminfo').read_text()
        return int(re.search(r'^MemTotal:\s+(\d+)\s+kB',t,re.M).group(1))*1024 / 1e9
    except (OSError, AttributeError): return 0.0


def gpu_vram_gb():
    if not shutil.which('nvidia-smi'): return 0.0
    r=command(['nvidia-smi','--query-gpu=memory.total','--format=csv,noheader,nounits'])
    if r.returncode: return 0.0
    try:return max(float(t.strip()) for t in r.stdout.splitlines() if t.strip())*1048576/1e9
    except ValueError:return 0.0


def system_info(backend):
    return {'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(), 'platform':platform.platform(),
        'machine':platform.machine(),'cpu':next((line.partition(':')[2].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.lower().startswith('model name')),platform.processor()) if Path('/proc/cpuinfo').exists() else platform.processor(),
        'ram_gb':round(mem_total_gb(),2),'cuda_gpu': command(['nvidia-smi','-L']).stdout.strip() if shutil.which('nvidia-smi') else None,
        'vram_gb':round(gpu_vram_gb(),2),'backend':backend,
        'git_sha':command(['git','-C',str(ROOT),'rev-parse','HEAD']).stdout.strip() if (ROOT/'.git').exists() else None}


def choose_backend(arg):
    if arg!='auto':return arg
    if shutil.which('nvidia-smi') and shutil.which('nvcc') and gpu_vram_gb()>0:return 'cuda'
    if shutil.which('vulkaninfo') and shutil.which('glslc'):
        result=command(['vulkaninfo','--summary'])
        if result.returncode==0 and ('radv' in result.stdout.lower() or 'radeon' in result.stdout.lower()):return 'vulkan'
    return 'cpu'


def models_for(selection):
    parts=[x.strip() for x in selection.split(',') if x.strip()]
    if not parts:raise ValueError('No models selected')
    found=[]
    for key in parts:
        chosen=list(CATALOG) if key=='all' else [n for n,v in CATALOG.items() if key in v['groups']] if key in ('small','edge','adapter','large') else [key]
        for n in chosen:
            if n not in CATALOG:raise ValueError(f'Unknown model {n}; choose {", ".join(CATALOG)} or groups small, edge, adapter, large, all')
            if n not in found:found.append(n)
    return found


def has_space_model(entry, backend, allow_hybrid, max_ram_percent):
    ram=mem_total_gb(); size=entry['size_gb']+entry.get('adapter_gb',0)
    if ram and size+0.8>ram*max_ram_percent/100:return False, f'weights ~{size:.1f} GB plus runtime > RAM budget {max_ram_percent}% of {ram:.1f} GB'
    vram=gpu_vram_gb()
    if backend=='cuda' and vram and not allow_hybrid and size+1.5>vram:return False, f'model {size:.1f} GB exceeds single CUDA GPU {vram:.1f} GB minus runtime overhead; choose CPU or --allow-hybrid'
    return True,'ok'


def make_output_folder(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def model_path(entry, cache, dry_run=False):
    path=cache/entry['repo'].replace('/','__')/entry['file']
    if path.is_file() and path.stat().st_size>200_000:return path
    if dry_run:return path
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError('Need huggingface_hub. Use `bash benchmark.sh` which bootstraps a user-space venv.') from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    downloaded=hf_hub_download(repo_id=entry['repo'],filename=entry['file'],local_dir=str(path.parent))
    return Path(downloaded)


def adapter_path(entry,cache):
    if 'adapter_file' not in entry:return None
    v={'repo':entry['adapter_repo'],'file':entry['adapter_file']}
    return model_path(v,cache)


def build_server(backend, cache, jobs, binary=None):
    if binary:
        b=Path(binary).expanduser().resolve()
        if not b.exists():raise RuntimeError(f'No llama-server binary: {b}')
        return b
    source=cache/'llama.cpp'
    if not (source/'.git').exists():
        if not shutil.which('git'):raise RuntimeError('git missing. Install git or supply --binary.')
        print('Cloning llama.cpp in user cache ...',flush=True)
        subprocess.run(['git','clone','--depth','1','https://github.com/ggml-org/llama.cpp.git',str(source)],check=True)
    binary_path=source/f'build-{backend}'/'bin'/'llama-server'
    if binary_path.exists():return binary_path
    if not shutil.which('cmake'):raise RuntimeError('cmake missing. Install build-essential, cmake and libcurl-dev, or pass --binary.')
    if backend=='cuda' and not shutil.which('nvcc'):raise RuntimeError('CUDA chosen but nvcc not found. Select CPU or install the CUDA toolkit.')
    if backend=='vulkan' and not shutil.which('glslc'):raise RuntimeError('Vulkan chosen but glslc absent. Install shaderc/glslc or use --backend cpu.')
    kwargs={'GGML_CUDA':'ON' if backend=='cuda' else 'OFF','GGML_VULKAN':'ON' if backend=='vulkan' else 'OFF'}
    opts=[f'-D{k}={v}' for k,v in kwargs.items()]
    outdir=source/f'build-{backend}'
    print(f'Compiling llama.cpp ({backend}, {jobs} jobs) ...',flush=True)
    subprocess.run(['cmake','-S',str(source),'-B',str(outdir),'-DCMAKE_BUILD_TYPE=Release','-DGGML_NATIVE=ON','-DGGML_CURL=ON','-DLLAMA_BUILD_SERVER=ON',*opts],check=True)
    subprocess.run(['cmake','--build',str(outdir),'--target','llama-server','-j',str(jobs)],check=True)
    if not binary_path.exists():raise RuntimeError('llama-server not found after compilation')
    return binary_path


def port_available():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def http_get(url,timeout=3):
    with urlopen(url,timeout=timeout) as r:return json.load(r)


def chat_call(url,model,case,max_tokens,timeout):
    if case['category'] in ('tool','tool_pt','no_tool'):
        system=TOOL_SYSTEM
        payload_tools={'tools':TOOLS,'tool_choice':'auto'}
    else:
        system=TRANSLATE_SYSTEM if case['category']=='translation' else SUMMARY_SYSTEM
        payload_tools={}
    query=json.dumps({'model':model,'temperature':0,'seed':42,'max_tokens':max_tokens,'stream':False,
        'messages':[{'role':'system','content':system},{'role':'user','content':case['prompt']}],**payload_tools},ensure_ascii=False).encode()
    req=Request(url.rstrip('/')+'/chat/completions',data=query,headers={'Content-Type':'application/json'},method='POST')
    start=time.monotonic()
    with urlopen(req,timeout=timeout) as response:body=json.load(response)
    elapsed=time.monotonic()-start
    message=body.get('choices',[{}])[0].get('message') or {}
    timing=body.get('timings') or {}
    usage=body.get('usage') or {}
    return {'seconds':round(elapsed,3),'response':message.get('content') or '',
       'tool_calls':message.get('tool_calls') or [],'finish_reason':body.get('choices',[{}])[0].get('finish_reason'),
       'prompt_tokens':usage.get('prompt_tokens'), 'completion_tokens':usage.get('completion_tokens'),
       'prompt_tps':timing.get('prompt_per_second'), 'decode_tps':timing.get('predicted_per_second'),
       'reasoning_text':message.get('reasoning_content') or ''}


def norm(s):
    s=unicodedata.normalize('NFD',str(s or '').casefold())
    return re.sub(r'\s+',' ',''.join(c for c in s if unicodedata.category(c)!='Mn')).strip()


def char_f_score(candidate,reference,nmax=4):
    """Small character n-gram overlap heuristic, not COMET or human translation evaluation."""
    a=norm(candidate);b=norm(reference)
    if not a or not b:return 0.0
    results=[]
    for n in range(1,min(nmax,len(a),len(b))+1):
        from collections import Counter
        ca=Counter(a[i:i+n] for i in range(max(0,len(a)-n+1)))
        cb=Counter(b[i:i+n] for i in range(max(0,len(b)-n+1)))
        hits=sum((ca&cb).values()); p=hits/max(1,sum(ca.values())); r=hits/max(1,sum(cb.values()))
        results.append(2*p*r/(p+r) if p+r else 0)
    return round(sum(results)/len(results),3)


def parse_call(call):
    fun=call.get('function') or {}
    name=fun.get('name')
    try:
        args=fun.get('arguments') or '{}'
        args=json.loads(args) if isinstance(args,str) else args
        if not isinstance(args,dict):return name,{},'not an object'
        return name,args,None
    except ValueError:return name,{},'invalid JSON'


def score_case(case,run):
    if 'error' in run:return {'correct':False,'metric':0.0,'metric_name':'error'}
    cat=case['category']; calls=run.get('tool_calls',[])
    if cat in ('tool','tool_pt'):
        if len(calls)!=1:return {'correct':False,'metric':0.0,'metric_name':'native_tool_exact','detail':f'{len(calls)} calls'}
        name,args,error=parse_call(calls[0]); target=case['expected_arguments']
        if name=='calculator' and isinstance(args.get('expression'),str):
            args['expression']=re.sub(r'\s+','',args['expression'])
        correct=name==case['expected_tool'] and error is None and args==target
        return {'correct':correct,'metric':1.0 if correct else 0.0,'metric_name':'native_tool_exact','detail':{'observed_name':name,'observed_arguments':args,'parse_error':error}}
    if cat=='no_tool':
        correct=not calls and bool((run.get('response') or '').strip())
        return {'correct':correct,'metric':1.0 if correct else 0.0,'metric_name':'no_tool_correct'}
    text=run.get('response') or ''
    if cat=='translation':
        required=case.get('required_terms',[])
        terms=sum(norm(q) in norm(text) for q in required)/max(1,len(required))
        return {'correct':None,'metric':round(terms,3),'metric_name':'required_terms_preserved','reference_overlap':char_f_score(text,case['reference'])}
    if cat=='summary':
        # Lexical/number evidence coverage only; manual factuality review essential.
        required=case.get('required_terms',[])
        terms=sum(norm(q) in norm(text) for q in required)/max(1,len(required))
        return {'correct':None,'metric':round(terms,3),'metric_name':'required_facts_mentioned'}
    return {'correct':None,'metric':None,'metric_name':'unknown'}


def peak_rss_mib(pid):
    try:
        t=Path(f'/proc/{pid}/status').read_text()
        m=re.search(r'^VmHWM:\s+(\d+) kB',t,re.M)
        return round(int(m.group(1))/1024,1) if m else None
    except (OSError,AttributeError):return None


def start_server(binary,path,adapter,entry,port,ctx,backend,gpu_layers,log_file,deadline):
    cmd=[str(binary),'-m',str(path),'--alias','edge-llm','--host','127.0.0.1','--port',str(port),
         '-c',str(ctx),'-np','1','-b','256','-ub','128','--jinja','-ngl',str(gpu_layers if backend!='cpu' else 0)]
    if adapter:cmd+=['--lora',str(adapter)]
    if entry.get('chat_template_kwargs'):cmd+=['--chat-template-kwargs',json.dumps(entry['chat_template_kwargs'])]
    log=open(log_file,'w',encoding='utf8')
    proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    start=time.monotonic()
    try:
        while time.monotonic()-start<deadline:
            if proc.poll() is not None:raise RuntimeError(f'llama-server exited {proc.returncode}; see {log_file}')
            try:
                health=http_get(f'http://127.0.0.1:{port}/health',timeout=2)
                if health.get('status') not in ('ok','ready'):
                    time.sleep(1.5); continue
                http_get(f'http://127.0.0.1:{port}/v1/models',timeout=2)
                return proc,log,round(time.monotonic()-start,2)
            except (URLError,TimeoutError,ConnectionError,OSError,ValueError):time.sleep(1.5)
        raise TimeoutError(f'Model did not become ready after {deadline}s; see {log_file}')
    except Exception:
        stop_server(proc,log)
        raise


def stop_server(proc,log):
    try:
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=5)
    except (ProcessLookupError,PermissionError):pass
    finally:log.close()


def summarize(records):
    # Failed requests stay in each accuracy denominator; otherwise a model
    # that errors on hard cases can appear more accurate than a reliable one.
    ok=[r for r in records if not r.get('error')]
    result={'attempted':len(records),'successful_responses':len(ok),'errors':len(records)-len(ok),
            'response_success_rate':round(len(ok)/len(records),3) if records else None}
    for category in ('tool','tool_pt','no_tool','translation','summary'):
        rows=[r for r in records if r['category']==category]
        metrics=[r.get('metric',0.0) if not r.get('error') else 0.0 for r in rows]
        metrics=[v if isinstance(v,(int,float)) else 0.0 for v in metrics]
        result[category+'_n']=len(rows)
        result[category+'_score']=round(statistics.mean(metrics),3) if metrics else None
    rows=[r for r in records if r['category'] in ('tool','tool_pt','no_tool')]
    result['tool_total_n']=len(rows)
    result['tool_correct_rate']=round(sum(r.get('correct') is True for r in rows)/len(rows),3) if rows else None
    for name,key in [('median_wall_seconds','seconds'),('median_decode_tps','decode_tps'),('median_prompt_tps','prompt_tps')]:
        vals=[r[key] for r in ok if isinstance(r.get(key),(int,float)) and r[key]>0]
        result[name]=round(statistics.median(vals),2) if vals else None
    return result


def write_reports(out,metadata,results):
    output={'metadata':metadata,'models':results}
    (out/'results.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    rows=[]
    for name,m in results.items():
        stat=m.get('summary',{});rows.append({'model':name,'status':m.get('status','unknown'),'backend':metadata['hardware']['backend'],
            'tool_correct_rate':stat.get('tool_correct_rate'),'response_success_rate':stat.get('response_success_rate'),'translation_term_score':stat.get('translation_score'),
            'summary_fact_coverage':stat.get('summary_score'),'median_wall_s':stat.get('median_wall_seconds'),
            'median_decode_tps':stat.get('median_decode_tps'),'median_prompt_tps':stat.get('median_prompt_tps'),
            'peak_server_rss_mib':m.get('peak_server_rss_mib'),'load_seconds':m.get('load_seconds'),'error':m.get('error','')})
    with (out/'comparison.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['model']);w.writeheader();w.writerows(rows)
    lines=['# Edge AI benchmark comparison','',f"Hardware: {metadata['hardware']['cpu']} | RAM {metadata['hardware']['ram_gb']} GB | backend {metadata['hardware']['backend']}",
       '',f"Suite: {metadata['suite']}, repetitions: {metadata['runs']}, context: {metadata['context']}",'',
       '| Model | Status | Response rate | Tool accuracy† | Translation terms‡ | Summary facts‡ | Median s/call | Decode tok/s | Peak RSS MiB |',
       '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    def fmt(v):return '—' if v is None else f'{v:.2f}' if isinstance(v,(int,float)) else str(v)
    for r in rows:
        lines.append('| '+' | '.join(str(r['model']) if k=='model' else fmt(r[k]).replace('|','/') for k in ['model','status','response_success_rate','tool_correct_rate','translation_term_score','summary_fact_coverage','median_wall_s','median_decode_tps','peak_server_rss_mib'])+' |')
    lines+=['','† Native *single function-call + exact arguments*, including correct no-tool decisions; **no commands executed**.',
      '‡ Translation checks required names/numbers and reference overlap; summary checks lexical fact coverage. **Neither measures full semantic quality or hallucinations. Manual PT-BR review required.**',
      'Errors and timeouts count as zero in all quality-score denominators. Response rate shows reliability; scores are *not* conditioned on success.',
      'Only compare speeds within **the same hardware/backend/context**. Data from Colab CUDA do not predict Raspberry Pi, Intel N95/N97 or Radeon 780M performance.',
      'Status skipped/error means no valid model measurement. Do not rank on speed without task accuracy.','']
    (out/'comparison.md').write_text('\n'.join(lines),encoding='utf8')
    print('\n'.join(lines[:8+len(rows)]))
    print(f'\nReports saved: {out}/results.json, comparison.csv, comparison.md')


def args_parser():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('--models',default='small',help='small, edge, adapter, large, all, or comma-separated names from model_catalog.json')
    p.add_argument('--suite',choices=['quick','full'],default='quick')
    p.add_argument('--runs',type=int,default=1,help='Repetitions per case. Use 3 for comparisons.')
    p.add_argument('--backend',choices=['auto','cuda','vulkan','cpu'],default='auto')
    p.add_argument('--require-gpu',action='store_true',help='Fail fast unless CUDA/Vulkan is usable; recommended on cloud GPU notebooks')
    p.add_argument('--gpu-layers',type=int,default=99)
    p.add_argument('--binary',help='Existing llama-server binary (avoids compilation)')
    p.add_argument('--server-url',help='Evaluate an existing OpenAI-compatible server only; no models installed/changed')
    p.add_argument('--server-model',default='edge-llm')
    p.add_argument('--cache-dir',default=str(Path.home()/'.cache/edge-llm-benchmark'))
    p.add_argument('--output-dir',help='Report directory; default reports/<UTC timestamp>')
    p.add_argument('--context',type=int,default=4096)
    p.add_argument('--max-tokens',type=int,default=768,help='Token budget: allow thought tokens for tool specialists')
    p.add_argument('--timeout',type=int,default=180,help='Per-request timeout seconds')
    p.add_argument('--startup-timeout',type=int,default=240)
    p.add_argument('--max-download-gb',type=float,default=16,help='Total planned new weights limit; override consciously')
    p.add_argument('--ram-limit-percent',type=int,default=78)
    p.add_argument('--allow-hybrid',action='store_true',help='Allow weights above CUDA VRAM; may be extremely slow')
    p.add_argument('--allow-large',action='store_true',help='Explicit acknowledgment for downloads of >8GB models')
    p.add_argument('--yes',action='store_true',help='Approve downloads/compilation in noninteractive notebook')
    p.add_argument('--dry-run',action='store_true',help='Print plan only; no changes, downloads or builds')
    return p


def main(argv=None):
    a=args_parser().parse_args(argv)
    if a.runs<1 or a.runs>20 or a.context<512 or a.context>131072 or a.max_tokens<64 or a.max_tokens>8192:
        raise SystemExit('Invalid runs, context or max-tokens')
    backend=choose_backend(a.backend)
    if a.require_gpu and backend == 'cpu':
        raise SystemExit('GPU required but unavailable: check Runtime > Change runtime type > GPU, nvidia-smi, nvcc, or Vulkan/Mesa. Refusing silent CPU fallback.')
    if a.require_gpu and backend == 'cuda' and (not shutil.which('nvidia-smi') or not shutil.which('nvcc')):
        raise SystemExit('CUDA required: nvidia-smi and nvcc must both work. Do not run the cloud comparison on CPU by mistake.')
    hardware=system_info(backend)
    cache=Path(a.cache_dir).expanduser().resolve()
    out=Path(a.output_dir).expanduser().resolve() if a.output_dir else ROOT/'reports'/dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')
    selected=['current_server'] if a.server_url else models_for(a.models)
    if a.server_url and len(a.models.split(','))>1:print('Note: --server-url tests only the already running model.',file=sys.stderr)
    if a.server_url and not a.server_url.startswith('http://127.0.0.1:') and not a.server_url.startswith('http://localhost:'):
        raise SystemExit('For safety, --server-url currently only allows localhost. Tunnel remote hosts over SSH.')
    cases=[c for c in CASES if a.suite=='full' or c.get('quick')]
    planned=sum(v['size_gb']+v.get('adapter_gb',0) for k in selected if (v:=CATALOG.get(k)))
    new_bytes=0
    for k in selected:
        if k in CATALOG:
            v=CATALOG[k]
            for repo,file,size in [(v['repo'],v['file'],v['size_gb'])]+([(v['adapter_repo'],v['adapter_file'],v.get('adapter_gb',0))] if 'adapter_file' in v else []):
                if not (cache/'models'/repo.replace('/','__')/file).exists():new_bytes+=size
    print(f'\nHardware: {hardware["cpu"]} | RAM {hardware["ram_gb"]} GB | GPU VRAM {hardware["vram_gb"]} GB | backend {backend}')
    print(f'Selected: {", ".join(selected)} | {len(cases)} synthetic cases x {a.runs} | ~{planned:.1f} GB weights, ~{new_bytes:.1f} GB new downloads')
    for k in selected:
        v=CATALOG.get(k)
        if v:
            ok,reason=has_space_model(v,backend,a.allow_hybrid,a.ram_limit_percent)
            print(f'  {k:14s} {v["size_gb"]:.2f} GB  {"fit" if ok else "SKIP: "+reason}')
    if a.dry_run:return 0
    if new_bytes>a.max_download_gb:raise SystemExit(f'Planned downloads {new_bytes:.1f}GB exceed --max-download-gb {a.max_download_gb}GB. Select fewer models or raise the limit explicitly.')
    if any(CATALOG[k]['size_gb']>8 for k in selected if k in CATALOG) and not a.allow_large:
        raise SystemExit('Large models require --allow-large. Not recommended on free Colab T4.')
    if not a.yes and not a.server_url:
        if not sys.stdin.isatty():raise SystemExit('Noninteractive notebook: pass --yes to allow model downloads and local compilation (no sudo).')
        answer=input('Download/compile these models sequentially? [y/N] ').strip().lower()
        if answer not in ('y','yes'):print('Cancelled');return 0
    make_output_folder(out)
    metadata={'suite':a.suite,'runs':a.runs,'context':a.context,'max_tokens':a.max_tokens,
              'hardware':hardware,'models_selected':selected,'cases':len(cases),
              'protocol':'Native OpenAI-style tool calls, no tool execution; synthetic fixtures',
              'warnings':['Not Hermes end-to-end tasks','Lexical PT-BR quality proxies are not human ratings','Colab CUDA speed does not predict edge CPU/Vulkan throughput']}
    results={}
    if not a.server_url:
        jobs=min(4,os.cpu_count() or 2)
        if mem_total_gb() and mem_total_gb()<7:jobs=min(jobs,2)
        binary=build_server(backend,cache,jobs,a.binary)
    else:binary=None
    for mid in selected:
        entry=CATALOG.get(mid)
        model_out=out/mid
        model_out.mkdir(parents=True,exist_ok=True)
        proc=log=None
        record={'status':'error','cases':[]}
        results[mid]=record
        try:
            if a.server_url:
                url=a.server_url.rstrip('/')+'/v1' if not a.server_url.rstrip('/').endswith('/v1') else a.server_url.rstrip('/')
                model=a.server_model;record['load_seconds']=0
                http_get(url+'/models',timeout=5)
            else:
                ok,reason=has_space_model(entry,backend,a.allow_hybrid,a.ram_limit_percent)
                if not ok:
                    record.update(status='skipped',error=reason);print(f'SKIP {mid}: {reason}',flush=True);continue
                path=cache/'models'/entry['repo'].replace('/','__')/entry['file']
                if not path.is_file():
                    free=shutil.disk_usage(cache).free if cache.exists() else shutil.disk_usage(cache.parent if cache.parent.exists() else Path.home()).free
                    needed=entry['size_gb']*1e9+1_500_000_000
                    if free<needed:record.update(status='skipped',error=f'Insufficient disk: {gb(free)} GB free, need ~{gb(needed)}');continue
                path=model_path(entry,cache/'models')
                adapter=adapter_path(entry,cache/'models')
                port=port_available();url=f'http://127.0.0.1:{port}/v1';model='edge-llm'
                print(f'Running {mid}: {entry["label"]}',flush=True)
                proc,log,record['load_seconds']=start_server(binary,path,adapter,entry,port,a.context,backend,a.gpu_layers,model_out/'server.log',a.startup_timeout)
            # One warmup with no tools. Warmup excluded from results.
            try:
                warm={'id':'warmup','category':'no_tool','prompt':'Reply with the single word OK.'}
                chat_call(url,model,warm,min(100,a.max_tokens),a.timeout)
            except Exception as ex: print(f'  Warmup warning: {ex}',flush=True)
            for n in range(a.runs):
                for case in cases:
                    row={'case_id':case['id'],'category':case['category'],'repetition':n+1}
                    try:
                        response=chat_call(url,model,case,a.max_tokens,a.timeout)
                        row.update(response)
                        row.update(score_case(case,row))
                    except Exception as ex:
                        row['error']=str(ex);row.update(score_case(case,row))
                    record['cases'].append(row)
                    print(f'  [{n+1}/{a.runs}] {case["id"]}: {row.get("metric_name")}: {row.get("metric")} ({row.get("seconds", "error")}s)',flush=True)
            record['summary']=summarize(record['cases'])
            record['status']='completed' if record['summary']['errors']==0 else 'partial'
        except (Exception,KeyboardInterrupt) as exc:
            record.update(status='error',error=str(exc))
            print(f'  Error {mid}: {exc}',file=sys.stderr,flush=True)
            if isinstance(exc,KeyboardInterrupt):raise
        finally:
            if proc is not None:
                record['peak_server_rss_mib']=peak_rss_mib(proc.pid)
                stop_server(proc,log)
            write_reports(out,metadata,results)
    return 0 if any(r.get('status') in ('completed','partial') for r in results.values()) else 2


if __name__=='__main__':
    try:sys.exit(main())
    except KeyboardInterrupt:sys.exit(130)