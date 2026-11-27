# Guia do participante — instalação e verificação (pt-BR)

Versão revisada em 2026-11-27 com resultados do ensaio de prontidão. Este guia
não contém chaves nem segredos. O operador define credenciais apenas no
ambiente isolado da própria máquina.

## 0. Escolha o modo correto

| Modo | Quando usar | Perfil Hermes | Custo típico da 1ª chamada |
|---|---|---|---|
| **Implantação somente terminal (recomendada)** | Instalar/verificar no equipamento alvo; comandos limitados e pré-aprovados | Perfil novo, `--no-skills`, sem carregar o corpo da skill | ~3,6 mil tokens de entrada, 1 chamada de terminal, 2 requisições ao modelo |
| **Personalização com skill habilitada (opcional)** | Pedir ao agente que raciocine sobre o conteúdo da skill e adapte o procedimento | Mesmo perfil, porém com a toolset `skills` ativa | ~6,7 mil tokens quando a skill é curta; **pode passar de 8 mil e falhar** no Groq free tier |

A implantação de oficina usa o **modo somente terminal**. A skill instalada é
documentação revisada para o operador e para o agente; ela não precisa ser
carregada automaticamente em cada tarefa.

## 1. Verifique a versão antes de usar qualquer flag

```bash
hermes --version
hermes profile create --help
hermes skills install --help
```

Use somente flags existentes na versão instalada (v0.23.4 verified).

## 2. Instalação nova do Hermes em ambiente isolado

A instalação padrão é o instalador público. Isole **os dois** caminhos para
não tocar em perfis, `~/.local/bin` ou arquivos de shell da máquina:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o /tmp/instalar-hermes.sh
HERMES_HOME=/tmp/hermes-participante HOME=/tmp/home-participante \
  bash /tmp/instalar-hermes.sh \
  --non-interactive --skip-browser --skip-computer-use \
  --commit 8fc0374447313e276f6b9a2764bfc750190c966a
```

Depois crie um perfil novo. **Nunca sobrescreva um perfil existente:**

```bash
export HERMES_HOME=/tmp/hermes-participante
"$HERMES_HOME/hermes-agent/.hermes/bin/hermes" \
  profile create participant --no-skills --no-credentials --no-alias
```

`--no-credentials` impede a cópia de chaves do perfil de origem;
`--no-alias` impede a criação de atalho em `~/.local/bin`.

## 3. Instale apenas a skill revisada

```bash
hermes -p participant skills install \
  https://github.com/luandro/edge-llm-autoinstall/raw/main/SKILL.md -y
```

O `SKILL.md` é curto (4,7 KB); os detalhes ficam em `references/` e são
buscados apenas quando necessários. Confira:

```bash
hermes -p participant skills list | grep edge-llm-autoinstall
```

## 4. Mescle a configuração enxuta (com backup)

O arquivo efetivo do perfil é `$HERMES_HOME/profiles/participant/config.yaml`
(se não existir, crie-o; while missing, o perfil usa o `config.yaml` raiz).

```bash
cp "$HERMES_HOME/profiles/participant/config.yaml" \
   "$HERMES_HOME/profiles/participant/config.yaml.bak"
# Mescle config/workshop-lean.yaml no config.yaml do perfil participant.
hermes -p participant config get platform_toolsets.cli   # deve mostrar: - terminal
```

Verificação medida no perfil novo e isolado: `terminal` como única toolset,
4 ferramentas / 4.915 bytes de JSON, índice de skills vazio (skill instalada,
mas não carregada automaticamente).

A configuração deve manter: `terminal` como única toolset da CLI, sem plugins,
sem MCP, sem memória, no máximo 6 turnos, saída de terminal limitada e nenhum
fallback automático. Para Groq use `provider: custom`,
`base_url: https://api.groq.com/openai/v1`, `api_key: ${GROQ_API_KEY}` e
`model.default: openai/gpt-oss-120b`. A chave fica apenas no `.env` do perfil.
O operador deve habilitar e verificar o **ZDR** no console do Groq.

**Não** use `reasoning_effort: none`: o modelo gpt-oss aceita apenas
`low`/`medium`/`high`. Com `low` há uma requisição extra rejeitada e um retry;
isso é conhecido e aceito.

## 5. Meça antes de gastar cota

```bash
hermes -p participant prompt-size --platform cli --json
python3 scripts/workshop-eval.py --help
```

O uso real de tokens no provedor é o dato autoritativo. O limite rígido do
Groq free tier é **8.000 tokens por requisição**; acima disso a API responde
413, não apenas 429.

