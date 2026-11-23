# **Arquitetura de IA Offline para o GMKtec K11 (Ryzen 9 8945HS / Radeon 780M / 32 GB)**

Para o edge-llm-autoinstall no GMKtec K11 (AMD Ryzen 9 8945HS, Radeon 780M gfx1103, 32 GB DDR5-4800 partilhados, SSD NVMe de 1 TB, Linux), a pilha mais fiável e reprodutível combina **llama.cpp compilado a partir do *upstream* com *backend* Vulkan (Mesa RADV)** para modelos de linguagem, **ONNX Runtime / sherpa-onnx ou faster-whisper INT8 em CPU (-t 8\)** para STT pt-BR e **CTranslate2 INT8 em CPU** para tradução EN→PT de baixa latência. Nos modelos médios e grandes (26B–35B+), as arquiteturas **MoE esparsas** (3B–4B de parâmetros ativos) são as únicas opções capazes de manter débito interativo (21,96–25,10 tok/s medidos em gfx1103 com DDR5-5600, estimados em 18,82–21,51 tok/s a DDR5-4800), enquanto modelos densos de grande porte como o Qwen3.8-27B colapsam para 4,29 tok/s medidos (\~3,68 tok/s estimados a DDR5-4800). Em \--mode safe, o Gemma 4 E4B (Q4\_K\_M, \~4,8 GiB) funciona dentro do limite GTT por omissão (\~16 GiB) em residência simultânea com STT e tradução (\~10,2 GiB totais); em \--mode best, o Gemma 4 26B-A4B (Q4\_K\_M, \~16,5 GiB) ou o Qwen3.6-35B-A3B (\~19,5–21,5 GiB) exigem orquestração *on-demand* por fases e aumento opcional (*opt-in*) de ttm.pages\_limit para 22–24 GiB.  
Quatro condicionantes de evidência e licenciamento balizam todas as decisões deste relatório. Primeiro, os anexos indicados no enunciado (edge-llm-autoinstall.zip com install.sh, README.md, docs/K11.md e testes, bem como Edge AI for Constrained Hardware.pdf) não estiveram disponíveis para inspeção, e o repositório https\://github.com/tomasastary/llama-amd-alpine encontrava-se inacessível; consequentemente, a auditoria ao comportamento atual do instalador, eventuais IDs quebrados no código existente e dados de referência em Pi 5/N95/N97 ficam marcados como **não verificados**, e os patches propostos devem ser revistos manualmente antes da fusão. Segundo, não foram localizadas medições públicas diretas num GMKtec K11 equipado exatamente com DDR5-4800: todas as estimativas para DDR5-4800 derivam por escala de largura de banda (4800/5600 \= 0,8571) de testes comunitários em outras máquinas Radeon 780M (e notando que várias unidades de retalho do K11 vêm com 2×16 GB DDR5-5600). Terceiro, os modelos Parakeet pt-BR afinados no conjunto de dados **TAGARELA** herdam a licença não comercial **CC BY-NC-SA 4.0** do *corpus* original apesar de listarem CC BY 4.0 nos metadados do Hugging Face. Quarto, o Inkling 2 Mini lidera *benchmarks* de código em inglês segundo o fornecedor, mas declara fraco desempenho multilingue e regista elevada propensão para alucinação factual.

## **Auditoria de Riscos e Configurações Inválidas na Radeon 780M**

Embora o código original de install.sh não tenha podido ser inspecionado, a análise de falhas reais documentadas na Radeon 780M (gfx1103) identifica sete armadilhas que o instalador deve bloquear de forma determinística antes de descarregar modelos ou iniciar serviços:

> 1. **Memória *single-channel* em mini PCs:** A ausência de um segundo módulo SODIMM corta a largura de banda DDR5 para metade (de 76,8 GB/s para 38,4 GB/s teóricos em DDR5-4800). Numa máquina 780M real com um único módulo DDR5-5600 analisada em relatório técnico independente (k8s.it), a geração em GPU num modelo de \~7 GB caiu para \~4,5 tok/s, ficando abaixo dos \~5,3 tok/s em CPU.  
> 2. **Pacotes llama.cpp desatualizados de distribuição (ex. *build* 8681):** Em testes controlados do projeto amd-ryzen-inference-testing (780m.md), o *build* 8681 de distribuição falhou ao carregar Gemma 4 E2B/E4B (missing tensor 'blk.24.attn\_k.weight'), sofreu perda de 10–80× com *KV cache* de tipos mistos, ignorou descodificação especulativa MTP/EAGLE3 e foi 28–41% mais lento em *prefill* face ao *upstream* (build 12020).  
> 3. **Falhas de alocação Vulkan em Mesa antigo, contentores ou AMDVLK:** No *issue* \#12695 da Unsloth (Linux Mint 22.3, Mesa 25.2.8, llama.cpp b11160 em contentor Docker unsloth-rocm:studio), o Vulkan falhou com vk::Device::allocateMemory: ErrorOutOfDeviceMemory a partir de \--gpu-layers 3 em Qwen3.5-4B-UD-Q4\_K\_XL.gguf e em \--gpu-layers 99 em gemma-4-E4B-it-Q4\_K\_M.gguf, apesar de reportar 15 170 MiB livres. Adicionalmente, o *driver* Vulkan AMDVLK impõe um limite de 2 GiB por *buffer*, bloqueando o carregamento de modelos grandes. O instalador deve exigir Mesa RADV nativo atualizado (ex. Mesa 26.0.8+).  
> 4. **Timeout da fila Vulkan em contexto ≥16K com \-ub 512:** Na Radeon 780M (780m.md), o valor por omissão \-ub 512 ao processar 2048 tokens sobre 16K de contexto excedeu o tempo limite de *compute* do amdgpu (ring comp\_1.1.0 timeout no *kernel* e vk::DeviceLostError); alterar para \-ub 256 resolveu o bloqueio.  
> 5. **Contenção de SMT em CPU (-t 16 vs \-t 8):** No Ryzen 780M/8945HS (8 núcleos / 16 *threads*), correr inferência em CPU com 16 *threads* faz as *hyperthreads* competirem pelos mesmos núcleos físicos e controlador de memória, tornando a execução 2–3× mais lenta do que com \-t 8\.  
> 6. **Incompatibilidade de licenças em TAGARELA e NLLB:** As exportações ONNX alefiury/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx e sandovs/...-onnx-q4 exibem cc-by-4.0 no cartão, mas derivam de freds0/TAGARELA, cuja licença de origem é **CC BY-NC-SA 4.0**. O modelo facebook/nllb-200-distilled-600M impõe igualmente restrição não comercial.  
> 7. **NPU XDNA1 e CUDA:** Não existe *runtime* Linux funcional para executar LLMs na NPU XDNA1 (o FastFlowLM suporta apenas XDNA2/Strix+), e qualquer *stack* CUDA (como NInfer-all CUDA) é incompatível com a arquitetura AMD gfx1103.

## **Comparação de Motores de Inferência na Radeon 780M**

