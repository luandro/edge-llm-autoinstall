# Comparing local edge models: Pi / N95-N97 / K11 / cloud

Run the **same** synthetic tasks on each model. Start with a small set, then use the full suite. The runner uses temporary localhost `llama-server` instances, one at a time, and **never executes a model's proposed commands**.

**Reliability:** request errors and timeouts are now counted as **zero** in task-score denominators, rather than excluded. Comparison reports also show **response success rate**, preventing an error-prone model from appearing artificially accurate. It does not modify systemd, kernel, BIOS, or other running services.

## One command

```bash
bash benchmark.sh --dry-run --models small
bash benchmark.sh --models small --suite quick --runs 1
bash benchmark.sh --models edge --suite full --runs 3
```

`small` tests **Qwen3.5 0.8B Q4, BotPsy 0.8B Q4, mini-agent 1.5B Q4, Qwen3.5 2B Q4**. `edge` adds Qwen3.5 4B Q4 and Gemma 4 E4B Q4. `adapter` compares LFM3 1.7B Q8 **base versus the same base with Hermes LoRA** (license review required). `large` includes K11 and Pi experimental large models; `all` includes everything in `scripts/model_catalog.json` and may exceed 100 GB. These large options require an additional `--allow-large` acknowledgement and a consciously raised `--max-download-gb` limit; many will be skipped on Colab T4 due to RAM or VRAM.

Or select exact models:

```bash
bash benchmark.sh --models qwen08,botpsy,mini_agent --runs 3 --suite full
bash benchmark.sh --models lfm3_base,lfm3_hermes --suite full --runs 3
```

**Requirements:** Linux, Python 3.10+, git, cmake, C/C++ compiler and libcurl development headers to compile llama.cpp, sufficient storage and Internet for downloading public GGUFs. `benchmark.sh` installs only `huggingface_hub` in a project-local venv if missing. It does **not** use `sudo`. You can instead provide a precompiled `--binary /path/to/llama-server`. On Raspberry Pi or a mini PC it auto-detects CPU; on a Colab GPU with CUDA Toolkit (`nvcc`), it builds CUDA. For Radeon 780M/Mesa use `--backend vulkan` after installing Vulkan compiler and runtime dependencies.

### Free Colab preflight and results

Colab runtimes are ephemeral: runtime resets discard local weights and unsaved reports. The [notebook](../notebooks/benchmark_colab.ipynb) now **requires a GPU**, checks that both `nvidia-smi` and `nvcc` are present, and explicitly runs `--backend cuda --require-gpu`. This prevents a missing CUDA toolkit from silently launching a many-hour CPU benchmark. If the preflight fails, switch Colab to a GPU runtime and reconnect; if `nvcc` is missing, use a compatible CUDA toolkit/runtime instead of interpreting CPU throughput as a GPU result. No free accelerator or fixed Colab quota is guaranteed.

Start with **quick, one repetition**; only increase to `--suite full --runs 3` after the first comparison succeeds. Each model is loaded sequentially, and the runner writes reports after each model. The notebook's last cell generates and **downloads a ZIP containing JSON, CSV and Markdown reports**, excluding verbose server logs. Download them before disconnecting. If a GPU runtime ends mid-run, previously completed models' reports remain on the runtime's disk but **will be lost when the runtime is deleted unless downloaded**. Model comparisons should be repeated on the same GPU/backend for valid throughput comparisons.

For CLI cloud hosts with a functioning CUDA toolkit:

```bash
bash benchmark.sh --models small --suite quick --runs 1 --backend cuda --require-gpu --yes
```

**On the target that already has the installed `edge-llm` service:** compare the current configuration without switching models or downloading anything:

```bash
bash benchmark.sh --server-url http://127.0.0.1:8080 --suite full --runs 3
```

The runner uses `--server-model edge-llm` by default for an existing API; on managed multi-model comparisons it launches each model sequentially on a random loopback-only port. To compare existing vs new settings, ensure the hardware, context, backend, repetition count and task suite match.

## What is actually measured

