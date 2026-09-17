# CodeMigrate — AI-Powered Legacy Code Migration Intelligence Platform

CodeMigrate is an AI-powered software modernization platform designed to assist developers in migrating legacy code to modern language versions.

Instead of treating migration as a simple code translation problem, the platform analyzes the repository, identifies migration candidates, understands dependencies and code structure, retrieves relevant historical migration examples, constructs migration-aware prompts, and uses an LLM to generate migrated code.

The current MVP focuses on **Python 2 → Python 3 migration** and is designed to be extensible to additional programming languages and migration scenarios.

---

## Project Overview

Legacy software systems often contain outdated syntax, APIs, dependencies, and language constructs that make manual modernization time-consuming and error-prone.

CodeMigrate provides an intelligent migration workflow:

```text
Legacy Repository
       ↓
Repository Scanning
       ↓
Version Detection
       ↓
Migration Candidate Selection
       ↓
Code Extraction & Static Analysis
       ↓
Semantic Embeddings
       ↓
Dependency Analysis
       ↓
Migration Planning
       ↓
Repository Context Construction
       ↓
RAG Retrieval
       ↓
Migration Prompt Construction
       ↓
LLM-Based Code Migration
       ↓
Migrated Code
```

Future stages extend this workflow with automated verification, differential testing, semantic equivalence analysis, migration risk prediction, explainability, and developer feedback.

---

## Key Features

### Repository Scanning
- Discovers files within an uploaded repository.
- Identifies programming languages and file types.
- Applies ignore/skip rules to exclude irrelevant files.
- Produces a repository manifest for subsequent pipeline stages.

### Version Detection
- Detects the language version used by source files.
- Identifies repositories containing legacy language constructs.
- Determines whether files require migration.

### Migration Candidate Selection
- Selects files containing migration-relevant constructs.
- Filters files that do not require migration.
- Produces a migration job containing selected candidates.

### Code Extraction & Static Analysis
- Extracts functions and relevant code units.
- Identifies migration-relevant language constructs.
- Collects structural and code-level features for downstream analysis.

### Semantic Embeddings
- Uses CodeBERT to generate semantic representations of extracted code.
- Current embedding model: `microsoft/codebert-base`.
- Embeddings support semantic retrieval and migration-example matching.

### Dependency Analysis
- Analyzes relationships between Python files.
- Identifies imports and function-call relationships.
- Builds repository-level dependency information.
- Helps determine migration order and contextual dependencies.

### Migration Planning
- Determines an ordered set of migration units.
- Uses dependency relationships to establish migration order.
- Produces a migration plan before LLM-based translation.

### Repository Context
- Collects repository-level information for each migration unit.
- Includes dependencies, dependents, repository structure, tests, and migration-related context.

### Retrieval-Augmented Generation (RAG)

The platform maintains a migration knowledge base constructed from historical migration examples.

The current data pipeline includes:

```text
Historical Migration Data
        ↓
Metadata Enrichment
        ↓
Migration Pair Extraction
        ↓
Quality Filtering
        ↓
RAG-Ready Dataset
        ↓
Semantic Embedding
        ↓
Similarity Retrieval
```

Processed datasets include:
- `data/pairs.jsonl`
- `data/pairs_quality.jsonl`
- `data/rag_ready_298.jsonl`

### Migration Prompt Construction
- Builds structured migration prompts.
- Combines migration plans, repository context, dependencies, tests, retrieved examples, and source code.
- Produces migration-specific prompts for the LLM.

### LLM-Based Migration
The current implementation uses Gemini for source-code migration.

The LLM receives the structured migration prompt and generates migrated source code.

Current MVP:

```text
Python 2 → Python 3
```

Generated files are stored under:

```text
outputs/python2_migration_test_repo_migrated/
```

---

## Current Migration Pipeline

```text
Repository
    ↓
Repository Scanner
    ↓
Version Detection
    ↓
Migration Selection
    ↓
Code Extraction
    ↓
CodeBERT Embeddings
    ↓
Dependency Analysis
    ↓
Migration Planning
    ↓
Repository Context
    ↓
RAG Retrieval
    ↓
Prompt Construction
    ↓
Gemini Migration
    ↓
Migrated Python Code
```

---

## Example Migration

The project includes a Python 2 migration test repository containing multiple Python files and intentional legacy constructs.

The migration workflow identifies files requiring migration and processes them according to their dependency relationships.

Example migration order:

```text
utils.py
    ↓
billing.py
    ↓
main.py
```

The resulting migrated source files are generated in:

```text
outputs/python2_migration_test_repo_migrated/
```

---

## Technology Stack

### Backend
- Python
- FastAPI
- Uvicorn

### Code Analysis
- Python AST / static analysis
- Dependency analysis
- Code feature extraction

### Machine Learning / NLP
- Hugging Face Transformers
- CodeBERT
- PyTorch
- Scikit-learn

### Retrieval
- JSONL migration datasets
- Supabase / vector retrieval components
- Retrieval-Augmented Generation (RAG)

### LLM
- Google Gemini

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- Lucide React

### Development
- Git / GitHub
- Python virtual environments
- VS Code

