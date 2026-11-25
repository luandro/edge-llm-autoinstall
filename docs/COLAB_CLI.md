# One-command Google Colab CLI benchmark

The repository now supports Google's **official** [Colab CLI](https://github.com/googlecolab/google-colab-cli) to provision a GPU, run the same synthetic model evaluation, download the report, and stop the runtime. You do not need to open or execute the Colab notebook manually.

## First run

Requirements on the **local** machine: Linux/macOS, Git checkout of this repository, Python 3.10+ for the wrapper, and internet access. The official `colab` program requires Python 3.12+; our wrapper installs it with `uv tool install google-colab-cli` if `uv` exists, otherwise it creates a local Python 3.12 environment. No sudo, no credentials written to the repository.

```bash
git clone https://github.com/luandro/edge-llm-autoinstall.git
cd edge-llm-autoinstall
bash colab-benchmark.sh
```

The CLI asks you to authenticate with your Google account on first use. Choose the account that has Colab access. The wrapper prompts **once** before provisioning the VM; use `--yes` only after deciding to allocate accelerator resources.

**Default:** GPU T4, four small GGUFs (Qwen3.5 0.8B, BotPsy 0.8B, mini-agent-v2 1.5B and Qwen3.5 2B), 11 synthetic test cases per model, one run per case, ~3.4 GB weights downloaded, max 16 GB download allowance.

The wrapper runs the following operations: `colab run --gpu T4 --keep` (temporary session), remote `benchmark.sh` against sequential local CUDA `llama-server` instances, `colab download` for `edge-llm-cli-results.zip`, and **`colab stop` in a `finally` block**. It does not expose an inference API to the internet. The runtime is normally **stopped even if the remote benchmark fails**; if the stop call itself fails, run `colab sessions` and stop it manually to avoid using compute units.

## Useful commands

```bash
bash colab-benchmark.sh --dry-run
bash colab-benchmark.sh                                  # T4; small/quick
bash colab-benchmark.sh --models small --suite full --runs 3 --yes
bash colab-benchmark.sh --models edge --suite full --runs 3 --gpu L4
bash colab-benchmark.sh --models adapter --suite full --runs 3  # review LFM model terms
bash colab-benchmark.sh --models qwen08,botpsy,mini_agent
bash colab-benchmark.sh --gpu A100 --high-mem --models edge --suite full
```

Free T4 quota **is not guaranteed**, even for paid Google users; allocation can fail because of quota or availability. GPU types, compute-unit usage and billed rates depend on the account. ChatGPT Pro is not a Colab subscription. The `--high-mem` flag requests additional RAM only when supported by the user's Google Colab entitlement.

For manual CLI authentication, the default is browser OAuth. To use Google Application Default Credentials for a headless Hermes environment, authorize **locally** with:

```bash
gcloud auth application-default login \
  --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory
bash colab-benchmark.sh --auth adc --yes
```

This authentication step needs the operator's approval. Never put OAuth tokens, passwords or private fieldwork data into model test prompts, this repository, or Colab logs.

## Results and diagnostics

Reports are automatically retrieved to:

```text
reports/colab/<session>.zip
reports/colab/<session>/comparison.md
reports/colab/<session>/comparison.csv
reports/colab/<session>/results.json
reports/colab/<session>/colab_run.json
reports/colab/<session>/runner.log
```

If a remote model fails or the runtime is interrupted, the ZIP may contain a partial comparison and/or `error.txt`. The wrapper tries to retrieve it **even when the remote execution fails**.

Both stages require a working CUDA compiler `nvcc`, not merely a GPU. The remote worker explicitly refuses silent CPU fallback. If Colab has a GPU but the standard runtime lacks `nvcc`, use the notebook or a compatible runtime; the benchmark currently builds llama.cpp with CUDA rather than downloading an unspecified third-party binary.

The default is to stop the session and free its compute resources. `--leave-running` is explicitly opt-in; if used, stop the session yourself with `colab stop -s <session-name>`.

## Important limitations

- This is **model/quantization quality benchmarking on CUDA**, not a prediction of token throughput or peak RAM on Pi 5, N95/N97 or Radeon 780M. Repeat the same suite on each physical machine.
- The suite measures *proposed tool calls only*, and never executes them. PT-BR summary and translation scores are lexical checks, not full human quality ratings.
- Results must be reviewed for task correctness and failure rates before selecting a new Hermes default.
- `--models all` and `--models large` can exceed free runtime GPU memory, download limits and storage. The wrapper requires explicit `--allow-large` and a raised `--max-download-gb`; even then, large models may be skipped or run poorly. Start with `small`, then `edge`.
- Colab runtimes are ephemeral. Downloads, build caches, and intermediate model weights may be lost when the runtime stops. The ZIP is retrieved before shutdown; if the Colab backend itself terminates unexpectedly, the report may be unrecoverable. Consider persistent model caching in a future optional Drive-backed workflow.
- The wrapper checks out the same **committed Git revision** on Colab, avoiding accidental comparisons with a different code version. Uncommitted local work is not transferred.
- This script **does not fine-tune models**; it evaluates the already-post-trained GGUF models. Colab permission/quota must be granted by the account holder.

See the [main benchmark guide](BENCHMARKING.md) and the [official Colab CLI instructions](https://github.com/googlecolab/google-colab-cli).
