"""
Ingest LinkedIn / Indeed data.

Expected JSON format (array of objects):
[
  {
    "company": "Infosys",
    "title": "React Developer",
    "location": "Prahlad Nagar",   <- area within Ahmedabad
    "url": "https://...",
    "source": "linkedin"            <- "linkedin" | "indeed"
  },
  ...
]

CSV format — columns: company, title, location, url, source
"""
import csv
import json
import io
from typing import Union


def parse_json(data: Union[str, bytes]) -> list[dict]:
    records = json.loads(data)
    return [_normalize(r) for r in records if _normalize(r)]


def parse_csv(data: Union[str, bytes]) -> list[dict]:
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    reader = csv.DictReader(io.StringIO(data))
    return [_normalize(row) for row in reader if _normalize(row)]


def _normalize(row: dict) -> dict | None:
    company = row.get("company") or row.get("Company") or row.get("company_name")
    title = row.get("title") or row.get("Title") or row.get("job_title")
    location = (
        row.get("location") or row.get("Location") or
        row.get("area") or "Ahmedabad"
    )
    url = row.get("url") or row.get("URL") or row.get("job_url") or ""
    source = row.get("source") or row.get("Source") or "manual"

    if not company or not title:
        return None

    return {
        "company": str(company).strip(),
        "title": str(title).strip(),
        "location_text": str(location).strip(),
        "experience": str(row.get("experience", "")).strip(),
        "url": str(url).strip(),
        "source": str(source).strip().lower(),
    }