---

## Project Structure

```text
CodeMigration/
│
├── api/
│   ├── __init__.py
│   └── server.py
│
├── data/
│   ├── metadata_enricher.py
│   ├── pairs.jsonl
│   ├── pairs_quality.jsonl
│   └── rag_ready_298.jsonl
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
│
├── pipeline/
│   ├── dependency/
│   ├── embeddings/
│   ├── extraction/
│   ├── llm/
│   ├── planning/
│   ├── retrieval/
│   ├── scanner/
│   ├── selection/
│   └── version_detection/
│
├── scripts/
│   ├── run_pipeline.py
│   ├── run_pre_llm_pipeline.py
│   ├── run_llm_migration.py
│   ├── generate_embeddings.py
│   ├── github_migration_miner.py
│   └── ...
│
├── test/
│
├── outputs/
│   ├── python2_migration_test_repo_migrated/
│   └── migration pipeline JSON outputs
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Installation

### 1. Clone the repository

```bash
git clone <YOUR-GITHUB-REPOSITORY-URL>
cd CodeMigration
```

### 2. Create a Python virtual environment

Windows:

```powershell
python -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```powershell
pip install -r requirements.txt
```

---

## Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

The frontend will normally be available at:

```text
http://localhost:5173
```

---

## Backend Setup

From the project root:

```powershell
python -m uvicorn api.server:app --port 8000
```

The backend will normally be available at:

```text
http://localhost:8000
```

Health check:

```text
GET /api/health
```

---

## Environment Variables

API credentials and other secrets are stored locally in `.env`.

Example:

```env
GEMINI_API_KEY=your_api_key
```

Do **not** commit `.env` to GitHub.

An optional `.env.example` file can document required variables without exposing credentials.

---

## Running the Migration Pipeline

### Pre-LLM Pipeline

The pre-LLM pipeline performs repository analysis, feature extraction, embeddings, dependency analysis, migration planning, repository context construction, RAG retrieval, and prompt construction.

```powershell
python scripts\run_pre_llm_pipeline.py "PATH_TO_REPOSITORY"
```

### LLM Migration

After the pre-LLM pipeline has completed:

```powershell
python scripts\run_llm_migration.py "PATH_TO_REPOSITORY"
```

The generated migration results are stored in the `outputs/` directory.

---

## API Workflow

```text
React Frontend
      ↓
FastAPI API
      ↓
Migration Job
      ↓
Migration Pipeline
      ↓
LLM Migration
      ↓
Job Results
      ↓
Frontend Dashboard
```

The dashboard is designed to display pipeline progress and results at individual stages.

---

## Migration Knowledge Base

The project uses historical migration examples to support retrieval-augmented migration.

The processed datasets are stored in:

```text
data/
├── pairs.jsonl
├── pairs_quality.jsonl
└── rag_ready_298.jsonl
```

The raw GitHub-mined source corpus is maintained locally and excluded from Git:

```text
data/files/
```

This keeps the repository manageable while preserving the processed migration knowledge base used by the project.

---

## Current MVP Status

The current implementation covers:
- Repository scanning
- Version detection
- Migration candidate selection
- Code extraction
- Static/code feature analysis
- CodeBERT embeddings
- Dependency analysis
- Migration planning
- Repository context construction
- RAG retrieval
- Structured migration prompt generation
- Gemini-based code migration
- Migrated source-code generation
- React + FastAPI integration
- Migration dashboard

Current demonstration:

```text
Python 2 → Python 3
```

---

## Planned Extensions

### Automated Verification
- Syntax verification
- Static verification of migrated code
- Automated test execution

### Differential Testing
- Generate compatible test inputs.
- Execute original and migrated implementations.
- Compare outputs and behavior.

### Semantic Equivalence
- Compare source and migrated code using semantic representations.
- Use transformer-based models to estimate semantic similarity.

### Migration Risk Prediction
- Combine static-analysis, dependency, retrieval, and verification features.
- Predict migration risk using machine-learning models.

### Explainability
- Identify factors contributing to migration risk.
- Provide developers with interpretable migration warnings.

### Developer Feedback
- Allow developers to review migration results.
- Capture feedback for future improvement of the migration knowledge base.

### Multi-Language Migration

The architecture is intended to support additional languages through language-aware parsing, analysis, retrieval, and model routing.

Potential future migrations include:

```text
Python 2 → Python 3
Java 7 → Java 17+
C/C++ legacy → modern standards
JavaScript → TypeScript
```

---

## Research Objective

The project investigates how repository-level static analysis, semantic retrieval, dependency-aware context, and LLM-based code generation can be combined for legacy software modernization.

The central objective is to move beyond direct source-code translation toward an intelligent migration workflow that can:

1. Understand the legacy repository.
2. Identify migration-relevant code.
3. Understand relationships between components.
4. Retrieve relevant historical migrations.
5. Generate migration-aware prompts.
6. Produce migrated code.
7. Verify and assess migration quality.
8. Provide actionable information to developers.

---

## Disclaimer

This project is an academic/research prototype. Generated migrations should be reviewed and verified before being used in production systems.
