import asyncio
import os
print("LOADING main.py FROM:", os.path.abspath(__file__))
from fastapi import FastAPI, Depends, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, get_db
import models
from geocoder import geocode
from scraper import scrape_all
from scraper_apify import scrape_linkedin_apify
from ingest import parse_json, parse_csv

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ahmedabad Jobs Map API")

ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = (
    ["*"] if ALLOWED_ORIGINS_RAW.strip() == "*"
    else [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",")]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_scrape_status = {"running": False, "last_count": 0, "error": None}


# ── helpers ──────────────────────────────────────────────────────────────────

def _upsert_jobs(records: list[dict], db: Session):
    """Insert or update companies + jobs from a list of normalized records."""
    added = 0
    for r in records:
        # Find or create company
        company = db.query(models.Company).filter_by(name=r["company"]).first()
        if not company:
            lat, lng = geocode(r["location_text"], company_name=r["company"])
            company = models.Company(
                name=r["company"],
                latitude=lat,
                longitude=lng,
                location_text=r["location_text"],
            )
            db.add(company)
            db.flush()

        # Avoid duplicate jobs (same title + source + company)
        exists = (
            db.query(models.Job)
            .filter_by(company_id=company.id, title=r["title"], source=r["source"])
            .first()
        )
        if not exists:
            job = models.Job(
                company_id=company.id,
                title=r["title"],
                experience=r.get("experience", ""),
                url=r.get("url", ""),
                source=r["source"],
            )
            db.add(job)
            added += 1

    db.commit()
    return added


# ── background scrape task ───────────────────────────────────────────────────

def _run_scrape_sync(pages: int):
    """Sync wrapper — runs in a thread so Playwright gets its own event loop."""
    from database import SessionLocal
    _scrape_status["running"] = True
    _scrape_status["error"] = None
    try:
        records = asyncio.run(scrape_all(pages=pages))
        db = SessionLocal()
        added = _upsert_jobs(records, db)
        db.close()
        _scrape_status["last_count"] = added
    except Exception as e:
        _scrape_status["error"] = str(e)
    finally:
        _scrape_status["running"] = False


# ── routes ───────────────────────────────────────────────────────────────────

@app.get("/api/companies")
def list_companies(db: Session = Depends(get_db)):
    companies = db.query(models.Company).all()
    result = []
    for c in companies:
        sources = list({j.source for j in c.jobs})
        result.append({
            "id": c.id,
            "name": c.name,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "location_text": c.location_text,
            "domain": c.domain,
            "job_count": len(c.jobs),
            "sources": sources,
            "titles": [j.title for j in c.jobs],
            "experiences": [j.experience for j in c.jobs if j.experience],
        })
    return result


@app.get("/api/companies/{company_id}/jobs")
def get_company_jobs(company_id: int, db: Session = Depends(get_db)):
    company = db.query(models.Company).filter_by(id=company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return {
        "company": company.name,
        "location_text": company.location_text,
        "jobs": [
            {
                "id": j.id,
                "title": j.title,
                "experience": j.experience,
                "url": j.url,
                "source": j.source,
            }
            for j in company.jobs
        ],
    }


@app.post("/api/scrape")
async def trigger_scrape(background_tasks: BackgroundTasks, pages: int = 3):
    if _scrape_status["running"]:
        return {"message": "Scrape already in progress"}
    background_tasks.add_task(_run_scrape_sync, pages)
    return {"message": f"Scraping Internshala + TimesJobs + Shine ({pages} pages each)"}


# keep old endpoint alias so frontend button still works
@app.post("/api/scrape/naukri")
async def trigger_scrape_legacy(background_tasks: BackgroundTasks, pages: int = 3):
    if _scrape_status["running"]:
        return {"message": "Scrape already in progress"}
    background_tasks.add_task(_run_scrape_sync, pages)
    return {"message": f"Scraping Internshala + TimesJobs + Shine ({pages} pages each)"}


_linkedin_status = {"running": False, "last_count": 0, "error": None}


def _run_linkedin_scrape_sync(queries: int):
    from database import SessionLocal
    _linkedin_status["running"] = True
    _linkedin_status["error"] = None
    try:
        records = asyncio.run(scrape_linkedin_apify(pages=queries))
        db = SessionLocal()
        added = _upsert_jobs(records, db)
        db.close()
        _linkedin_status["last_count"] = added
        print(f"[LinkedIn/Apify] Ingested {added} new jobs")
    except Exception as e:
        _linkedin_status["error"] = str(e)
        print(f"[LinkedIn/Apify] ERROR: {e}")
    finally:
        _linkedin_status["running"] = False


@app.post("/api/scrape/linkedin")
async def trigger_linkedin_scrape(background_tasks: BackgroundTasks, queries: int = 3):
    if _linkedin_status["running"]:
        return {"message": "LinkedIn scrape already in progress"}
    background_tasks.add_task(_run_linkedin_scrape_sync, queries)
    return {"message": f"Scraping LinkedIn via Apify ({queries} search queries)"}


@app.get("/api/scrape/linkedin/status")
def linkedin_scrape_status():
    return _linkedin_status


@app.get("/api/scrape/status")
def scrape_status():
    return _scrape_status


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    rows = (
        db.query(models.Job.source, func.count(models.Job.id))
        .group_by(models.Job.source)
        .all()
    )
    return {source: count for source, count in rows}


ALLOWED_MIME_TYPES = {"application/json", "text/csv", "application/octet-stream"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

@app.post("/api/ingest")
async def ingest_data(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Check file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is 5MB, got {len(content) // 1024}KB"
        )

    filename = file.filename or ""
    content_type = file.content_type or ""

    # Check extension + mime type
    if filename.endswith(".csv") or "csv" in content_type:
        try:
            records = parse_csv(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid CSV: {str(e)}")
    elif filename.endswith(".json") or "json" in content_type:
        try:
            records = parse_json(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    else:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a .json or .csv file."
        )

    added = _upsert_jobs(records, db)
    return {"message": f"Ingested {added} new jobs from {len(records)} records"}
