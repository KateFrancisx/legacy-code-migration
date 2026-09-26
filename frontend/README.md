# CodeMigrate Complete Frontend

A React + TypeScript + Vite dashboard for the complete CodeMigrate pipeline.

## Data contract

The frontend uses the existing REST endpoints:

- `POST /api/migrate`
- `GET /api/jobs/{job_id}`

It does not contain demo pipeline values. Stage views render the `results` and `stage_status` returned by FastAPI.

## Important backend note

The supplied historical `api/server.py` only orchestrated the Review-1 pre-LLM + LLM stages. The complete pipeline entry point is `scripts/run_complete_pipeline.py`, which also runs assembly, syntax verification, dependency verification, differential/semantic verification and risk analysis. The included `api_server_complete.py` is a wrapper example that invokes that complete entry point and exposes its JSON artifacts.

Before replacing your existing server, compare it with your current branch and merge only the required orchestration/data-collection changes.

## Run frontend

```bash
npm install
npm run dev
```

Set `VITE_API_BASE` if FastAPI is not on `http://localhost:8000`.
