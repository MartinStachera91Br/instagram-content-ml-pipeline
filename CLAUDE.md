# CLAUDE.md — Instagram Content ML Pipeline

## Data Science Pipeline (Content Analysis)

### Objetivo
Cruzar métricas de performance do Instagram com 62 features extraídas por IA dos posts, para modelagem preditiva.

### Estrutura do Projeto
```
instagram-content-ml-pipeline/
├── .env                              # API keys (NÃO commitar)
├── .env.example                      # Template do .env
├── .gitignore
├── .venv/                            # Virtual environment Python
├── requirements.txt                  # Dependências Python
├── setup.bat                         # Script de setup (Windows)
├── PROJECT_GENERAL_ANALYSIS.md       # Plano da análise geral (62 features)
├── PROJECT_FORMAT_ANALYSIS.md        # Plano da análise de formato
├── general_features_reference.json   # 62 features gerais (referência)
├── format_definition.md              # Definição do formato de conteúdo
├── format_features_reference.json    # Features de formato (AI + humano)
├── scripts/
│   ├── config.py                     # Paths e constantes
│   ├── prepare_data.py               # Fase 1: parse + join
│   ├── pipeline.py                   # Fase 2: extractors gerais
│   ├── build_dataframe.py            # Fase 3: DataFrame geral
│   ├── extractors/                   # Extractors gerais (6 módulos)
│   └── format/                       # Pipeline de formato
│       ├── discover_features.py      # Fase 1: AI propõe features
│       ├── pipeline.py               # Orquestrador (discover/confirm/extract)
│       ├── extractor.py              # Fase 2: extração de features
│       └── build_format_dataset.py   # Fase 3: dataset combinado
├── notebooks/
│   ├── general/                      # Análise das 62 features gerais
│   │   ├── 01_eda.ipynb
│   │   ├── 02_feature_importance.ipynb
│   │   ├── 03_modeling.ipynb
│   │   ├── 04_clustering.ipynb
│   │   └── 05_all_features.ipynb
│   └── format/                       # Análise das features de formato
│       ├── 01_eda.ipynb
│       ├── 02_feature_importance.ipynb
│       ├── 03_combined_modeling.ipynb
│       └── 04_all_features.ipynb
├── data/
│   ├── processed/                    # Datasets finais (parquet/csv)
│   ├── general_features_cache/       # Cache de features gerais
│   └── format_features_cache/        # Cache de features de formato
├── Post Storage/                     # Arquivos baixados do Instagram
└── Metrics/                          # CSV com métricas do Instagram
```

### Chave de cruzamento
O **Unix timestamp** no nome do arquivo (`{PROFILE}_{TIMESTAMP}_{POST_ID}_{USER_ID}.ext`) é a chave primária que conecta arquivos ↔ métricas CSV ↔ features extraídas.

### Ambiente
- Python 3.14 com venv
- Dependências em `requirements.txt`
- API keys em `.env` (carregar com `python-dotenv`)
- Código em `scripts/`, análises em `notebooks/`
