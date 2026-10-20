# Instagram Content ML Pipeline

A data enrichment and machine-learning pipeline that explains **why some Instagram posts outperform others**. It joins each post's performance metrics (reach, views, likes, shares, saves, comments) with **62 AI-extracted content features**, then uses scikit-learn to rank feature importance, model performance and cluster content.

Built for the Instagram profile of Genna Technologies (Brazilian market, business-storytelling Reels and carousels). The dataset covered 484 media files / 140 posts (Dec 2025 – Mar 2026).

> **Data privacy:** this repository contains code, feature definitions and aggregated notebook results only. Raw exports, media files, transcripts, captions and per-post datasets are excluded. On-camera presenters are pseudonymized as `presenter_a`, `presenter_b` and `presenter_c`.

## How it works

```
Instagram media (Post Storage/)  ─┐
                                  ├─► Phase 1  prepare_data.py   parse filenames + metrics CSV, join on Unix timestamp
Instagram metrics CSV (Metrics/) ─┘
                                      Phase 2  pipeline.py       run 6 extractors → 62 features (cached per post)
                                      Phase 3  build_dataframe.py one unified DataFrame (parquet/csv)
                                      Phase 4  notebooks/         EDA · feature importance · modeling · clustering
```

**Join key:** the Unix timestamp embedded in each media filename (`{profile}_{TIMESTAMP}_{POST_ID}_{USER_ID}.ext`) links files ↔ metrics rows ↔ extracted features. Carousels with multiple media are grouped into one post.

### Feature extractors (`scripts/extractors/`)

Free/local extractors run first, then paid APIs:

| Extractor | Source | Examples of features |
|---|---|---|
| `local` | OpenCV / ffmpeg | duration, cuts per minute, resolution, image quality |
| `whisper` | OpenAI Whisper (local) | transcript, speech pacing (WPM) |
| `mixed` | local + heuristics | audio/caption availability, text density |
| `metadata` | metrics CSV | caption length, post type, posting time |
| `gemini` | Gemini Flash (vision) | hook technique, visual format, first-frame scroll-stop score |
| `gpt4o` | GPT-4o | narrative structure, emotional arc, value proposition, curiosity gap |

The full catalog of 62 features, with types and allowed values, is in `general_features_reference.json`.

### Format analysis (human in the loop) — `scripts/format/`

A second pass adds 15 format-specific features (e.g. plot-twist strength, hook strength, presenter energy):

```bash
python -m scripts.format.pipeline discover  # AI proposes features → format_features_review.md
# a human edits/approves the review file
python -m scripts.format.pipeline confirm   # parse review → format_features_reference.json
python -m scripts.format.pipeline extract   # extract approved features for every post
```

## Notebooks

| Notebook | What it does |
|---|---|
| `general/01_eda` | metric distributions, Reels vs carousels, Spearman correlations, top vs bottom performers |
| `general/02_feature_importance` | feature ranking across metrics |
| `general/03_modeling` | Linear Regression, Random Forest, Gradient Boosting with 5-fold CV |
| `general/04_clustering` | content clusters (silhouette analysis) |
| `format/01–03` | same analysis for format features and the combined 77-feature set |
| `*_all_features` | full feature dumps (outputs cleared for privacy) |

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env          # then add your OPENAI_API_KEY and GOOGLE_API_KEY
```

Put your own media in `Post Storage/` and your Instagram metrics export in `Metrics/`, then run the phases in order. `PROJECT_GENERAL_ANALYSIS.md` and `PROJECT_FORMAT_ANALYSIS.md` hold the full design notes (in Portuguese).

## Stack

Python · pandas · scikit-learn · SciPy · matplotlib/seaborn · OpenCV · ffmpeg · OpenAI Whisper · GPT-4o · Gemini Flash · Jupyter
