# Setup

## Backend

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload
```

API runs at http://localhost:8000

## Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at http://localhost:5173

---

## Scraping Naukri

Click **Scrape Naukri** in the UI, or hit the API directly:

```bash
curl -X POST "http://localhost:8000/api/scrape/naukri?pages=5"
```

Check status:
```bash
curl http://localhost:8000/api/scrape/status
```

---

## Ingesting LinkedIn / Indeed data

Prepare a JSON file:
```json
[
  {
    "company": "Infosys",
    "title": "React Developer",
    "location": "Prahlad Nagar",
    "url": "https://linkedin.com/jobs/...",
    "source": "linkedin"
  }
]
```

Or a CSV with columns: `company, title, location, url, source`

Upload via API:
```bash
curl -X POST http://localhost:8000/api/ingest \
  -F "file=@linkedin_jobs.json"
```
