## Proctoring Backend (FastAPI + MongoDB)

### Setup

1. Install and start MongoDB locally or use MongoDB Atlas
2. Create and activate a virtual environment (recommended)

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Set MongoDB URL (optional, defaults to localhost)

```bash
set MONGODB_URL=mongodb://localhost:27017  # Windows
# or
export MONGODB_URL=mongodb://localhost:27017  # Linux/Mac
```

### Run the server (local)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Deployment: Deta Space

1. Install Space CLI and login (see Deta docs)
2. Ensure `Spacefile` exists (included). It sets `STORAGE_BACKEND=deta`.
3. Push and deploy:

```bash
space push
space deploy
```

Environment variables to configure in Deta Space:

- `MONGODB_URL` (MongoDB Atlas connection string)
- `STORAGE_BACKEND=deta` (default via Spacefile)

Storage behavior:

- When `STORAGE_BACKEND=deta` or running in Deta, videos and reports are stored in Deta Drive buckets `videos` and `reports`.
- Locally, files are stored under `data/videos` and `data/reports` and exposed as static routes.

### API overview

- POST `/sessions` { candidate_name } → create a session
- GET `/sessions` → list sessions
- GET `/sessions/{id}` → session + events
- POST `/sessions/{id}/events` { event_type, message?, timestamp? } → log event
- POST `/sessions/{id}/end` → end session
- POST `/sessions/{id}/video` (multipart file) → upload video file (stored via storage backend)
- POST `/sessions/{id}/video/import` { filename } → import from `frontend/data` to storage
- GET `/sessions/{id}/report` → JSON report; HTML saved to storage
- GET `/sessions/{id}/report.csv` → CSV report download; stored to storage

Static mounts (local only):

- Videos under `/videos/*` (served from `data/videos`)
- Reports under `/reports/*` (served from `data/reports`)

Dynamic fetch (Deta storage):

- `GET /videos/{name}` and `GET /reports/{name}` stream from Deta Drive

### Event types (suggested)

- focus_lost, looking_away, no_face, multiple_faces, phone_detected, notes_detected, device_detected

### Notes

- Uses MongoDB database named "proctoring" with collections "sessions" and "events"
- Integrity score is computed as 100 minus weighted event counts
- All endpoints are now async for better performance with MongoDB