Para a execução de LLMs no GMKtec K11, a decisão técnica situa-se entre o **llama.cpp *upstream* com Vulkan (Mesa RADV)**, o **ROCm/HIP (gfx1103)** e a **execução em CPU**, apoiados por **ONNX Runtime** e **CTranslate2** para STT e tradução neuronal clássica.  
Na comparação direta mais rigorosa disponível para gfx1103 (Discussão \#32165 do llama.cpp, executada em Ryzen 7 255 com 128 GB DDR5 *dual-channel*, Ubuntu 24.04 LTS, *kernel* HWE 7.0.0-43-generic, Mesa RADV e llama.cpp b12323.24), o **Vulkan RADV** demonstrou o melhor compromisso entre velocidade de resposta e estabilidade operacional. Num modelo MoE de 35B (Cyber-Tiel-Coder-35B-A3B-MTP-UD-Q4\_K\_S.gguf, \~21,3 GB, *prompt* de 6845 tokens), o Vulkan superou o ROCm 7.2.4 na geração de tokens (*decode*) entre 9,5% e 31,9%: atingiu **21,96 tok/s** com ubatch=2048 e KV q8\_0 contra **16,72 tok/s** no ROCm, e **20,20 tok/s** contra **18,45 tok/s** com KV f16 e HSA\_ENABLE\_SDMA=0. No modelo denso Qwen3.8-27B (Q4\_K\_M, 6618 tokens), o Vulkan manteve igualmente vantagem marginal tanto no *prefill* (98,15 vs 94,89 tok/s) como no *decode* (4,29 vs 4,14 tok/s), além de concluir o carregamento de MiniMax-M3.1-Flash-90B (UD-IQ2\_XXS-E89) onde o ROCm sofreu reinício do *driver* amdgpu.  
O **ROCm/HIP** apresenta vantagem na velocidade de ingestão de *prompt* (*prefill*) em modelos MoE: com rocWMMA Flash Attention (-DGGML\_HIP\_ROCWMMA\_FATTN=ON), HSA\_OVERRIDE\_GFX\_VERSION=11.0.0 e HSA\_ENABLE\_SDMA=0, o ROCm 7.2.4 bateu o Vulkan em \+17,5% a \+21,7% no *prefill* de modelos MoE (426,60 vs 359,35 tok/s em Cyber-Tiel-Coder-35B-A3B) e igualou praticamente o *decode* quando usado com cabeçalho draft-mtp (24,29 vs 25,10 tok/s no Vulkan). Todavia, dois fatores desaconselham o ROCm num instalador automático de produção. Em ROCm 7.2.4, a falta de bibliotecas TensileLibrary oficiais para gfx1103 obriga a falsificar o alvo (HSA\_OVERRIDE\_GFX\_VERSION=11.0.0), instalar com \--no-dkms e editar /etc/ld.so.conf.d/20-amdgpu.conf para não corromper o Mesa/libdrm do *kernel* 7.0. Por sua vez, a atualização do llama.cpp para o ROCm 7.14 (que adicionou o alvo gfx1103, ausente nos binários pré-compilados) levou utilizadores no r/LocalLLaMA a reportar falhas frequentes em tarefas reais e conflitos entre amdgpu.gttsize e GGML\_CUDA\_ENABLE\_UNIFIED\_MEMORY=1, obrigando à remoção de parâmetros GTT.

| Motor / Backend | Suporte gfx1103 | Prefill Relativo | Decode Relativo | Estabilidade & Longo Contexto | Manutenção | Recomendação K11 |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **llama.cpp *upstream* \+ Vulkan (Mesa RADV)** | Nativo | Bom (328–360 tok/s em 35B MoE) | Mais rápido s/ MTP; 25,10 tok/s c/ MTP | Estável com \-ub 256 em 16K+; requer Mesa recente | Baixa (compilação simples) | **Padrão do instalador** |
| **llama.cpp ROCm 7.2.4 (rocWMMA)** | Requer HSA\_OVERRIDE\_GFX\_VERSION=11.0.0 | \+18–22% em MoE vs Vulkan | 10–32% inferior s/ MTP; 24,29 tok/s c/ MTP | *Crash* amdgpu em IQ2\_XXS; sensível a SDMA=0 | Alta (conflitos ld.so e DKMS) | **Apenas avançado / experimental** |
| **llama.cpp ROCm 7.14 nativo** | Compilação manual (gfx1103) | \+50% em densos (relato único) | Sem ganho claro em MoE | *Crashes* frequentes e conflito com gttsize | Muito alta | **Não recomendar** |
| **llama.cpp Vulkan AMDVLK** | Nativo | Muito rápido | Não verificado | Limite de 2 GiB por *buffer* impede modelos grandes | Média | **Evitar** |
| **llama.cpp CPU-only (-t 8, AVX-512 BF16)** | Universal | Lento face à iGPU | Supera iGPU em *single-channel* | Excelente; sem limite de GTT | Mínima | **Fallback automático** |
| **Ollama (Vulkan 0.22.1+ / ROCm)** | Funciona via Vulkan ou gfx1102 | Bom no *bundle* ROCm | Sem controlo fino de ubatch/MTP/router | Formatos internos nem sempre portáveis | Baixa | **Não usar no núcleo** |
| **Strata 0.2.9 / ik\_llama.cpp / OpenVINO** | Strata testado em ROCm 10.1; outros **não verificados** | \~371–388 tok/s (Strata Q2\_0+MTP) | \~21,0–21,2 tok/s (Strata) | ik\_llama.cpp e OpenVINO sem testes gfx1103 | Alta | **Não verificado / Excluir** |

Na componente CPU, o llama.\[span\_31\](start\_span)\[span\_31\](end\_span)cpp compilado com suporte nativo (AVX-512 BF16) e limitado a **\--threads 8** constitui o *fallback* ideal caso /dev/dri esteja inacessível, o Vulkan falhe ou o sistema tenha apenas um módulo de RAM. Para áudio e tradução neuronal clássica, **ONNX Runtime** (CPU) e **CTranslate2 INT8** (CPU) executam sem disputar a fila gráfica Vulkan da iGPU.

## **Restrições de Memória, Largura de Banda e Térmica do K11**

Na Radeon 780M sem VRAM dedicada, a velocidade de geração (*decode*) é estritamente limitada pela largura de banda da memória DDR5. Em configuração *dual-channel* (2 canais × 8 bytes por transferência), a especificação **DDR5-4800** fornece **76,8 GB/s teóricos** (cerca de **57,6 GB/s efetivos** assumindo 75% de utilização realista da iGPU/UMA), ao passo que sistemas **DDR5-5600** oferecem **89,6 GB/s teóricos** (\~67,2 GB/s efetivos). O rácio de largura de banda entre DDR5-4800 e DDR5-5600 é de 0,8571 (−14,3%). Aplicando este fator a medições comunitárias de referência em gfx1103 (que frequentemente utilizam DDR5-5600, embora a Discussão \#32165 registe "128 GB Dual-Channel DDR5" sem indicar o *clock* exato), os 21,96–25,10 tok/s de um MoE 35B-A3B (Q4\_K\_S) escalam para **\~18,82–21,51 tok/s** estimados em DDR5-4800, e os 25,00 tok/s reportados para Gemma 4 26B-A4B escalam para **\~21,43 tok/s** (sujeito à confirmação do *clock* real de RAM dessa submissão no llamaperf). Em *single-channel*, a banda DDR5-4800 cai para **38,4 GB/s** teóricos.  
Nos 32 GiB partilhados do K11, a interação entre BIOS UMA, limite GTT e reserva do sistema operativo define o teto seguro de carregamento:

> * **Carve-out BIOS UMA:** Deve manter-se no mínimo (**512 MiB a 2 GiB**). Reservas estáticas maiores na BIOS imobilizam RAM que o CPU necessita para STT, CTranslate2 e caches do sistema.  
> * **Limite GTT (ttm.pages\_limit):** Por omissão, o *kernel* Linux restringe o GTT a \~50% da RAM (\~15–16 GiB num equipamento de 32 GiB). Isso acomoda perfeitamente todos os modelos do perfil \--mode safe, mas impede modelos de 16–22 GiB em GPU. O teto pode ser elevado opcionalmente em páginas de 4 KiB: **20 GiB \= 5242880 páginas** (20480 MiB), **22 GiB \= 5767168 páginas** (22528 MiB) e **24 GiB \= 6291456 páginas** (24576 MiB, medido no *kernel* 7.0 a expor 25 769 803 776 bytes).  
> * **Reserva de SO, despejo (*eviction*) e *swap*:** Contando \~2,5 GiB para o Linux *headless* e \~2,5 GiB de margem de segurança, sobram \~27 GiB úteis totais. Como permanece em aberto na comunidade 780M se o *kernel* 7.0 sobrevive de forma estável sob pressão extrema perto de 24 GiB de GTT em máquinas de 32 GiB, **22 GiB é o limite prudente para 26B MoE**, devendo reservar-se **24 GiB** apenas para perfis de 35B-A3B com carregamento exclusivo (*on-demand*) e monitorização de estabilidade. O *swap* em SSD nunca deve servir para acomodar pesos de GPU (usar apenas zram leve para páginas ociosas do SO).

| Modelo / Quantização | Peso Estimado (GiB) | KV 16K Q8 \+ Buffers (GiB) | Total llama.cpp (GiB) | Total Sistema *On-Demand* (GiB) | Total Tudo Residente c/ STT+NMT (GiB) | Cabe em GTT Padrão (\~16 GiB)? |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| Gemma-4-E4B-it (Q4\_K\_M) | \~4,8 | \~1,3 | \~6,1 | \~8,6 | \~10,2 | **Sim** |
| Qwen3.5-9B (Q4\_K\_M) | \~5,6 | \~1,4 | \~7,0 | \~9,5 | \~11,1 | **Sim** |
| gpt-oss-20b (MXFP4/Q4) | \~12,1 | \~1,6 | \~13,7 | \~16,2 | \~17,8 | **Sim** (no limite a 16K) |
| Inkling-2-Mini (Q4\_K\_M) | \~15,8 | \~1,4 | \~17,2 | \~19,7 | \~21,3 | Não (requer ≥20 GiB GTT) |
| Gemma-4-26B-A4B-it (Q4\_K\_M) | \~16,5 | \~1,6 | \~18,1 | \~20,6 | \~22,2 | Não (requer ≥20–22 GiB GTT) |
| Qwen3.8-27B (Q4\_K\_M) | \~16,8 | \~2,0 | \~18,8 | \~21,3 | \~22,9 | Não (requer ≥22 GiB GTT) |
| Qwen3-Coder-30B-A3B (Q4\_K\_M) | \~18,6 | \~1,8 | \~20,4 | \~22,9 | \~24,5 | Não (requer ≥22–24 GiB GTT) |
| Qwen3.6-35B-A3B (Q4\_K\_S/IQ4\_XS est.) | \~19,5 | \~1,6 | \~21,1 | \~23,6 | \~25,2 | Não (requer 24 GiB GTT \+ *on-demand*) |
| Qwen3.6-35B-A3B (Q4\_K\_M) | \~21,5 | \~1,6 | \~23,1 | \~25,6 | \~27,2 | Não (margem crítica em 32 GiB) |

No plano de afinação térmica e parâmetros de inferência, o K11 opera com TDP base de 35 W configurável até 70 W na BIOS, tendendo a estabilizar no limite térmico sustentado durante sessões longas (guias de mini PCs apontam perda de frequência na Radeon 780M acima de 85 °C). O descarregamento total em GPU (--n-gpu-layers 99\) é preferível sempre que o modelo couber em GTT, recorrendo ao descarregamento parcial ou a CPU (-t 8\) caso falhe o limite GTT. Nos *flags* do llama.cpp *upstream*, é essencial ativar \[span\_106\](start\_span)\[span\_106\](end\_span)\[span\_108\](start\_span)\[span\_108\](end\_span)--flash-attn on (+11% a \+86% a 8K de contexto), \--cache-type-k q8\_0 \--cache-type-v q8\_0 (reduz a memória KV para metade sem perda de velocidade mensurável em Vulkan *upstream*) e **\-ub 256** em janelas de 16K–32K para prevenir *timeouts* de GPU. Quanto à descodificação especulativa, cabeçalhos **MTP nativos** trazem ganhos consistentes em *upstream* com \--spec-type draft-mtp (Gemma 4 E4B \+ MTP atingiu 2,47× / 58 tok/s em 780m.md, e Cyber-Tiel-Coder-35B-A3B subiu de 20,20 para 25,10 tok/s em Vulkan na Discussão \#32165), ao passo que modelos *draft* externos ou EAGLE3 em MoE **reduziram** o rendimento (Qwen3-30B-A3B \+ 0.6B \= 0,75×; gpt-oss-20b \+ EAGLE3 \= 0,77×).

## **Avaliação dos Modelos de Linguagem (LLMs)**

A verificação de repositórios reais, tamanhos, licenças e comportamento em gfx1103 separa claramente os candidatos MoE viáveis dos modelos densos lentos ou com restrições funcionais.  
Entre os candidatos principais para **\--mode best**, o **Qwen3.6-35B-A3B** (unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4\_K\_M e lmstudio-community/Qwen3.6-35B-A3B-GGUF, Apache 2.0) combina 35B parâmetros totais e 3B ativos (256 peritos, 8 encaminhados \+ 1 partilhado, 30 camadas Gated DeltaNet \+ 10 Gated Attention, contexto de 262K, capacidades multimodais, MTP nativo e retenção de raciocínio preserve\_thinking para agentes). O blogue do fabricante reporta 75,0% no SWE-bench Verified. Contudo, os únicos resultados comunitários para o Qwen3.6-35B-A3B na 780M no llamaperf correspondem a 8 bits (18,4–19,7 tok/s de *decode*, 311,4 tok/s de *prefill*), cujo ficheiro Q8\_0 ocupa 36,9 GB e não cabe em 32 GB; além disso, utilizadores no Hugging Face relataram respostas mais verbosas e maior taxa de erro em alguns testes no UD-Q8\_K\_XL face ao Qwen3.5. Em 32 GB, exige UD-Q4\_K\_M (\~21,5 GiB) ou uma quantização menor (\~19,5 GiB) com 24 GiB GTT e execução *on-demand*. Usando o Cyber-Tiel-Coder-35B-A3B-MTP (UD-Q4\_K\_S, \~21,3 GB) da Discussão \#32165 como referência arquitetural próxima de 35B-A3B em Vulkan, espera-se \~18,8–21,5 tok/s em DDR5-4800.  
O **Gemma 4 26B-A4B** (lmstudio-community/gemma-4-26B-A4B-it-GGUF, Apache 2.0, 26B totais / 4B ativos, 256K de contexto) oferece uma folga de memória superior em 32 GB (\~16,5 GiB em Q4\_K\_M, \~20,6 GiB totais *on-demand*, cabendo em 20–22 GiB de GTT). Um registo comunitário único no llamaperf em Radeon 780M (Q4\_K\_M) obteve **25,0 tok/s de geração e 208,7 tok/s de *prefill*** (\~21,43 tok/s estimados em DDR5-4800 se a origem for DDR5-5600). Falta, porém, auditoria empírica à sua qualidade em pt-BR e à sua fiabilidade agêntica, uma vez que noutros testes de programação o Gemma 4 31B apresentou desempenho baixo (14,2% no SWEBench Pro v2 Hard).  
Para **\--mode safe**, o **Gemma 4 E4B** (unsloth/gemma-4-E4B-it-GGUF:gemma-4-E4B-it-Q4\_K\_M.gguf, \~4,8 GiB, 128K de contexto) é o único modelo verificado em medições na Radeon 780M (780m.md, *build* 12020\) com aceleração MTP operacional, atingindo **58 tok/s** (2,47× sobre o base) em 32 GB DDR5. Cabe confortavelmente dentro do limite GTT por omissão. O **Qwen3.5-9B** (\~5,6 GiB em Q4\_K\_M) e o **gpt-oss-20b** (\~12,1 GiB em MXFP4/Q4) também cabem nos 16 GiB GTT padrão (este último no limite a 16K), mas o Qwen3.5-9B não dispõe de medições na 780M nas fontes recolhidas e o gpt-oss-20b sofreu penalização de velocidade com EAGLE3 (0,77× em 780m.md), ficando ambos como opções secundárias não verificadas para qualidade pt-BR.  
Nos modelos **especializados e densos**, as restrições são severas. O **Qwen3.8-27B** (Qwen/Qwen3.8-27B, denso, suporte a reasoning\_effort e recomendação oficial de temperature=0.7, top\_p=0.80, top\_k=20, presence\_penalty=1.5 no modo *non-thinking*) fica bloqueado pelo barramento de memória: mediu **4,29 tok/s** (Q4\_K\_M, 6618 tokens) na Discussão \#32165 (\~3,68 tok/s estimados em DDR5-4800) e 5,1–8,3 tok/s num portátil 32 GB reportado no llamaperf, sendo demasiado lento para agentes ou chat. O **Inkling 2 Mini** (unsloth/Inkling-2-Mini-GGUF, Apache 2.0, lançado em novembro de 2026; 26,4B totais / 3,4B ativos físicos em *looped transformer* de 24 camadas com bloco central repetido 3 vezes; \~15,8 GiB em Q4\_K\_M) atinge 79,2% no SWEBench Verified segundo o cartão do fornecedor e análises secundárias. Contudo, o cartão oficial indica que **não é forte em línguas além do inglês**, regista **63,4% de taxa de não-alucinação** e índice negativo AA-Omniscience (−8,6) na avaliação da Artificial Analysis, atinge apenas 33,4% no ComplexConstraints v1.1, e o seu comportamento em llama.cpp Vulkan na 780M é **não verificado**. O **Qwen3-Coder-30B-A3B** (\~18,6 GiB Q4\_K\_M) carece de dados completos em 780M (apenas um registo de *draft* 0.6B negativo em 780m.md), enquanto a poda **ManniX-ITA/Qwen3.6-27B-A3B-Coder-MTP-GGUF** (184 peritos, *top-10*) mantém 90% em saída estruturada e 100% em precisão de parâmetros, mas cai para 40,0% em planeamento autónomo de longo horizonte. Por fim, o **LFM2.5-24B-A2B** (\~37 tok/s a contexto zero no llamaperf sem quantização nem qualidade pt-BR verificadas) e o **Flint-MoE 40B-A2.5B** (23,80 tok/s em Vulkan na Discussão \#32165, demasiado próximo do teto de 32 GB) permanecem fora da seleção principal.

## **Reconhecimento de Fala pt-BR (STT) e Auditoria de Licenças**

Para transcrição offline em português do Brasil em áudios de 10 a 60 minutos, os motores em **CPU INT8** evitam competir pela memória GTT da iGPU ou funcionam na primeira etapa de um *pipeline* sequencial. O candidato de maior precisão específica em pt-BR é o **Parakeet TDT 0.6B v3 pt-BR TAGARELA** em formato ONNX INT8, disponível para onnx-asr (alefiury/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx, \~0,67 GB em encoder-model.int8.onnx \+ decoder\_joint-model.int8.onnx) e para sherpa-onnx (joaorura/parakeet-tdt-0.6b-v3-ptBR-sherpa-onnx-int8, 671 MB totais com encoder.int8.onnx, decoder.int8.onnx, joiner.int8.onnx e tokens.txt). Derivado do *checkpoint* alexandreacff/parakeet-tdt-0.6b-v3-ptBR-plus com pontuação, o modelo FP32 reporta no seu cartão WER de 0,137 e 0,213 entre o conjunto privado e a média de *corpora* de fala espontânea brasileira (ALIP, C-ORAL Brasil I, NURC-Recife, SP2010, NURC-SP e MuPe), e o artigo do TAGARELA reporta 15,18% WER / 7,09% CER para o Parakeet v2 *Fine-Tuned* face a Whisper Large V3 e Distil-Whisper. Contudo, a auditoria jurídica revela que o *corpus* freds0/TAGARELA (8972 horas de *podcasts*) está licenciado sob **CC BY-NC-SA 4.0**. Os metadados cc-by-4.0 dos repositórios ONNX derivados não invalidam a restrição não comercial a montante; por isso, este modelo deve ser instalado apenas mediante aceitação explícita de \--non-commercial.  
Para implantações comerciais limpas (--mode safe), as alternativas recomendadas são o **faster-whisper INT8** (CTranslate2) / **whisper.cpp INT8** (MIT) e o **Parakeet TDT 0.6B v3 base multilingue** em ONNX INT8 (CC-BY-4.0). O faster-whisper apresenta pontuação estável e boa tolerância a *code-switching* inglês/português em termos técnicos, enquanto o Parakeet base tende a oferecer menor latência em CPU, embora não existam medições de *Real-Time Factor* (RTF) nem de WER INT8 em fala espontânea de 10–60 minutos especificamente no Ryzen 9 8945HS (**não verificado**). Para gravações longas, qualquer motor escolhido deve ser precedido por **Silero VAD** para segmentar em blocos de 20–30 segundos sem perda de *timestamps*. Como opção experimental Apache 2.0, o **Qwen3-ASR** (ggml-org/Qwen3-ASR-1.7B-GGUF ou exportação baicai-1145/Qwen3-ASR-onnx, complementado pelo Qwen3-ForcedAligner-0.6B para *timestamps* em português) suporta 30 línguas, mas carece de *benchmarks* independentes de WER em pt-BR e de RTF na 780M.

## **Tradução EN para PT-BR e Sumarização em Português**

Na **tradução EN → PT-BR**, a escolha opõe determinismo em CPU à fluência idiomática brasileira em LLM. O modelo **gow-solucoes/opus-mt-en-pt-ct2** (conversão CTranslate2 INT8 de Helsinki-NLP/opus-mt-tc-big-en-pt, licença **CC-BY 4.0**) consome apenas \~0,4 GiB de RAM em CPU, reporta **BLEU 49,6** para en→pt na ficha de origem e elimina o risco de omissões ou acréscimos de conteúdo que ocorrem frequentemente quando LLMs traduzem documentos extensos. Representa a escolha \--mode safe de menor latência, exigindo validação prática no K11 porque o modelo base abrange português genérico (pt, podendo introduzir construções europeias) e sofre maior degradação se a pontuação gerada pelo STT for deficiente. O **facebook/nllb-200-distilled-600M** em CTranslate2 INT8 mantém boa qualidade multilingue, mas carrega licença não comercial; **Argos/Bergamot** não têm medições disponíveis no 8945HS (**não verificado**). Quando o orçamento de tempo e GTT permite (--mode best), a tradução via **Gemma 4 26B-A4B** ou **Qwen3.6-35B-A3B** adapta melhor terminologia técnica e registo pt-BR após STT ruidoso, devendo operar por blocos curtos para mitigar omissões.  
Na **sumarização de entrevistas, reuniões e textos longos em pt-BR**, nenhuma das fontes recolhidas avaliou objetivamente a retenção de datas, números, nomes próprios, decisões ou itens de ação na 780M (**não verificado**). Arquiteturalmente, atas acima de \~10K–16K tokens devem usar **map-reduce por blocos** de 4K–8K tokens sobre uma janela \-c 16384 com \-ub 256, mantendo o modelo em modo *non-thinking* (para impedir que o raciocínio consuma o orçamento de tokens e latência) e temperatura baixa (0,2–0,4) para ancoragem factual. Em \--mode safe, o Gemma 4 E4B fornece velocidade elevada (\~58 tok/s medidos na 780M com MTP) para rascunhos rápidos, enquanto em \--mode best o Gemma 4 26B-A4B e o Qwen3.6-35B-A3B são os candidatos prioritários para verificação de fidelidade factual no hardware físico.

## **Tabela Classificada por Carga de Trabalho**

As estimativas de velocidade para DDR5-4800 resultam da aplicação do fator de banda 0,8571 (4800/5600) apenas às medições onde o cálculo consta da investigação; onde a velocidade de RAM de origem não foi declarada ou faltam testes na 780M, o estado é explicitamente assinalado como **não verificado**.

| Carga de Trabalho | Nível | Modelo & ID / Ficheiro | Runtime | Licença | Memória Pico Est. (K11) | Prefill / Decode (Referência 780M → Est. DDR5-4800) | Notas & Condições |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **STT pt-BR** | **Best** (NC) | alefiury/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx INT8 ou joaorura/...-sherpa-onnx-int8 | onnx-asr\[span\_34\](start\_span)\[span\_34\](end\_span) / sherpa-onnx CPU (-t 8\) | **CC BY-NC-SA 4.0** (herdada de TAGARELA) | \~0,67 GB disco; \~1,2 GiB RAM | WER 0,137 / 0,213 (FP32); RTF 8945HS **não verificado** | Só instalar com \--non-commercial; usar Silero VAD. |
| **STT pt-BR** | **Safe** | faster-whisper / whisper.cpp INT8 ou Parakeet v3 base ONNX INT8 | CTranslate2 / onnx-asr CPU (-t 8\) | MIT (whisper) / CC-BY-4.0 (Parakeet base) | \~0,5–1,5 GiB RAM | RTF e WER pt-BR no 8945HS **não verificados** | Uso comercial limpo; boa tolerância a *code-switching*. |
| **STT pt-BR** | **Exp.** | ggml-org/Qwen3-ASR-1.7B-GGUF (+ Qwen3-ForcedAligner-0.6B) | llama.cpp / ONNX | Apache 2.0 | \~1,5–2,5 GiB (est.) | RTF e WER pt-BR em 780M **não verificados** | Suporta português e alinhamento. |
| **Tradução EN→PT** | **Best** | lmstudio-community/gemma-4-26B-A4B-it-GGUF (Q4\_K\_M) | llama.cpp Vulkan (-ub 256 \-fa on \-ctk q8\_0 \-\[span\_54\](start\_span)\[span\_54\](end\_span)ctv q8\_0) | Apache 2.0 | \~18,1 GiB (llama) / \~20,6 GiB sist. | llamaperf: 208,7 / 25,0 tok/s → **\~21,43 tok/s** est. | Requer 20–22 GiB GTT e validação pt-BR; traduzir por blocos para evitar omissões. |
| **Tradução EN→PT** | **Safe** | gow-solucoes/opus-mt-en-pt-ct2 INT8 (Helsinki-NLP/opus-mt-tc-big-en-pt) | CTranslate2 CPU INT8 | CC-BY 4.0 | \~0,4 GiB RAM | BLEU 49,6 (en→pt); latência 8945HS **não verificada** | Zero alucinações; cabe em GTT padrão; auditar variante pt-BR/pt-PT. |
| **Tradução EN→PT** | **Exp.** | facebook/nllb-200-distilled-600M (CT2 INT8) ou Gemma 4 E4B (Q4\_K\_M) | CT2 CPU / llama.cpp Vulkan | NLLB: **NC**; Gemma: ver HF | \~0,6–6,1 GiB | Gemma E4B c/ MTP: 58 tok/s (780m.md, clock DDR5 não indicado) | NLLB não comercial; qualidade pt-BR de E4B a testar. |
| **Sumarização PT** | **Best** | lmstudio-community/gemma-4-26B-A4B-it-GGUF (Q4\_K\_M) ou unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4\_K\_M | llama.cpp Vulkan (-c 16384 \-ub 256 \-fa on \-ctk q8\_0 \-ctv q8\_0) | Apache 2.0 | 18,1 GiB (26B) / 23,1 GiB (35B Q4\_K\_M) | Proxy 35B-A3B Q4\_K\_S (\#32165): 359,6 / 21,96 tok/s → **\~18,82 tok/s** est. | 35B exige 24 GiB GTT e *on-demand* estrito; 26B é mais seguro em 32 GiB; usar *map-reduce*. |
| **Sumarização PT** | **Safe** | unsloth/gemma-4-E4B-it-GGUF (gemma-4-E4B-it-Q4\_K\_M.gguf) | llama.cpp Vulkan (--spec-type draft-mtp) | Ver cartão HF | \~6,1 GiB (llama) / \~10,2 GiB resid. | **58 tok/s** c/ MTP (780m.md) | Residente com STT/NMT sem mexer no *kernel*; Qwen3.5-9B é alternativa **não verificada**. |
| **Sumarização PT** | **Exp.** | Qwen/Qwen3.8-27B (\[span\_59\](start\_span)\[span\_59\](end\_span)Q4\_K\_M GGUF) | llama.cpp Vulkan | Ver cartão HF | \~18,8 GiB (llama) / \~21,3 GiB *on-demand* | \#32165: 98,15 / 4,29 tok/s → **\~3,68 tok/s** est. (llamaperf: 5,1–8,3) | Modelo denso limitado pela banda; só para *batch* assíncrono. |
| **Código / Agentes** | **Best** | unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4\_K\_M (ou quantização \~19,5 GiB) | llama.cpp Vulkan (preserve\_think\[span\_73\](start\_span)\[span\_73\](end\_span)ing / MTP) | Apache 2.0 | \~21,1–23,1 GiB (llama) | Proxy 35B-A3B+MTP (\#32165): 329 / 25,10 tok/s → **\~21,51 tok/s** est. | 75,0% SWE-bench Verified (fabricante); requer 24 GiB GTT e descarregar STT/NMT. |
| **Código / Agentes** | **Safe** | unsloth/gemma-4-E4B-it-GGUF (Q4\_K\_M) ou lmstudio-community/gemma-4-\[span\_123\](start\_span)\[span\_123\](end\_span)26B-A4B-it-GGUF | llama.cpp Vulkan | Apache 2.0 (26B-A4B) | \~6,1 GiB (E4B) / \~18,1 GiB (26B) | 58 tok/s (E4B medido) / \~21,43 tok/s (26B est.) | Sem *tuning* GTT, usar E4B (ou testar gpt\[span\_180\](start\_span)\[span\_180\](end\_span)-oss-20b); Gemma 4 mostrou fragilidade em *benchmarks* agênticos. |
| **Código / Agentes** | **Exp.** | unsloth/Inkling-2-Min\[span\_75\](start\_span)\[span\_75\](end\_span)i-GGUF (Q4\_K\_M \~15,8 GiB / UD-IQ3\_XXS) ou ManniX-ITA/Qwen3.6-27B-A3B-Coder-MTP-GGUF | llama.cpp Vulkan | Apache 2.0 (Inkling) | \~17,2 GiB (Inkling Q4\_K\_M) | 780M Vulkan **não verificado** | Inkling: 79,2% SWE-Verified (fabricante), mas só inglês e 63,4% não-alucinação. |

## **Pipeline Offline e Arquitetura de Memória em 32 GB**

A comparação entre manter modelos residentes e alternar processos *on-demand* resolve-se pela fronteira dos 16 GiB de GTT por omissão. Em \--mode safe, a soma de Gemma 4 E4B (\~6,1 GiB), STT CPU INT8 (\~1,2 GiB), opus-mt-en-pt-ct2 (\~0,4 GiB) e sistema operativo (\~2,5 GiB) totaliza **\~10,2 GiB**, permitindo residência contínua sem alterações de *kernel* nem risco de *OOM*. Em \--mode best, Gemma 4 26B-A4B (\~18,1 GiB) ou Qwen3.6-35B-A3B (\~21,1–23,1 GiB) elevariam o consumo conjunto residente para **22,2–27,2 GiB**, deixando margem insuficiente para picos de *buffers* de áudio e *desktop*/SO. Por conseguinte, o modo best deve executar as etapas em série por detrás de uma única API local (127.0.0.1:8080, compatível com OpenAI) que descarrega o motor de cada fase antes de iniciar a seguinte, preservando *timestamps* em JSON e registando RSS, mem\_info\_gtt\_used, latência por etapa e códigos de erro em disco local.

| Etapa do Pipeline (127.0.0.1:8080) | Motor & Modo | Comportamento de Memória (safe vs best) | Artefactos & Registo Local |
| :---- | :---- | :---- | :---- |
| **1\. Áudio → VAD → STT** | ffmpeg (16 kHz mono) \+ Silero VAD \+ faster-whisper / Parakeet ONNX (-t 8\) | safe: permanece residente (\~1,2 GiB); best: suspende/descarrega LLM, processa segmentos de 20–30 s e liberta RSS | JSON com start\_ms, end\_ms, texto pt-BR/EN, RTF e RSS máximo |
| **2\. Tradução (opcional)** | opus-mt-en-pt-ct2 (safe) ou llama-server (best) | safe: residente (\~0,4 GiB); best: reutiliza fase LLM sem sobrecarga adicional | Frases traduzidas com start\_ms/end\_ms preservados |
| **3\. Sumarização / Chat** | llama-server (127.0.0.1:8081, Vulkan RADV, \-c 16384 \-ub 256 \-fa on \-ctk q8\_0 \-ct\[span\_6\](start\_span)\[span\_6\](end\_span)v q8\_0) | safe: residente (\~6,1 GiB); best: carregado *on-demand* (18,1–23,1 GiB) com *map-reduce* em \>10K tokens | Ata estruturada (decisões, datas, responsáveis) \+ registo mem\_info\_gtt\_used |

## **Instalação Verificada e Perfis de Serviço para Ubuntu/Debian**

Os passos seguintes aplicam-se a Ubuntu 24.04 LTS HWE / 26.04+ ou Debian recente com Mesa RADV atualizado, ligação restrita a 127.0.0.1 e execução totalmente *offline* após o descarregamento inicial dos pesos.

### **1\. Compilação Upstream do llama.cpp com Vulkan RADV**

`sudo apt-get update`  
`sudo apt-get install -y --no-install-recommends \`  
  `build-essential cmake git pkg-config curl jq ca-certificates \`  
  `mesa-vulkan-drivers libvulkan-dev vulkan-tools glslc \`  
  `ffmpeg python3-venv python3-pip dmidecode`

`sudo usermod -aG video,render "$USER"`

`git clone https://github.com/ggml-org/llama.cpp.git /opt/llama.cpp`  
`cmake -S /opt/llama.cpp -B /opt/llama.cpp/build \`  
  `-DGGML_VULKAN=ON \`  
  `-DGGML_NATIVE=ON \`  
  `-DLLAMA_BUILD_SERVER=ON \`  
  `-DCMAKE_BUILD_TYPE=Release`  
`cmake --build /opt/llama.cpp/build -j8 --target llama-server llama-cli llama-bench`  
`sudo ln -sf /opt/llama.cpp/build/bin/llama-server /usr/local/bin/llama-server`  
`sudo ln -sf /opt/llama.cpp/build/bin/llama-bench /usr/local/bin/llama-bench`

`# Confirmar deteção de "RADV PHOENIX" antes de prosseguir`  
`llama-server --list-devices`

### **2\. Ambiente Python CPU para STT e Tradução**

`python3 -m venv /opt/edge-ai/venv`  
`/opt/edge-ai/venv/bin/pip install --upgrade pip`

`# Pacote comercialmente limpo (--mode safe):`  
`/opt/edge-ai/venv/bin/pip install faster-whisper ctranslate2 sentencepiece huggingface_hub fastapi uvicorn soundfile`

`# Opcional apenas se o utilizador aceitar explicitamente licença NC do TAGARELA (--non-commercial):`  
`# /opt/edge-ai/venv/bin/pip install "onnx-asr[cpu,hub]" sherpa-onnx`

### **3\. Ajuste Opcional e Reversível de Memória GTT (--tune-gtt)**

Este passo nunca deve correr por omissão. Aplica-se apenas para \--mode best (22 GiB conservador \= 5767168 páginas de 4 KiB; ou 24 GiB \= 6291456 páginas para 35B-A3B). Na BIOS do K11, definir opcionalmente o *UMA Frame Buffer Size* para o mínimo (512M).  
`sudo tee /etc/modprobe.d/99-k11-gtt.conf >/dev/null <<'EOF'`  
`# Opcional para modelos 20B-35B MoE em 32 GiB K11 (22 GiB = 5767168; 24 GiB = 6291456)`  
`options ttm pages_limit=5767168 page_pool_size=5767168`  
`options amdgpu gttsize=22528`  
`EOF`  
`sudo update-initramfs -u`  
`# Após reiniciar, confirmar com: cat /sys/class/drm/card*/device/mem_info_gtt_total`

**Recuperação e *rollback*:** Se ocorrer erro de arranque ou instabilidade sob carga, no menu GRUB carregar em e, remover parâmetros ttm.pages\_limit/amdgpu.gttsize caso tenham sido adicionados à linha linux, arrancar e remover o módulo de configuração:  
`sudo rm -f /etc/modprobe.d/99-k11-gtt.conf`  
`sudo update-initramfs -u`  
`sudo reboot`

### **4\. Unidade systemd Local-Only**

Configuração base para \--mode safe em 127.0.0.1:8081 (no perfil best, apontar \--model para gemma-4-26B-A4B-it-Q4\_K\_M.gguf ou Qwen3.6-35B-A3B-UD-Q4\_K\_M.gguf e omitir \--spec-type draft-mtp caso o GGUF escolhido não inclua cabeçalho MTP):  
`# /etc/systemd/system/edge-llm.service`  
`[Unit]`  
`Description=Edge AI Local llama-server (Vulkan RADV)`  
`After=network-online.target`

`[Service]`  
`Type=simple`  
`User=edgeai`  
`Group=edgeai`  
`Environment=HOME=/var/lib/edge-ai`  
`Environment=HF_HUB_OFFLINE=1`  
`ExecStart=/usr/local/bin/llama-server \`  
  `--host 127.0.0.1 --port 8081 \`  
  `--model /var/lib/edge-ai/models/gemma-[span_49](start_span)[span_49](end_span)4-E4B-it-Q4_K_M.gguf \`  
  `--n-gpu-layers 99 \`  
  `--ctx-size 16384 \`  
  `--ubatch-size 256 \`  
  `--threads 8 \`  
  `--flash-attn on \`  
  `--cache-type-k q8_0 --cache-type-v q8_0 \`  
  `--spec-type draft-mtp`  
`Restart=on-failure`  
`RestartSec=5`

`[Install]`  
`WantedBy=multi-user.target`

## **Alterações Propostas ao edge-llm-autoinstall e CLI**

Para preservar integralmente a retrocompatibilidade com **Raspberry Pi 5** e **Intel N95/N97** sem ter acesso ao install.sh atual, a alteração mínima recomendada consiste em adicionar um único módulo lib/arch\_amd\_780m.sh, carregado exclusivamente quando /sys/class/drm ou lspci expõe o dispositivo Radeon 780M (0x15bf / gfx1103) com ≥24 GiB de RAM. O instalador mantém **uma única confirmação inicial**, vincula todos os serviços a 127.0.0.1 e não toca em parâmetros GTT sem a *flag* explícita \--tune-gtt.  
Na interface proposta para os argumentos \--task stt\|translate\|summarize\|chat\|pipeline e \--mode safe\|best, a seleção funciona por composição simples. O argumento \--task define os binários e rotas expostos pelo serviço local http\://127.0.0.1:8080/v1 (/audio/transcriptions para stt/pipeline e /chat/completions para translate/summarize/chat, com alternância automática entre estágios em pipeline quando \--mode best estiver ativo). Por sua vez, \--mode safe seleciona sempre Gemma 4 E4B \+ faster-whisper INT8 \+ opus-mt-en-pt-ct2 (comerciais e residentes dentro dos 16 GiB GTT padrão), enquanto \--mode best exige validação de *dual-channel* e mem\_info\_gtt\_total ≥ 20 GiB antes de aceitar Gemma 4 26B-A4B ou Qwen3.6-35B-A3B; caso falte GTT ou seja detetado *single-channel*, o instalador recusa o perfil pesado e retrocede automaticamente para safe com aviso legível.

## **Verificações Automatizadas, Guardas e Script de Benchmark**

O fluxo de instalação deve aplicar quatro controlos automáticos antes de ativar qualquer unidade systemd. Primeiro, **auditoria de hardware** via dmidecode \-t memory e mem\_info\_gtt\_total: se detetar apenas um módulo SODIMM ou menos de 20 GiB de GTT, bloqueia \--mode best e ativa safe ou CPU \-\[span\_42\](start\_span)\[span\_42\](end\_span)t 8\. Segundo, **guardas de armazenamento e integridade**: exige espaço livre mínimo igual a 1,5 × tamanho\_modelos \+ 10 GiB em /var/lib/edge-ai e valida SHA-256 de todos os ficheiros .gguf e .onnx descarregados. Terceiro, **verificação de saúde (*health check*) e *smoke test***: aguarda até 60 segundos por resposta 200 OK em http\://127.0.0.1:8081/health e envia um pedido de 32 tokens com *schema* de *tool call* mínimo. Quarto, ***rollback*** **automático**: se o serviço registar vk::Device::allocateMemory, vk::DeviceLostError ou código de saída OOM no journalctl, restaura a configuração anterior de systemd e reconfigura o serviço em CPU \-t 8\.

### **Script de Benchmark Reprodutível para o GMKtec K11**

Este script mede no K11 físico os valores atualmente estimados ou não verificados (llama-bench em 1K/4K/16K com \-ub 256, TTFT, *tool calling*, consumo GTT e estado térmico):  
`#!/usr/bin/env bash`  
`set -euo pipefail`  
`MODEL="${1:-/var/lib/edge-ai/models/gemma-4-E4B-it-Q4_K_M.gguf}"`  
`OU[span_85](start_span)[span_85](end_span)[span_89](start_span)[span_89](end_span)T="k11_bench_$(date +%Y%m%d_%H%M%S).log"`

`{`  
  `echo "=== HARDWARE, MEMÓRIA & KERNEL ==="`  
  `uname -r`  
  `vulkaninfo --summary 2>/dev/null | grep -E "deviceName|driverInfo" || true`  
  `cat /sys/class/drm/card*/device/mem_info_gtt_total || true`  
  `sudo dmidecode -t memory | grep -E "Size:|Speed:|Configured Memory Speed:" | head -n 12 || true`

  `echo "=== LLAMA-BENCH (1K, 4K, 16K com -ub 256 e -fa 1) ==="`  
  `llama-bench -m "$MODEL" -ngl 99 -t 8 -fa 1 -ctk q8_0 -ctv q8_0 \`  
    `-ub 256 -p 1024,4096,16384 -n 128 -r 3`

  `echo "=== SMOKE TEST TOOL-CALL & TTFT (127.0.0.1:8081) ==="`  
  `T0=$(date +%s%3N)`  
  `curl -sS http://127.0.0.1:8081/v1/chat/completions \`  
    `-H "Content-Type: application/json" \`  
    `-d '{`  
      `"model": "local",`  
      `"temperature": 0.2,`  
      `"max_tokens": 180,`  
      `"tools": [{"type":"function","function":{"name":"create_action_item","parameters":{"type":"object","properties":{"owner":{"type":"string"},"due":{"type":"string"},"task":{"type":"string"}},"required":["owner","task"]}}}],`  
      `"messages": [{"role":"user","content":"Em português (pt-BR), resume e regista a tarefa: Ana deve entregar o relatório até 2026-12-01."}]`  
    `}'`  
  `T1=$(date +%s%3N)`  
  `echo -e "\nLatency_ms=$((T1-T0))"`  
  `echo "GTT_used=$(cat /sys/class/drm/card*/device/mem_info_gtt_used | head -n1)"`  
`} | tee "$OUT"`

## **Plano de Testes no K11 Físico e Critérios de Aprovação**

Os ensaios seguintes exigem acesso físico ao GMKtec K11 e devem ser executados por ordem estrita de prioridade:

> 1. **Prioridade 1 — Verificação DDR5-4800 *Dual-Channel*, GTT 22–24 GiB e Estabilidade Térmica:** Confirmar *clock* e número de canais via dmidecode e executar 15 minutos contínuos de carga em Gemma 4 26B-A4B (Q4\_K\_M) e Qwen3.6-35B-A3B (UD-Q4\_K\_M) a 16K com \-ub 256\. **Critério de aprovação:** zero *resets* amdgpu no dmesg, zero vk::DeviceLostError e degradação térmica de tok/s ≤15% ao fim de 10 minutos.  
> 2. **Prioridade 2 — Medição Direta de *Useful Throughput* (4K–16K) e *Tool Calling*:** Medir *prefill*, *decode* e TTFT para Gemma 4 E4B (c/ MTP), Qwen3.5-9B, Gemma 4 26B-A4B e Qwen3.6-35B-A3B. **Critério de aprovação:** \--mode safe ≥20 tok/s *decode* e TTFT ≤3 s a 4K; \--mode best ≥14 tok/s *decode* e TTFT ≤12 s a 8K, além de ≥90% de chamadas JSON válidas em 10 testes de ferramentas.  
> 3. **Prioridade 3 — Benchmark STT pt-BR em Áudios de 10–30 Minutos:** Comparar faster-whisper INT8, Parakeet v3 base e Parakeet TAGARELA (não comercial) com Silero VAD em fala espontânea pt-BR com sotaques e anglicismos técnicos. **Critério de aprovação:** RTF ≤0,25 em CPU (-t 8), WER ≤18% e desvio de *timestamps* \<500 ms.  
> 4. **Prioridade 4 — Qualidade EN→PT-BR e Fidelidade de Atas 1K/4K/16K:** Avaliar opus-mt-en-pt-ct2 pós-STT e sumarização *map-reduce* em Gemma 4 E4B, Gemma 4 26B-A4B e Qwen3.6-35B-A3B quanto a preservação de nomes, datas, valores numéricos e decisões. **Critério de aprovação:** zero alucinações factuais/numéricas em 10 atas de controlo e avaliação pt-BR ≥4/5.

## **Rascunho de Atualização para docs/K11.md**

Como o docs/K11.md atual não esteve acessível, o texto abaixo serve como proposta pronta para revisão antes de aplicação no repositório:

# **GMKtec K11 Deployment Profile (Ryzen 9 8945HS / Radeon 780M / 32 GB)**

## **Hardware & Runtime Baseline**

> * **APU / iGPU:** AMD Ryzen 9 8945HS (8C/16T Zen 4), Radeon 780M (gfx1103), XDNA1 NPU (unused on Linux).  
> * **Memory Guard:** Requires dual-channel DDR5 (dmidecode verified). DDR5-4800 provides 76.8 GB/s theoretical (\~85.7% of DDR5-5600 systems). Single-channel halves bandwidth and triggers CPU-fallback (--threads 8).  
> * **Inference Engine:** Upstream llama.cpp built with \-DGGML\_VULKAN=ON over Mesa RADV (never distro build 8681 or AMDVLK). ROCm is excluded from default install due to gfx1103 instability and DKMS/ld.so conflicts.  
> * **Required 16K+ Flags:** \--n-gpu-layers 99 \--threads 8 \--flash-attn on \--cache-type-k q8\_0 \--cache-type-v q8\_0 \--ubatch-size 256 (-ub 512 risks vk::DeviceLostError at 16K).

## **Profiles (127.0.0.1 Local-Only)**

> * **\--mode safe (Default, Always-Resident \~10.2 GiB):**  
  * LLM: unsloth/gemma-4-E4B-it-GGUF (gemma-4-E4B-it-Q4\_K\_M.gguf, \--spec-type draft-mtp)  
  * STT: faster-whisper INT8 (MIT) \+ Silero VAD (CPU \-t 8\)  
  * Translation: gow-solucoes/opus-mt-en-pt-ct2 INT8 (CC-BY 4.0)  
  * Operates within default \~16 GiB kernel GTT without kernel modifications.  
> * **\--mode best (On-Demand Pipeline Stages, Opt-In GTT):**  
  * LLM: lmstudio-community/gemma-4-26B-A4B-it-GGUF (Q4\_K\_M, 22 GiB GTT) or unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4\_K\_M (24 GiB GTT).  
  * Requires explicit \--tune-gtt (reversible /etc/modprobe.d/99-k11-gtt.conf with pages\_limit=5767168 or 6291456).  
  * Optional \--non-commercial enables alefiury/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx INT8 (upstream TAGARELA corpus is CC BY-NC-SA 4.0).

## **Verification Status**

> * DDR5-4800 token rates are bandwidth-scaled estimates from related 780M setups and remain unverified on physical K11 hardware until scripts/bench\_k11.sh is executed.

#### **Referências citadas**

1\. Ryzen 7 355, Radeon 780M benchmarking Vulkan versus ROCm (7.2), https\://github.com/ggml-org/llama.cpp/discussions/32165 2\. amd-ryzen-inference-testing/hardware/780m.md at main \- GitHub, https\://github.com/cyberpuffin-digital/amd-ryzen-inference-testing/blob/main/hardware/780m.md 3\. Mini PC Gmktec Nucbox K11 AMD Ryzen 9 8945HS de 4.0GHz, https\://www\.visaovip.com/prod/mini-pc/mini-pc-gmktec-nucbox-k11-amd-ryzen-9-8945hs-de-4-0ghz-32gb-de-ram-1tb-ssd-win11pro/50252/ 4\. GMKtec NucBox K11 AMD Ryzen™ 9 8945HS, https\://de.gmktec.com/pt/products/gmktec-nucbox-k11-amd-ryzen%E2%84%A2-9-8945hs 5\. alefiury/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx \- Hugging Face, https\://huggingface.co/alefiury/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx 6\. sandovs/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx-q4, https\://huggingface.co/sandovs/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx-q4 7\. \[ICASSP 2026\] TAGARELA is a speech dataset composed ... \- GitHub, https\://github.com/freds0/TAGARELA 8\. Introducing Inkling 2 Mini \- Thinking Machines Lab, https\://thinkingmachines.ai/news/inkling-2-mini/ 9\. Inkling 2 Mini Benchmarks: How Thinking Machines' Open Model, https\://www\.mindstudio.ai/blog/inkling-2-mini-benchmarks 10\. Inkling 2 Mini: \$0.59 a Task at Qwen3.8-27B's Score \- OrcaRouter, https\://www\.orcarouter.ai/blog/inkling-2-mini-cost-per-task 11\. Running a Local LLM on AMD Radeon 780M — gfx1103, ROCm, https\://www\.k8s.it/posts/running-a-local-llm-on-amd-radeon-780m-gfx1103-rocm-and-the-gpu-that-wasnt-supposed-to-work/ 12\. \[Unsloth Bug\] Vulkan GGUF inference fails with ... \- GitHub, https\://github.com/unslothai/unsloth/issues/12695 13\. AMD Strix Halo Llama.cpp Installation Guide for Fedora 42, https\://community.frame.work/t/amd-strix-halo-llama-cpp-installation-guide-for-fedora-42/75856 14\. How to Build a Translation App With Open Models \- Acta Ai, https\://acta.ai/blogs/build-a-translation-app-with-open-models 15\. Llama.cpp ROCm 7.2-\>7.14 upgrade, Radeon 780m iGPU ... \- Reddit, https\://www\.reddit.com/r/LocalLLaMA/comments/1vqa7qh/llamacpp\_rocm\_72714\_upgrade\_radeon\_780m\_igpu/ 16\. Best Mini PC for Ollama in 2026: Specs That Decide It, https\://localaimaster.com/blog/best-mini-pc-ollama 17\. AMD Radeon 780M local LLM performance \- llamaperf, https\://llamaperf.com/gpu/radeon-780m 18\. Qwen3.8-Flash-Next GSQ-RCO Q2\_0 in Strata on a Radeon 780M, https\://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF/discussions/76 19\. GMKtec K11 Mini PC Review 2026 \| Ryzen 9 \+ OCuLink, https\://minipc-review.com/en/gmktec-k11-mini-pc-review 20\. What to Look for in a Mini PC with AMD Ryzen? Key Specs Explained, https\://electronics.alibaba.com/question/mini-pc-amd-buying-guide-ryzen-performance,-use-cases-pitfalls 21\. Qwen/Qwen3.6-35B-A3B \- Hugging Face, https\://huggingface.co/Qwen/Qwen3.6-35B-A3B 22\. lmstudio-community/Qwen3.6-35B-A3B-GGUF \- Hugging Face, https\://huggingface.co/lmstudio-community/Qwen3.6-35B-A3B-GGUF 23\. unsloth/Qwen3.6-35B-A3B-GGUF \- Hugging Face, https\://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/discussions/10 24\. Qwen — Qwen3.6-35B-A3B: Agentic Coding Power, Now Open to All, https\://qwen.ai/blog?id=qwen3.6-35b-a3b 25\. Welcome Gemma 4: Frontier multimodal intelligence on device, https\://huggingface.co/blog/gemma4 26\. lmstudio-community/gemma-4-26B-A4B-it-GGUF \- Hugging Face, https\://huggingface.co/lmstudio-community/gemma-4-26B-A4B-it-GGUF 27\. Inkling 2 Mini Benchmarks: How It Stacks Up Against Rivals, https\://www\.mindstudio.ai/blog/inkling-2-mini-benchmark-scores 28\. gemma4 \- Ollama, https\://ollama.com/library/gemma4 29\. Qwen/Qwen3.8-27B \- Hugging Face, https\://huggingface.co/Qwen/Qwen3.8-27B 30\. Inkling 2 Mini VRAM Requirements: BF16, FP8 & 4-bit \- StudioTV, https\://studiotvai.com/vram-requirements/inkling-2-mini 31\. Inkling-2-Mini-UD-IQ3\_XXS.gguf \- Hugging Face, https\://huggingface.co/unsloth/Inkling-2-Mini-GGUF/blob/main/Inkling-2-Mini-UD-IQ3\_XXS.gguf 32\. Inkling Mini 2 dethrones Qwen 3.8–27B for local coding \- Medium, https\://medium.com/data-science-in-your-pocket/inkling-mini-2-dethrones-qwen-3-8-27b-for-local-coding-32dd0c44ee5c 33\. ManniX-ITA/Qwen3.6-27B-A3B-Coder-MTP-GGUF \- Hugging Face, https\://huggingface.co/ManniX-ITA/Qwen3.6-27B-A3B-Coder-MTP-GGUF 34\. LFM2.5 benchmarks: tokens per second by GPU \| llamaperf, https\://llamaperf.com/model/lfm2-5 35\. joaorura/parakeet-tdt-0.6b-v3-ptBR-sherpa-onnx-int8 at bf31b61, https\://huggingface.co/joaorura/parakeet-tdt-0.6b-v3-ptBR-sherpa-onnx-int8/tree/bf31b612b9ea9602c21b9faf0dec038ff2c9a3fc 36\. ggml-org/Qwen3-ASR-1.7B-GGUF \- Hugging Face, https\://huggingface.co/ggml-org/Qwen3-ASR-1.7B-GGUF 37\. Qwen3-ASR & Qwen3-ForcedAligner is Now Open Sourced, https\://qwen.ai/blog?id=qwen3asr 38\. Qwen3-ASR-onnx \- baicai-1145 \- GitHub, https\://github.com/baicai-1145/Qwen3-ASR-onnx 39\. gow-solucoes/opus-mt-en-pt-ct2 \- Hugging Face, https\://huggingface.co/gow-solucoes/opus-mt-en-pt-ct2 40\. Download README.md from gow-solucoes/opus-mt-en-pt-ct2, https\://huggingface.co/gow-solucoes/opus-mt-en-pt-ct2/blob/b66dc8aa47cd5f6664433c0638e9b724ec563bf3/README.md 41\. README.md · Helsinki-NLP/opus-mt-tc-big-en-pt at main, https\://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-pt/blob/main/README.md 42\. NLLB-200 with CTranslate2 \- Tutorials \- OpenNMT, https\://forum.opennmt.net/t/nllb-200-with-ctranslate2/5090