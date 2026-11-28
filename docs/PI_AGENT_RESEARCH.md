# Pi agent harness research for constrained edge devices

2026-11-28. **Research and decision record; not a new installation profile.** Pi here means the [Pi coding-agent harness](https://pi.dev), not the Raspberry Pi board. Reopen the previously rejected Pi experiment: the old local-pi configuration was likely bloated. Do not infer inherent harness overhead from that configuration.

## Evidence and uncertainty

| Observation | Evidence | Implication |
| --- | --- | --- |
| Previous Pi run ~21,300 prompt tokens, 15–18 min per round | [local-hermes LEARNINGS](https://github.com/luandro/local-hermes/blob/1a9851b8689db47266fb3be0f4355d33a6fbc137/LEARNINGS.md); unpublished local-pi setup | Not a clean upstream baseline; causes not isolated. Do not claim Pi is intrinsically slower. |
| Lean Hermes 15,815 → 4,175 actual prompt tokens | Same lab, [lean config](https://github.com/luandro/local-hermes/blob/1a9851b8689db47266fb3be0f4355d33a6fbc137/config/lean-config.yaml) | Schema/extension/context injection reduction is the main CPU lever. |
| Hermes allocation stays 65,536 | [serve.sh](https://github.com/luandro/local-hermes/blob/1a9851b8689db47266fb3be0f4355d33a6fbc137/serve.sh) and lab notes | Prompt length is not context allocation; observed stock Hermes guard >=64,000. Never spoof server capacity. |
| Original Pi system prompt + four tools <1,000 tokens | [Creator's 2025 design write-up](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/) | Historical creator report, not a measurement of current Pi version or chat-template overhead. Establish new baseline. |
| LFM3 Pi adapter data tasks 70%→80.7%, tool calls −37% on jointly solved tasks | [Publisher Pi model card](https://huggingface.co/harness-hub/LFM3-1.7B-pi) | Promising narrow-task evidence, not GGUF, 4K, PT-BR or Pi-board validation. Hard repo tasks worsened; no claim of coding superiority. |
| LFM3 Hermes adapter data tasks 62%→78%, calls −38% | [Publisher Hermes model card](https://huggingface.co/harness-hub/LFM3-1.7B-hermes) | Different harness/task configuration; compare within controlled experiments, not raw headline scores. |
| Merged Hermes Q4_K_M prefill 18.8→41.0 tok/s, 136→0 CPU_REPACK warnings, 2/2 passes each | ThinkPad lab notes | Prefer merged Pi and Hermes weights, compare parity; no demonstrated ARM speedup. |

## Official upstream resources

- [Pi source](https://github.com/earendil-works/pi), [coding agent documentation](https://github.com/earendil-works/pi/tree/main/packages/coding-agent/docs), [configuration](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/configuration.md), [custom models](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md), [Agent Core](https://github.com/earendil-works/pi/tree/main/packages/agent).
- Pi supports restricted tools, custom system prompts, isolated configuration, headless/RPC and embeddable SDK; the Agent Core is a possible second step if CLI overhead remains high.
- Global/project instructions (including parent directory AGENTS.md), extensions, packages, MCP schemas, skills, prompt templates, prior history and custom system prompts are potential hidden prompt contributors. Record actual context on wire; inspect request size after chat-template rendering; never log credentials or sensitive user content.
- [little-coder](https://github.com/itayinbarr/little-coder): small-model-focused Pi runtime without a fork; borrow model-specific adaptations/isolation, not its ~7K scaffold.
- [pi-local-agents](https://github.com/chrischabot/pi-local-agents): model process lifecycle and selective skills/history, useful inspiration for sequential STT/NMT/LLM. Its hardware/results do not establish edge performance.
- [pi-llama](https://github.com/huggingface/pi-llama): archived after upstream llama.cpp discovery support; verify the current release's native support, avoid obsolete dependencies.
- [Potato OS](https://github.com/potato-os/core): borrow deterministic verifiers, model lifecycle and memory pressure diagnostics. Its supported hardware does not establish 4 GB fit.

## Reproducible clean baseline

Pin a released Pi version and supported Node runtime, record versions and lockfile; use a fresh temporary HOME/config and disposable workspace outside inherited project directories. Never move/delete the existing Pi user config. No credentials, network-backed provider or unreviewed extensions. Inspect the exact release's --help and docs before using flags; names change between versions. Verify the server's actual context and alias. Example candidate models.json in isolated agent dir (adjust to verified release schema):

```json
{
  "providers": {
    "edge": {
      "baseUrl": "http://127.0.0.1:8080/v1",
      "api": "openai-completions",
      "apiKey": "local",
      "models": [{
        "id": "edge-llm", "name": "LFM3 Edge",
        "input": ["text"], "contextWindow": 4096, "maxTokens": 512
      }]
    }
  }
}
```

Candidate CLI invocation (validate flags against installed version, remove/replace unsupported flags with equivalent config; never disable approval for write tools):

```bash
# In isolated, read-only synthetic fixture workspace; server already running.
PI_CODING_AGENT_DIR="$ISOLATED_AGENT_DIR" pi \
  --provider edge --model edge-llm --offline --no-session \
  --no-extensions --no-skills --no-mcp --no-context-files \
  --no-prompt-templates --tools read --thinking off --mode json \
  "Read and summarize sample.txt in Brazilian Portuguese."
```

Start with no tools, then a single read tool, then four stock tools in a sandbox; compare default and compact custom system prompts. Capture actual tool definitions and uncached prompt tokens on llama.cpp, time to first token, decode, result tokens and total across rounds. Keep reasoning and sampling comparable; test valid native tool calls, not merely JSON-shaped output. Use one request/slot. Disable compaction for short bounded fresh sessions; for persistent 4K sessions test reserveTokens=768 and keepRecentTokens=1024 after verifying actual Pi compaction settings (historical defaults 16,384 and 20,000 exceed 4K). Count all compaction calls; cap total rounds and input/output tokens; handle overflow without truncating user intent or authorization.

## Matched model and harness experiment

| Arm | Harness / model | Initial context / prompt target |
| --- | --- | --- |
| A | Optimized Hermes + merged Hermes Q4_K_M | 64K / historical ~4,175 |
| B | Clean Pi + LFM3 base Q4_K_M | 8K then 4K / measure |
| C | Minimal Pi + base, Hermes and Pi merged adapters, separate runs | 4K / <1,500 initial tokens target |
| D | Agent Core + same three variants | 4K / <800 target |
| E | Direct structured LLM calls and deterministic known tasks | 4K / <500 target or no LLM |

Hold model/runtime constant for harness overhead comparisons; separately vary base vs matched vs cross-harness adapter to identify quality effect. Pin [base GGUF](https://huggingface.co/LiquidAI/LFM3-1.7B-GGUF), [Pi PEFT adapter](https://huggingface.co/harness-hub/LFM3-1.7B-pi) and [GGUF adapter](https://huggingface.co/harness-hub/LFM3-1.7B-pi-GGUF). Verify filenames/license/revisions before download. Merge BF16 base with each PEFT adapter on laptop/stronger host, then convert and quantize to Q4_K_M using pinned llama.cpp; log hashes and provenance and validate parity. No merging on 4 GB. Do not assume publisher's large-context training transfers to 4K. Q4 base/adapter, Qwen3/3.5, BotPsy and mini-agent remain comparison controls. See [LFM3 edge profile](LFM3_EDGE_AGENT.md), [task models](TASK_RESEARCH_NOTES.md), [agent model research](AGENT_MODELS.md).

## Conclusion

Pi is the highest-priority **harness experiment** for Raspberry Pi 5 4 GB, and worth testing on NUC too. Start clean upstream CLI/SDK; no fork. Use Agent Core only if measured overhead warrants it. Keep Hermes as comparison and fallback, with existing 64K guard respected. No claim of measured clean-Pi performance, no access to unpublished historical local-pi config, no Pi runtime installed by this document. Next implementation: [PI_TELEGRAM_PLAN.md](PI_TELEGRAM_PLAN.md).
