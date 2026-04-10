"""
Apify LinkedIn Jobs Scraper
Uses valig~linkedin-jobs-scraper actor (free tier)
"""
import os
import httpx
import asyncio

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
ACTOR_ID = "valig~linkedin-jobs-scraper"
BASE_URL = "https://api.apify.com/v2"

EXP_LEVEL_MAP = {
    "Internship":       "0 yrs",
    "Entry level":      "0-1 yrs",
    "Associate":        "1-3 yrs",
    "Mid-Senior level": "3-6 yrs",
    "Director":         "7+ yrs",
    "Executive":        "10+ yrs",
}

SEARCH_QUERIES = [
    ("software developer", "Ahmedabad, India"),
    ("full stack developer", "Ahmedabad, India"),
    ("frontend developer", "Ahmedabad, India"),
    ("backend developer", "Ahmedabad, India"),
    ("data engineer", "Ahmedabad, India"),
    ("devops engineer", "Ahmedabad, India"),
]


def _normalize(item: dict) -> dict | None:
    company = (item.get("companyName") or "").strip()
    title   = (item.get("title") or "").strip()
    if not company or not title:
        return None
    return {
        "company":       company,
        "title":         title,
        "location_text": (item.get("location") or "Ahmedabad").split(",")[0].strip(),
        "experience":    EXP_LEVEL_MAP.get(item.get("experienceLevel", ""), ""),
        "url":           item.get("url") or "",
        "source":        "linkedin",
    }


async def scrape_linkedin_apify(pages: int = 2) -> list[dict]:
    """
    Run the Apify LinkedIn actor for multiple search queries.
    `pages` controls how many queries to run (1 query ≈ ~25 jobs).
    """
    results: list[dict] = []

    async with httpx.AsyncClient(timeout=300) as client:
        for i, (keywords, location) in enumerate(SEARCH_QUERIES[:pages * 2]):
            try:
                run_id, dataset_id = await _start_run(client, keywords, location, count=50)
                print(f"[Apify] Started run {run_id} for '{keywords}' in '{location}'")
                await _wait_for_run(client, run_id)
                items = await _fetch_results(client, dataset_id)
                normalized = [n for item in items if (n := _normalize(item))]
                print(f"[Apify] '{keywords}': {len(normalized)} jobs")
                results.extend(normalized)
            except Exception as e:
                print(f"[Apify] FAILED for '{keywords}': {type(e).__name__}: {e}")

    print(f"[Apify] Total LinkedIn jobs: {len(results)}")
    return results


async def _start_run(client: httpx.AsyncClient, keywords: str, location: str, count: int) -> tuple[str, str]:
    resp = await client.post(
        f"{BASE_URL}/acts/{ACTOR_ID}/runs",
        params={"token": APIFY_TOKEN},
        json={"keywords": keywords, "location": location, "count": count},
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    return data["id"], data["defaultDatasetId"]


async def _wait_for_run(client: httpx.AsyncClient, run_id: str, poll_interval: int = 8, max_wait: int = 300):
    elapsed = 0
    while elapsed < max_wait:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        resp = await client.get(
            f"{BASE_URL}/actor-runs/{run_id}",
            params={"token": APIFY_TOKEN},
        )
        resp.raise_for_status()
        status = resp.json()["data"]["status"]
        if status == "SUCCEEDED":
            return
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify run {run_id} ended with status: {status}")
    raise TimeoutError(f"Apify run {run_id} did not finish within {max_wait}s")


async def _fetch_results(client: httpx.AsyncClient, dataset_id: str) -> list[dict]:
    resp = await client.get(
        f"{BASE_URL}/datasets/{dataset_id}/items",
        params={"token": APIFY_TOKEN, "limit": 200},
    )
    resp.raise_for_status()
    return resp.json()
