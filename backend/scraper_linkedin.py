"""
LinkedIn scraper using linkedin-jobs-scraper library.
Falls back gracefully if it fails (auth required, blocked, etc.)
"""
import asyncio
import logging
from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import Events, EventData, EventMetrics
from linkedin_jobs_scraper.query import Query, QueryOptions, QueryFilters
from linkedin_jobs_scraper.filters import RelevanceFilters, TimeFilters, TypeFilters

logging.getLogger("linkedin_jobs_scraper").setLevel(logging.WARNING)


async def scrape_linkedin(max_jobs: int = 100) -> list[dict]:
    results = []
    errors = []
    done = asyncio.Event()

    def on_data(data: EventData):
        company = (data.company or "").strip()
        title = (data.title or "").strip()
        if not company or not title:
            return

        location_raw = (data.place or "Ahmedabad").strip()
        location_text = _extract_ahmedabad_area(location_raw)

        results.append({
            "company": company,
            "title": title,
            "location_text": location_text,
            "experience": "",
            "url": data.link or "",
            "source": "linkedin",
        })

    def on_error(error):
        errors.append(str(error))
        print(f"[LinkedIn] error: {error}")

    def on_end():
        done.set()

    import os
    from linkedin_jobs_scraper.linkedin_scraper import Config
    os.environ["LI_AT_COOKIE"] = "AQEDAT3mlXwBrONdAAABnPBSQZIAAAGdhbPw0k0AZLhx2sY5f9mcNolsKddnjy0kZ_7DruW1S5qnBzamYlmUh00yT82HFHFT3DgOGevaq3Q2a28nR9De6BZqJFFkwXxXcVtAAnS5_D_MAc4usqEXvDiJ"
    Config.LI_AT_COOKIE = os.environ["LI_AT_COOKIE"]

    scraper = LinkedinScraper(
        chrome_executable_path=None,  # uses system chromedriver
        headless=True,
        max_workers=1,
        slow_mo=1.2,
        page_load_timeout=40,
    )

    scraper.on(Events.DATA, on_data)
    scraper.on(Events.ERROR, on_error)
    scraper.on(Events.END, on_end)

    queries = [
        Query(
            query="Software Engineer",
            options=QueryOptions(
                locations=["Ahmedabad, Gujarat, India"],
                apply_link=True,
                limit=max_jobs // 4,
                filters=QueryFilters(
                    relevance=RelevanceFilters.RECENT,
                    time=TimeFilters.MONTH,
                ),
            ),
        ),
        Query(
            query="React Developer",
            options=QueryOptions(
                locations=["Ahmedabad, Gujarat, India"],
                apply_link=True,
                limit=max_jobs // 4,
                filters=QueryFilters(
                    relevance=RelevanceFilters.RECENT,
                    time=TimeFilters.MONTH,
                ),
            ),
        ),
        Query(
            query="Python Developer",
            options=QueryOptions(
                locations=["Ahmedabad, Gujarat, India"],
                apply_link=True,
                limit=max_jobs // 4,
                filters=QueryFilters(
                    relevance=RelevanceFilters.RECENT,
                    time=TimeFilters.MONTH,
                ),
            ),
        ),
        Query(
            query="Full Stack Developer",
            options=QueryOptions(
                locations=["Ahmedabad, Gujarat, India"],
                apply_link=True,
                limit=max_jobs // 4,
                filters=QueryFilters(
                    relevance=RelevanceFilters.RECENT,
                    time=TimeFilters.MONTH,
                ),
            ),
        ),
    ]

    try:
        scraper.run(queries)
        # Wait up to 5 minutes for completion
        await asyncio.wait_for(done.wait(), timeout=300)
    except asyncio.TimeoutError:
        print("[LinkedIn] Timed out waiting for results")
    except Exception as e:
        print(f"[LinkedIn] Scraper failed: {e}")
        return []
    finally:
        try:
            scraper.close()
        except Exception:
            pass

    if errors and not results:
        print(f"[LinkedIn] All queries failed, errors: {errors}")
        return []

    print(f"[LinkedIn] Collected {len(results)} jobs")
    return results


def _extract_ahmedabad_area(raw: str) -> str:
    known_areas = [
        "Prahlad Nagar", "SG Highway", "Satellite", "Bodakdev", "Thaltej",
        "Vastrapur", "Navrangpura", "Makarba", "Anandnagar", "Maninagar",
        "Chandkheda", "Bopal", "South Bopal", "Gota", "Motera", "Sabarmati",
        "Naroda", "Vatva", "Odhav", "GIFT City", "Gandhinagar", "Sola",
        "Science City", "Prahladnagar", "Ambawadi", "Ellis Bridge",
    ]
    raw_lower = raw.lower()
    for area in known_areas:
        if area.lower() in raw_lower:
            return area
    return "Ahmedabad"
