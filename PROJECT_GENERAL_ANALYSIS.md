# Genna Content Machine — Project Plan

## Objetivo

Construir um pipeline de Data Science que cruza **métricas de performance** do Instagram com **62 features extraídas por IA** dos posts do perfil `@genna.brasil`, gerando um DataFrame unificado para modelagem preditiva.

---

## 1. Fontes de Dados

### 1.1 Arquivos de Mídia (Post Storage)
- **Localização:** `máquina de conteúdo/Post Storage/`
- **Quantidade atual:** 484 arquivos (480 do genna.brasil + 4 do 4blueoficial)
- **Formatos:** `.mp4` (reels/vídeos), `.jpg`, `.webp` (imagens)
- **Padrão de nome:** `{username}_{unix_timestamp}_{post_id}_{user_id}.{ext}`
- **Exemplo:** `profile_1774402267_<POST_ID>_<USER_ID>.mp4`
- **Timestamps únicos:** 182 (posts com múltiplas mídias compartilham o mesmo timestamp)

### 1.2 Planilha de Métricas (CSV)
- **Localização:** `máquina de conteúdo/Metrics/genna_export.csv`
- **Quantidade:** 144 linhas (posts de dez/2025 a mar/2026)
- **Colunas:** Caption, Post Type, Date, Reach, Likes Rate, Shares Rate, Reels Avg Watch Time, Views Rate, Interactions Rate, Views, Likes, Comments, Saved, Shares, Interactions, Following, Reels Video View Total Time, Profile Activity, Profile Visits, Replies, Saved Rate, Comments Rate
- **Formato da data:** `"Tue Mar 24 2026 22:31:07 GMT-0300 (Horário Padrão de Brasília)"`

