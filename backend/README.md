# TaskManager API

Run from `backend` with the included environment:

```powershell
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`; interactive documentation is at `/docs`.

Run tests with `pytest`. The suite uses `test_taskmanager.db`, separate from the normal `taskmanager.db`.
