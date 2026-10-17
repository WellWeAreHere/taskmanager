# TaskManager

TaskManager is a full-stack personal productivity app that turns recorded work sessions into outcome-aware task recommendations. It starts with a transparent baseline and activates a KNN regressor only after it has ten real, valid sessions.

## Run locally

Start the API:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

In another terminal start the dashboard:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:3000`. The API documentation is at `http://127.0.0.1:8000/docs`.

## Learning design

Each work session stores the task facts at its start, so later task edits never rewrite history. The outcome target is a documented 0–1 blend of completion (40%), partial progress (35%), time-fit (15%), and estimate realism (10%). KNN receives scaled numerical features (time available, remaining work, priority, deadline urgency, available-to-remaining ratio, category history) plus one-hot category encoding; unseen categories are accepted safely.

The model predicts outcomes for candidate task/session combinations, then combines that prediction with a small transparent baseline priority/urgency component. It does not predict task IDs or present scores as calibrated probabilities. The `/ml/metrics` endpoint performs a chronological holdout evaluation and withholds metrics for insufficient data. Session history is observational, not proof that a recommendation caused an outcome.

## Test

```powershell
cd backend
.\venv\Scripts\pytest.exe
```