### 1.3 Features de Enriquecimento (62 features)
- **Referência:** `máquina de conteúdo/features_reference.json`
- **Planilha original:** [Google Sheets](https://docs.google.com/spreadsheets/d/1SGxhH_HT45tuM1ccmtsOG2uBnjeXNOxR/edit)
- **7 categorias:** Visual & Production (15), Hook & Attention (10), People & Talent (8), Audio & Music (8), Content & Narrative (10), Sensuality & Provocation (5), Text & Copy (6)
- **Modelos necessários:** GPT-4o (24 features), Gemini Flash (19), Local/free (9), Whisper (2), Mixed (1), API metadata (1)

---

## 2. Estratégia de Cruzamento de Dados

### 2.1 Chave Primária: Unix Timestamp

O **Unix timestamp** presente no nome do arquivo é a chave que conecta as três fontes de dados.

```
ARQUIVO:  profile_[1774402267]_<POST_ID>_<USER_ID>.mp4
                         ↕
CSV:      Date: "Tue Mar 24 2026 22:31:07 GMT-0300"  →  timestamp 1774402267
                         ↕
FEATURES: Extraídas do arquivo identificado pelo mesmo timestamp
```

### 2.2 Validação do Cruzamento
- **140 de 144** registros do CSV bateram exatamente com timestamps dos arquivos (97.2%)
- **4 registros** não bateram — provável diferença de fuso horário no parse (ajustável)
- **42 arquivos** sem par no CSV — posts anteriores ao período coberto pela planilha

### 2.3 Tratamento de Posts com Múltiplas Mídias (Carrosséis)
- Posts de carrossel geram múltiplos arquivos com o **mesmo timestamp**
- Estratégia: agrupar por timestamp, tratar como um único registro no DataFrame
- Para features visuais: analisar a primeira imagem ou calcular média entre slides

---

## 3. Pipeline de Processamento

### Fase 1 — Preparação de Dados
1. **Parsear nomes dos arquivos** → extrair `timestamp`, `post_id`, `user_id`, `extensão`
2. **Parsear CSV** → converter coluna `Date` para Unix timestamp
3. **Join** → cruzar arquivos com métricas via timestamp
4. **Agrupar carrosséis** → consolidar múltiplos arquivos por timestamp

### Fase 2 — Extração de Features (62 features)

Features são organizadas por **engine de extração** (não por categoria temática), porque features que usam o mesmo modelo são extraídas numa única chamada de API (batching). A categoria temática (Visual & Production, Hook & Attention, etc.) está registrada no `features_reference.json`.

#### Applicabilidade por tipo de post

| Tipo | Features aplicáveis | Processo |
|------|-------------------|----------|
| Reels (R) | Todas as 62 | Vídeo + áudio + caption |
| Carousels (C) | ~45 features | Imagens + caption (sem áudio) |
| Single Images (I) | ~40 features | Imagem + caption (sem áudio) |

#### Extractors (6 módulos em `scripts/extractors/`)

| Módulo | Features | Engine / Ferramentas | Custo |
|--------|----------|---------------------|-------|
| `local.py` | 9 features | FFprobe, PIL, regex, textstat | Grátis |
| `whisper.py` | 2 features | OpenAI Whisper (local) | Grátis |
| `gemini.py` | 19 features | Gemini Flash API (batched) | ~$0.01/post |
| `gpt4o.py` | 24 features | GPT-4o API (batched) | ~$0.03–0.05/post |
| `mixed.py` | 1 feature | OpenCV + FFprobe (cuts_per_minute) | Grátis |
| `metadata.py` | 1 feature | API metadata (carousel_slide_count) | Grátis |

#### Ordem de execução (menor → maior custo)
1. `local.py` → 9 features grátis, execução instantânea
2. `whisper.py` → 2 features grátis, requer FFmpeg
3. `mixed.py` → 1 feature grátis, requer OpenCV
4. `metadata.py` → 1 feature, depende de como obtemos a contagem de slides
5. `gemini.py` → 19 features, mais barato entre os modelos pagos
6. `gpt4o.py` → 24 features, mais caro, rodar por último

**Custo estimado total:** ~$0.04–$0.07 por Reel (conforme planilha original)

### Fase 3 — Montagem do DataFrame Final
```
DataFrame = Métricas (CSV) + Features Extraídas (62 cols) + Metadados do Arquivo
```

Colunas esperadas:
- **Identificação:** timestamp, post_id, date, post_type
- **Métricas (22 cols):** Reach, Views, Likes, Comments, Saved, Shares, etc.
- **Features extraídas (62 cols):** video_duration_sec, cuts_per_minute, etc.
- **Total:** ~87+ colunas por registro

### Fase 4 — Data Science / Modelagem
- Análise exploratória (EDA)
- Correlações entre features e métricas de performance
- Modelos preditivos (ex: quais features predizem alto Reach?)
- Feature importance analysis
- Clustering de tipos de conteúdo

---

## 4. Automação Diária (Download de Novos Posts)

### Situação Atual
- **Ferramenta:** Turbo Downloader for Instagram (extensão Chrome)
- **Funciona com automação Claude:** Sim (após ajuste feito pelo usuário)
- **Detecção de duplicatas:** Sim (extensão pula arquivos já baixados)
- **Destino:** `máquina de conteúdo/Post Storage/`

### Fluxo Diário
1. Claude abre Chrome → navega para `instagram.com/genna.brasil`
2. Clica "Download All" → extensão baixa apenas posts novos
3. Novos arquivos são processados pelo pipeline de features
4. DataFrame é atualizado com novos registros

### Limitações
- Requer Chrome aberto + Claude Code ativo (não é cron verdadeiro)
- Alternativa futura: script Python com `instaloader` ou `yt-dlp` para automação completa
- A extensão baixa TODOS os tipos de post (não filtra só reels)

---

## 5. Dev Setup

### Pré-requisitos
- Python 3.14 (instalado em via `py` launcher)
- FFmpeg (necessário para `ffmpeg-python` e Whisper) — instalar separadamente
- API keys: OpenAI (GPT-4o) e Google AI (Gemini Flash)

### Setup rápido (Windows)
```bash
# Opção 1: Rodar o script de setup
setup.bat

# Opção 2: Manual
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Editar .env com suas API keys
```

### Ativar o venv antes de trabalhar
```bash
# Sempre que abrir o terminal/Cursor:
.venv\Scripts\activate

# Para confirmar que está no venv:
where python
# Deve mostrar: ...\máquina de conteúdo\.venv\Scripts\python.exe
```

### Arquivos de configuração
| Arquivo | Propósito |
|---------|-----------|
| `requirements.txt` | Dependências Python — rodar `pip install -r requirements.txt` |
| `.env` | API keys e paths (criado a partir de `.env.example`) |
| `.env.example` | Template do `.env` (seguro para git) |
| `.gitignore` | Protege `.env`, venv, e arquivos grandes do git |
| `setup.bat` | Script automático de setup (Windows) |

---

## 6. Estrutura de Pastas

```
máquina de conteúdo/
├── .env                         # API keys (NÃO commitar)
├── .env.example                 # Template do .env
├── .gitignore                   # Proteção de arquivos sensíveis
├── .venv/                       # Virtual environment Python
├── CLAUDE.md                    # Instruções do projeto (para IA)
├── PROJECT_PLAN.md              # Este arquivo
├── features_reference.json      # 62 features detalhadas
├── requirements.txt             # Dependências Python
├── setup.bat                    # Setup automático (Windows)
│
├── scripts/                     # Pipeline Python
│   ├── __init__.py
│   ├── config.py                # Paths, constantes, settings do projeto
│   ├── prepare_data.py          # Fase 1: parse filenames + CSV + join
│   ├── pipeline.py              # Fase 2: orquestra todos os extractors
│   ├── build_dataframe.py       # Fase 3: monta DataFrame final
│   │
│   └── extractors/              # Um módulo por engine de extração
│       ├── __init__.py
│       ├── base.py              # Classe base + utilitários compartilhados
│       ├── local.py             # 9 features  — FFprobe, PIL, regex
│       ├── whisper.py           # 2 features  — transcrição de áudio
│       ├── gemini.py            # 19 features — prompt batched Gemini Flash
│       ├── gpt4o.py             # 24 features — prompt batched GPT-4o
│       ├── mixed.py             # 1 feature   — cuts_per_minute (CV + FFprobe)
│       └── metadata.py          # 1 feature   — carousel_slide_count
│
├── notebooks/                   # Jupyter para EDA e modelagem
├── data/
│   ├── processed/               # DataFrame final (parquet/csv)
│   └── features_cache/          # Cache de features extraídas por post
│
├── Post Storage/                # Arquivos baixados do Instagram (484+)
├── Metrics/
│   └── genna_export.csv         # Métricas exportadas do Instagram
│
├── content/                     # (existente — roteiros)
└── Old Scripts/                 # (existente — referências)
```

---

## 7. Passo a Passo de Execução

Guia granular para construir o pipeline do zero. Cada etapa é independente e verificável — só avance para a próxima quando a atual estiver funcionando.

---

### BLOCO A — Fundação (setup + dados crus)

#### Etapa A1: Verificar ambiente Python
- **O que faz:** confirma que Python, venv e dependências estão funcionando
- **Como verificar:** rodar `python --version` no venv e confirmar que importa pandas sem erro
- **Resultado:** terminal mostra Python 3.14.x e `import pandas` roda sem erro

#### Etapa A2: Criar estrutura de pastas e arquivos
- **O que faz:** cria `scripts/`, `scripts/extractors/`, `data/`, `notebooks/` e todos os `__init__.py`
- **Como verificar:** abrir a árvore de pastas no Cursor e conferir que a estrutura bate com a seção 6
- **Resultado:** todas as pastas e arquivos vazios criados

#### Etapa A3: Criar `scripts/config.py`
- **O que faz:** centraliza todos os caminhos (Post Storage, Metrics, data/), constantes e carrega `.env`
- **Como verificar:** rodar `python -c "from scripts.config import *; print(POST_STORAGE_DIR)"` e ver o caminho correto
- **Resultado:** qualquer script do projeto pode importar paths de `config.py`

---

### BLOCO B — Fase 1: Preparação de Dados

#### Etapa B1: Parsear nomes dos arquivos
- **O que faz:** lê todos os arquivos de `Post Storage/`, extrai `username`, `timestamp`, `post_id`, `user_id`, `extensão` do nome
- **Onde:** `scripts/prepare_data.py` → função `parse_filenames()`
- **Como verificar:** gera um DataFrame com 484 linhas (uma por arquivo), todas as colunas preenchidas
- **Resultado:** DataFrame `df_files` com colunas `[filename, username, timestamp, post_id, user_id, extension]`

#### Etapa B2: Parsear CSV de métricas
- **O que faz:** lê `Metrics/genna_export.csv`, converte a coluna `Date` para Unix timestamp
- **Onde:** `scripts/prepare_data.py` → função `parse_metrics()`
- **Como verificar:** conferir que o timestamp gerado bate com o esperado para algumas datas conhecidas
- **Resultado:** DataFrame `df_metrics` com 144 linhas + coluna `timestamp` numérica

#### Etapa B3: Join — cruzar arquivos com métricas
- **O que faz:** merge de `df_files` e `df_metrics` via coluna `timestamp`
- **Onde:** `scripts/prepare_data.py` → função `join_files_metrics()`
- **Como verificar:** contar quantos registros cruzaram (esperado: ~140 de 144)
- **Resultado:** DataFrame `df_joined` com arquivos + métricas lado a lado; log dos registros que não bateram

#### Etapa B4: Investigar os 4 registros que não cruzaram
- **O que faz:** identifica e corrige a diferença de timezone que impediu o match
- **Como verificar:** após correção, rodar o join de novo e confirmar 144/144 matches
- **Resultado:** todos os registros do CSV têm correspondência com arquivos

#### Etapa B5: Agrupar carrosséis
- **O que faz:** consolida múltiplos arquivos com o mesmo timestamp em um único registro
- **Onde:** `scripts/prepare_data.py` → função `group_carousels()`
- **Como verificar:** confirmar que o número de registros únicos = número de timestamps únicos
- **Resultado:** DataFrame `df_posts` — um registro por post, com lista de arquivos associados

#### Etapa B6: Salvar checkpoint da Fase 1
- **O que faz:** salva `df_posts` como `data/processed/posts_base.parquet`
- **Como verificar:** recarregar o parquet e confirmar que os dados estão intactos
- **Resultado:** arquivo parquet pronto para servir de input para a Fase 2

---

### BLOCO C — Fase 2: Extractors (features grátis)

#### Etapa C1: Criar classe base `scripts/extractors/base.py`
- **O que faz:** define `BaseExtractor` com interface padrão (`extract(post) → dict`), utilitários de cache e logging
- **Como verificar:** instanciar a classe e confirmar que os métodos existem
- **Resultado:** classe abstrata que todos os extractors vão herdar

#### Etapa C2: Implementar `scripts/extractors/local.py` (9 features)
- **O que faz:** extrai features usando ferramentas locais gratuitas
- **Features:** `video_duration_sec`, `aspect_ratio`, `face_presence`, `caption_length_chars`, `hashtag_count`, `caption_readability_score`, `emoji_density`, `account_mentions_count`, `carousel_slide_count`
- **Ferramentas:** FFprobe (duração, aspect ratio), PIL/OpenCV (face detection), regex/textstat (caption)
- **Como verificar:** rodar em 5 posts conhecidos e conferir os valores manualmente
- **Resultado:** 9 features extraídas corretamente para cada post

#### Etapa C3: Implementar `scripts/extractors/whisper.py` (2 features)
- **O que faz:** transcreve o áudio dos Reels e calcula métricas de fala
- **Features:** `speech_language`, `speech_pacing_wpm`
- **Pré-requisito:** FFmpeg instalado
- **Como verificar:** rodar em 3 Reels e conferir idioma detectado + palavras por minuto
- **Resultado:** 2 features de áudio extraídas para cada Reel

#### Etapa C4: Implementar `scripts/extractors/mixed.py` (1 feature)
- **O que faz:** detecta cortes no vídeo e calcula taxa por minuto
- **Features:** `cuts_per_minute`
- **Ferramentas:** OpenCV (scene detection) + FFprobe (duração)
- **Como verificar:** rodar em 3 Reels e conferir se o número de cortes parece razoável
- **Resultado:** 1 feature de edição extraída para cada Reel

#### Etapa C5: Testar extractors grátis em batch
- **O que faz:** roda os 3 extractors (local + whisper + mixed) em todos os posts
- **Onde:** `scripts/pipeline.py` → função `run_free_extractors()`
- **Como verificar:** confirmar que todas as 12 features grátis estão preenchidas; salvar resultado em `data/features_cache/`
- **Resultado:** cache com 12 features para cada post; sem custo de API

---

### BLOCO D — Fase 2: Extractors (APIs pagas)

#### Etapa D1: Implementar `scripts/extractors/gemini.py` (19 features)
- **O que faz:** monta prompt batched que extrai todas as 19 features Gemini Flash de uma vez
- **Como verificar:** rodar em 3 posts de teste e conferir as 19 features retornadas
- **Resultado:** extractor funcional com prompt otimizado, parsing de resposta e tratamento de erros

#### Etapa D2: Implementar `scripts/extractors/gpt4o.py` (24 features)
- **O que faz:** monta prompt batched que extrai todas as 24 features GPT-4o de uma vez
- **Como verificar:** rodar em 3 posts de teste e conferir as 24 features retornadas
- **Resultado:** extractor funcional com prompt otimizado, parsing de resposta e tratamento de erros

#### Etapa D3: Implementar `scripts/extractors/metadata.py` (1 feature)
- **O que faz:** obtém `carousel_slide_count` via contagem de arquivos ou API
- **Como verificar:** conferir com posts que sabemos serem carrosséis
- **Resultado:** feature de contagem de slides extraída

#### Etapa D4: Rodar pipeline completo (62 features) em amostra
- **O que faz:** roda TODOS os 6 extractors em ~10 posts para validar o pipeline de ponta a ponta
- **Onde:** `scripts/pipeline.py` → função `run_all_extractors()`
- **Como verificar:** DataFrame de saída tem 62 colunas de features preenchidas (com NaN onde a feature não se aplica)
- **Resultado:** pipeline validado ponta a ponta antes de rodar no dataset completo

#### Etapa D5: Rodar pipeline completo em todos os posts
- **O que faz:** processa todos os ~144 posts com métricas (ou 182 posts totais)
- **Custo estimado:** ~$6–$10 para 144 posts
- **Como verificar:** conferir que todos os posts foram processados e os resultados fazem sentido
- **Resultado:** `data/features_cache/` completo com todas as 62 features para cada post

---

### BLOCO E — Fase 3: DataFrame Final

#### Etapa E1: Montar DataFrame unificado
- **O que faz:** junta `posts_base.parquet` (Fase 1) com features extraídas (Fase 2) em um único DataFrame
- **Onde:** `scripts/build_dataframe.py`
- **Como verificar:** DataFrame tem ~87 colunas (4 identificação + 22 métricas + 62 features) e número correto de linhas
- **Resultado:** `data/processed/genna_dataset.parquet` — dataset completo pronto para análise

#### Etapa E2: Validação e limpeza
- **O que faz:** verifica tipos de dados, trata NaNs, remove outliers óbvios, padroniza colunas categóricas
- **Como verificar:** rodar `df.describe()` e `df.info()` — sem surpresas
- **Resultado:** dataset limpo e documentado

---

### BLOCO F — Fase 4: Data Science

#### Etapa F1: Análise Exploratória (EDA)
- **O que faz:** notebook com distribuições, correlações e visualizações das 62 features vs métricas
- **Onde:** `notebooks/01_eda.ipynb`
- **Resultado:** entendimento visual dos padrões nos dados

#### Etapa F2: Feature Importance
- **O que faz:** identifica quais das 62 features mais influenciam Reach, Views, Likes, Shares
- **Onde:** `notebooks/02_feature_importance.ipynb`
- **Resultado:** ranking das features mais importantes por métrica

#### Etapa F3: Modelagem Preditiva
- **O que faz:** treina modelos para prever performance a partir das features
- **Onde:** `notebooks/03_modeling.ipynb`
- **Resultado:** modelo que responde "dado essas features, quanto Reach esse post terá?"

#### Etapa F4: Clustering
- **O que faz:** agrupa posts por similaridade de features, identifica "tipos" de conteúdo
- **Onde:** `notebooks/04_clustering.ipynb`
- **Resultado:** segmentação dos posts em clusters com perfis distintos

---

### Resumo da sequência

```
A1 → A2 → A3                          FUNDAÇÃO (setup)
       ↓
B1 → B2 → B3 → B4 → B5 → B6          FASE 1 (dados crus)
                              ↓
C1 → C2 → C3 → C4 → C5               FASE 2a (features grátis)
                        ↓
D1 → D2 → D3 → D4 → D5               FASE 2b (features pagas)
                        ↓
E1 → E2                               FASE 3 (DataFrame final)
       ↓
F1 → F2 → F3 → F4                     FASE 4 (Data Science)
```

Total: **23 etapas**, estimativa de ~15–20 horas de trabalho distribuídas.

---

## 8. Decisões em Aberto

1. **Filtrar só Reels?** — A planilha tem `Post Type = REEL` em todas as linhas visíveis. Se o foco é só Reels, podemos ignorar imagens/carrosséis.
2. **Conta secundária para scraping?** — Se migrarmos para script Python, usar conta descartável é recomendado.
3. **Onde rodar os modelos de IA?** — API direta vs pipeline orquestrado (n8n, Airflow, etc.)
4. **Frequência de atualização do CSV de métricas** — De onde vem o export? Manual ou API?
5. **Período de análise** — Focar nos 144 posts com métricas, ou enriquecer todos os 182 posts baixados?
