"""
Multi-source job scraper for Ahmedabad.
Primary: LinkedIn (linkedin-jobs-scraper library)
Fallback: Internshala, TimesJobs, Shine (Playwright)
"""
import asyncio
import re
from playwright.async_api import async_playwright, Browser

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


async def scrape_all(pages: int = 5) -> list[dict]:
    # Try LinkedIn first
    linkedin_results = []
    try:
        from scraper_linkedin import scrape_linkedin
        print("[Scraper] Trying LinkedIn...")
        linkedin_results = await scrape_linkedin(max_jobs=pages * 25)
        print(f"[Scraper] LinkedIn returned {len(linkedin_results)} jobs")
    except Exception as e:
        print(f"[Scraper] LinkedIn failed ({e}), falling back to Internshala/TimesJobs/Shine")

    if linkedin_results:
        return linkedin_results

    print("[Scraper] Using fallback scrapers...")
    return await _scrape_fallback(pages)


async def _scrape_fallback(pages: int) -> list[dict]:
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            tasks = [
                ("internshala", scrape_internshala(browser, pages)),
                ("timesjobs", scrape_timesjobs(browser, pages)),
                ("shine", scrape_shine(browser, pages)),
            ]
            gathered = await asyncio.gather(
                *[t for _, t in tasks],
                return_exceptions=True
            )
            for (name, _), result in zip(tasks, gathered):
                if isinstance(result, Exception):
                    print(f"[Scraper] {name} FAILED: {type(result).__name__}: {result}")
                else:
                    print(f"[Scraper] {name} OK: {len(result)} jobs")
                    results.extend(result)
        finally:
            await browser.close()
    print(f"[Scraper] Fallback total: {len(results)}")
    return results


# ── Internshala ───────────────────────────────────────────────────────────────

async def scrape_internshala(browser: Browser, pages: int) -> list[dict]:
    results = []
    ctx = await browser.new_context(user_agent=UA)
    page = await ctx.new_page()

    for page_no in range(1, pages + 1):
        url = f"https://internshala.com/jobs/computer-science,information-technology/ahmedabad/page-{page_no}/"
        print(f"[Internshala] page {page_no}: {url}")
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            if response and response.status == 429:
                print(f"[Internshala] Rate limited (429), stopping")
                break
            await page.wait_for_timeout(3000)

            cards = await page.query_selector_all(".individual_internship")
            print(f"[Internshala] {len(cards)} cards")

            for card in cards:
                try:
                    title_el = await card.query_selector("h2.job-internship-name a, a.job-title-href")
                    title = (await title_el.inner_text()).strip() if title_el else None

                    href = await title_el.get_attribute("href") if title_el else None
                    url_job = f"https://internshala.com{href}" if href and href.startswith("/") else (href or "")

                    company_el = await card.query_selector("p.company-name")
                    company = (await company_el.inner_text()).strip() if company_el else None

                    # location — try multiple selectors
                    loc_el = await card.query_selector(".location_link, .locations, .job-location, [class*='location']")
                    location_raw = (await loc_el.inner_text()).strip() if loc_el else "Ahmedabad"
                    location_text = _extract_ahmedabad_area(location_raw)

                    if company and title:
                        results.append({
                            "company": company,
                            "title": title,
                            "location_text": location_text,
                            "experience": "",
                            "url": url_job,
                            "source": "internshala",
                        })
                except Exception as e:
                    print(f"[Internshala] card error: {e}")

        except Exception as e:
            print(f"[Internshala] page {page_no} error: {e}")
            break

    await ctx.close()
    print(f"[Internshala] collected {len(results)} jobs")
    return results


# ── TimesJobs ─────────────────────────────────────────────────────────────────