- **Tool accuracy:** native OpenAI-style function calls: 18 test requests (12 English, six PT-BR), exact function name and arguments, including read-only file paths; plus six *no-tool* decisions. The harness never executes proposed file reads, Bash, or Python.
- **Translation:** eight synthetic EN→PT-BR segments, checks preservation of specified names/numbers and reports simple character reference overlap. **Not a human quality score, BLEU, chrF++, COMET, or definitive translation ranking**.
- **Summarization:** eight short synthetic PT-BR excerpts, measures whether specified facts appear in the text. **Not factuality verification**; review hallucinations manually.
- **Speed:** per-call wall time, llama.cpp-reported prompt/decode tok/s when available, model load time, process peak RSS, generated tokens, model/backend/hardware metadata and error records. Does not measure actual Hermes autonomous coding, STT WER or audio translation. No speculative time-to-first-token metric is made up.

The **quick** suite uses 11 representative test requests and the **full** suite all 40. **Timeouts and failed responses count against each task's accuracy score**; speed medians use only successful responses and must be viewed alongside the reported success rate. Use three warm repetitions per model when choosing defaults. Large throughput differences on different backends do **not** establish that a Pi or Radeon 780M will achieve CUDA speed.

## Results

Every run saves a dated directory under `reports/`:

```text
reports/YYYYMMDD-HHMMSS/
  results.json           # all responses, per-case scores and device metadata
  comparison.csv         # summary comparison table
  comparison.md          # human-readable ranking table and warnings
  <model>/server.log     # llama.cpp diagnostic output; review before sharing
```

Published `reports/` must not contain personal transcripts or secrets. These fixtures are synthetic and public. Do not enter confidential Indigenous territorial information, partner data or transcripts into hosted notebooks without permission. Share only curated, sanitized benchmark reports.

## One-click Colab, Kaggle and on-device runs

- **Colab:** open [benchmark_colab.ipynb](../notebooks/benchmark_colab.ipynb). Select **Runtime → Change runtime type → T4 GPU**, then run all cells. GPU access is dynamic; CUDA may not be available. The notebook clones this public repo and invokes the *same* `benchmark.sh`. Full comparison normally fits within a T4 session if models are limited to `small`, but GPU, RAM, availability and time vary. The benchmark script starts a transient *localhost-only* inference server as an interactive compute step, not a public web endpoint.
- **Kaggle:** create a free GPU Notebook, enable Internet in notebook settings, clone the repo and run `bash benchmark.sh --models small --suite quick --yes`. Notebooks may limit GPU allocation or block network; availability and quota vary.
- **Lightning AI:** introductory GPU credits may be offered, but no fixed free allowance should be assumed; same Linux command applies.
- **Hugging Face ZeroGPU:** not recommended as a benchmark runner. It is a Gradio-specific shared GPU environment with short function durations rather than an ordinary persistent shell.
- **Actual Pi/N95/K11:** mandatory for valid on-device power, memory, and prompt/decode speed comparison. Colab is useful for *quality/functionality triage*, not for hardware performance forecasts.

A ChatGPT Plus/Pro subscription does not automatically confer paid Colab/GPU units. Google AI Pro or a Colab-native subscription may grant additional Colab access, depending on the Google account. Free Colab GPU access is neither guaranteed nor unlimited; do not circumvent platform quotas or run persistent unattended workers.

## Failure handling

A model that exceeds the system memory budget or single NVIDIA GPU VRAM is **skipped and recorded**, not silently substituted with a different quantization. `--allow-hybrid` permits oversize models only when the user explicitly chooses CPU/GPU hybrid offload; often much slower. `--context 4096` is the common starting point; when testing Pi 4 GB, prefer `--context 2048`. Build/runtime failures appear in `server.log` and JSON results; incomplete measurements must not be interpreted as success. To avoid very large downloads, use `--dry-run` and the default `--max-download-gb 16` guard.

This is an evaluation harness. It never changes the model selected by `install.sh`, and it never promotes an experimental model to a default automatically.

## Sources (access and limits)

- [Official Google Colab FAQ](https://research.google.com/colaboratory/faq.html): dynamic GPU quotas, at most 12h in free tier, no guaranteed machine type.
- [Kaggle notebooks documentation](https://www.kaggle.com/docs/notebooks): free accelerator access subject to account quota and availability.
- [Lightning AI studios](https://platform.lightning.ai/studio): conditional introductory GPU allocation.
- [Hugging Face ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu): shared Gradio GPU function limits and quotas.