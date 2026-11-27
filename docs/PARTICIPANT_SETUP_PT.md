# Guia do participante — configuração mínima (pt-BR)

Este guia não contém chaves nem segredos. O operador configura as credenciais
privadamente no ambiente da própria máquina.

## 1. Verifique a versão do Hermes

```bash
hermes --version
hermes profile create --help
```

Use apenas flags existentes na versão instalada.

## 2. Crie um perfil novo e isolado

```bash
hermes profile create workshop --no-skills
```

Nunca sobrescreva um perfil existente. O perfil fica em `~/.hermes/profiles/workshop/`.

## 3. Instale apenas a skill revisada

```bash
hermes -p workshop skills install \
  https://github.com/luandro/edge-llm-autoinstall/raw/main/SKILL.md --yes
```

Não instale todas as skills do pacote. O `SKILL.md` é curto; os detalhes ficam
em `references/` e são carregados somente quando necessário.

## 4. Mescle a configuração enxuta (com backup)

```bash
cp ~/.hermes/profiles/workshop/config.yaml ~/.hermes/profiles/workshop/config.yaml.bak
# Mescle config/workshop-lean.yaml no config.yaml do perfil workshop.
hermes -p workshop config get model
```

A configuração deve manter: `terminal` como única toolset da CLI, sem plugins,
sem MCP, sem memória, no máximo 6 turnos. Se o provedor for Groq, use
`provider: custom`, `base_url: https://api.groq.com/openai/v1`,
`api_key: ${GROQ_API_KEY}` (a chave fica apenas no `.env`). O operador deve
habilitar e verificar o ZDR no console do Groq.

## 5. Meça o prompt (sem chamar a API)

```bash
hermes -p workshop prompt-size --platform cli --json
```

O uso real de tokens é o dado autoritativo. Meta: menos de 3.000 tokens de
entrada na primeira chamada, uma chamada de terminal e duas requisições ao
modelo para uma tarefa simples de hardware. Correção vem antes de números.

## 6. Tarefa única e limitada (copie e cole uma vez)

```
Execute exatamente uma chamada de terminal com este comando: uname -m; free -h; df -h "$HOME". Resuma arquitetura, RAM e disco em uma frase e pare. Não leia arquivos antes de executar.
```

Depois de uma resposta, pare. Para instalar, use uma sessão nova e o comando
aprovado pelo operador. Nunca repita um comando com efeito colateral após timeout;
verifique primeiro o status e os logs.

## 7. Se não houver internet

Use a CLI direta do USB, sem Hermes e sem nuvem:

```bash
python3 scripts/edge-task.py health
bash workshop-install.sh --usb /ponto/de/montagem --dry-run
```

Somente depois de aprovação humana, execute o mesmo comando sem `--dry-run` no
terminal do operador (com sudo, se necessário). Não envie áudio, transcrições,
credenciais nem saídas secretas de shell para nenhum provedor de nuvem.