async def scrape_timesjobs(browser: Browser, pages: int) -> list[dict]:
    results = []
    ctx = await browser.new_context(user_agent=UA)
    page = await ctx.new_page()

    for page_no in range(1, pages + 1):
        seq = (page_no - 1) * 10 + 1
        url = (
            "https://www.timesjobs.com/candidate/job-search.html"
            f"?searchType=personalizedSearch&from=submit"
            f"&txtKeywords=developer+engineer&txtLocation=Ahmedabad&sequence={seq}&startPage={page_no}"
        )
        print(f"[TimesJobs] page {page_no}: {url}")
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            if response and response.status == 429:
                print(f"[TimesJobs] Rate limited (429), stopping")
                break
            await page.wait_for_timeout(4000)

            cards = await page.query_selector_all("div.srp-card")
            print(f"[TimesJobs] {len(cards)} cards")

            for card in cards:
                try:
                    title_el = await card.query_selector("h2")
                    title = (await title_el.inner_text()).strip() if title_el else None

                    # company is the first span inside the gray meta line
                    comp_el = await card.query_selector("div.text-xs span:first-child, span.text-gray-400")
                    company = (await comp_el.inner_text()).strip() if comp_el else None
                    if company:
                        company = company.split("|")[0].strip()

                    # experience — look for "yrs" pattern in card text
                    card_text = await card.inner_text()
                    exp_match = re.search(r"(\d+\s*[-–]\s*\d+\s*(?:yrs?|years?)|\d+\+?\s*(?:yrs?|years?))", card_text, re.I)
                    experience = exp_match.group(0).strip() if exp_match else ""

                    # job URL — try to find an anchor
                    link_el = await card.query_selector("a[href*='job-detail'], a[href*='timesjobs']")
                    job_url = await link_el.get_attribute("href") if link_el else ""

                    if company and title:
                        results.append({
                            "company": company,
                            "title": title,
                            "location_text": "Ahmedabad",
                            "experience": experience,
                            "url": job_url,
                            "source": "timesjobs",
                        })
                except Exception as e:
                    print(f"[TimesJobs] card error: {e}")

        except Exception as e:
            print(f"[TimesJobs] page {page_no} error: {e}")
            break

    await ctx.close()
    print(f"[TimesJobs] collected {len(results)} jobs")
    return results


# ── Shine ─────────────────────────────────────────────────────────────────────

async def scrape_shine(browser: Browser, pages: int) -> list[dict]:
    results = []
    ctx = await browser.new_context(user_agent=UA)
    page = await ctx.new_page()

    for page_no in range(1, pages + 1):
        url = f"https://www.shine.com/job-search/it-software-jobs-in-ahmedabad/?page={page_no}"
        print(f"[Shine] page {page_no}: {url}")
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            if response and response.status == 429:
                print(f"[Shine] Rate limited (429), stopping")
                break
            await page.wait_for_timeout(4000)

            cards = await page.query_selector_all("[class*='jobCardNova_bigCard']")
            print(f"[Shine] {len(cards)} cards")

            for card in cards:
                try:
                    title_el = await card.query_selector("h3[class*='Heading'], h2[class*='Heading'], h3, h2")
                    title = (await title_el.inner_text()).strip() if title_el else None

                    comp_el = await card.query_selector("[class*='TitleName'], [class*='companyName'], [class*='Company']")
                    company = (await comp_el.inner_text()).strip() if comp_el else None

                    exp_el = await card.query_selector("[class*='Exp'], [class*='experience']")
                    experience = (await exp_el.inner_text()).strip() if exp_el else ""

                    loc_el = await card.query_selector("[class*='Loc'], [class*='location']")
                    location_raw = (await loc_el.inner_text()).strip() if loc_el else "Ahmedabad"
                    location_text = _extract_ahmedabad_area(location_raw)

                    link_el = await card.query_selector("a[href]")
                    href = await link_el.get_attribute("href") if link_el else ""
                    job_url = f"https://www.shine.com{href}" if href and href.startswith("/") else href

                    if company and title:
                        results.append({
                            "company": company,
                            "title": title,
                            "location_text": location_text,
                            "experience": experience,
                            "url": job_url,
                            "source": "shine",
                        })
                except Exception as e:
                    print(f"[Shine] card error: {e}")

        except Exception as e:
            print(f"[Shine] page {page_no} error: {e}")
            break

    await ctx.close()
    print(f"[Shine] collected {len(results)} jobs")
    return results


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_ahmedabad_area(raw: str) -> str:
    """Return the most specific Ahmedabad area from a location string."""
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

    # If explicitly not Ahmedabad, return "Ahmedabad" as fallback
    if "ahmedabad" not in raw_lower and raw.strip():
        return "Ahmedabad"
    return raw.strip() or "Ahmedabad"