## 6. Tarefa limitada — copie e cole **uma vez**

```
Execute exatamente uma chamada de terminal com este comando: uname -m; free -h; df -h "$HOME". Resuma arquitetura, RAM e disco em uma frase e pare. Não leia arquivos antes de executar.
```

Depois da resposta, pare. Para instalar, abra uma **sessão nova** com o comando
aprovado pelo operador. Nunca repita um comando com efeito colateral após
timeout: verifique primeiro o status, os logs e os arquivos já criados.

Se houver 429, espere o `Retry-After` (ou 45 s quando não houver cabeçalho).
Não faça requisições paralelas na mesma conta.

## 7. Pré-visualização e instalação offline (sem Hermes e sem internet)

No USB preparado, entre na pasta `repo-<REV>` e leia `START-HERE.txt`:

```bash
bash install.sh --offline --usb /ponto/de/montagem --mode safe --dry-run
bash workshop-install.sh --usb /ponto/de/montagem --dry-run
```

Só depois de aprovação humana explícita, no terminal do operador:

```bash
bash workshop-install.sh --usb /ponto/de/montagem   # pede sudo -v
# ou, separadamente:
bash install.sh --offline --usb /ponto/de/montagem --mode safe
bash install-stt.sh --usb /ponto/de/montagem
```

Verificação:

```bash
systemctl is-active edge-llm
curl --fail --silent http://127.0.0.1:8080/v1/models
python3 scripts/edge-task.py health
python3 scripts/edge-task.py pt 'The meeting is on Friday at nine.'
python3 scripts/edge-task.py en 'A reunião será sexta-feira.'
~/.local/bin/edge-transcribe -l pt -f amostra.wav
journalctl -u edge-llm -n 120 --no-pager
```

`scripts/edge-task.py` usa apenas a biblioteca padrão do Python e a API local;
não fala com nuvem e não envia áudio, transcrições ou saídas secretas.

## 8. Backup local limitado (facilitador)

O serviço local do laptop com o modelo LFM3 mesclado serve apenas como
ajudante **limitado e offline**. Verifique sem alterá-lo:

```bash
curl --fail --silent http://127.0.0.1:8080/v1/models
```

Para uma pergunta curta, use orçamento de raciocínio zero; caso contrário o
modelo gasta todo o `max_tokens` em `reasoning_content` e devolve conteúdo vazio:

```bash
curl -fsS -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"lfm3-harbor-hermes","messages":[{"role":"user","content":"Reply with exactly: PONG"}],"max_tokens":40,"reasoning_effort":"none","chat_template_kwargs":{"reasoning_budget":0}}'
```

Não prometa instalação autônoma multietapa nesse modelo. Não interrompa o
gateway nem o serviço em execução.

## 9. Failover (não habilitado por padrão)

Cloudflare Workers AI é a próxima opção óbvia, mas **não há credenciais
fornecidas**: permanece DESABILITADO e não verificado. OpenRouter também
permanece desabilitado até existir um modelo `:free` com capacidade de
ferramentas, ZDR e proibição de treinamento verificados. Nunca habilite uma
rota paga ou não testada. O modelo 20B do Groq usa a mesma cota da conta e
**não** é um backup independente.

## 10. Recuperação rápida

- **413 Request too large:** reduza o prompt; confirme que a skill não foi
  carregada automaticamente em tarefa de terminal.
- **429:** respeite `Retry-After`; 45 s entre tentativas; sem paralelismo.
- **`exec format error` em ARM64:** binfmt/QEMU ausente no host; não registrado
  sem aprovação; use a CLI direta do USB no alvo.
- **Porta 8080 ocupada:** não pare o serviço automaticamente; investigue
  `ss -ltnp | grep ':8080'`.
- **CPU não suportada:** a instalação offline falha fechada; use apenas Pi 5,
  N95/N97 ou Ryzen 8945HS/K11.
- **Timeout:** não repita o comando; verifique logs, checkpoints e estado antes
  de continuar.
- **Resposta vazia nos modelos USB:** use `reasoning_effort: none` (ou
  `chat_template_kwargs.enable_thinking: false`) nos Qwen3.5; `reasoning_budget: 0`
  **não** funciona neles. No LFM3 local, use `reasoning_budget: 0`. Avalie sempre
  o `content` final, nunca o `reasoning_content`.

Nenhum segredo deve ser colado neste guia, no USB, no repositório ou em logs
enviados a provedores de nuvem.
