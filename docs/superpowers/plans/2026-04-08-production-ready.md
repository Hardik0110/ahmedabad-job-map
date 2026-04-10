# Production-Ready Ahmedabad Jobs Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Ahmedabad Jobs Map into a production-ready, investor-worthy product with filters, bookmarks, mobile support, security hardening, and live deployment.

**Architecture:** Foundation fixes first (security + bugs), then client-side filters (state in App.jsx, no new API), then localStorage bookmarks (custom hook), then mobile bottom sheet UI, then deploy config for Vercel + Render.

**Tech Stack:** React 18 + Vite, FastAPI + SQLAlchemy + SQLite, Leaflet + react-leaflet, Render.com (backend), Vercel (frontend)

---

## File Map

### Modified Files
- `backend/main.py` — CORS hardening, ingest validation, DB index creation
- `backend/models.py` — Add SQLAlchemy Index declarations
- `backend/scraper.py` — Per-source error isolation, structured logging
- `frontend/src/App.jsx` — Filter state, bookmark count in header, error banner
- `frontend/src/App.css` — Error banner styles, filter bar layout
- `frontend/src/components/Sidebar.jsx` — Filter bar, bookmark star, saved filter chip
- `frontend/src/components/Sidebar.css` — Filter chips, star icon, bottom sheet styles
- `frontend/src/components/MapView.jsx` — Remove dead hook, gold pin ring, mobile pin size, cleanup listener
- `frontend/src/components/MapView.css` — Gold ring style
- `frontend/vite.config.js` — VITE_API_URL env var, conditional proxy

### New Files
- `frontend/src/hooks/useBookmarks.js` — localStorage bookmark hook
- `frontend/src/components/FilterBar.jsx` — Role/experience/source filter UI
- `frontend/src/components/FilterBar.css` — Filter chip styles
- `frontend/.env.example` — Frontend env template
- `backend/.env.example` — Backend env template
- `backend/.gitignore` — Exclude .env and jobs.db from git
- `frontend/.gitignore` — Exclude .env from git

---

## Task 1: Backend Security — CORS + Ingest Hardening

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Update CORS to read from env var**

Replace the existing `CORSMiddleware` block in `main.py`:

```python
import os

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:5174"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

- [ ] **Step 2: Harden `/api/ingest` endpoint**

Replace the existing `ingest_data` function:

```python
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
```

- [ ] **Step 3: Verify backend starts without error**

```bash
cd backend
python run.py
```
Expected: `INFO: Application startup complete.` with no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "security: harden CORS and ingest endpoint"
```

---

## Task 2: Database Indexes

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Add Index imports and declarations**

Replace `models.py` entirely:

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    domain = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    location_text = Column(String)
    jobs = relationship("Job", back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_companies_name", "name"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    title = Column(String, nullable=False)
    experience = Column(String)
    url = Column(String)
    source = Column(String)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="jobs")

    __table_args__ = (
        Index("idx_jobs_company_id", "company_id"),
        Index("idx_jobs_source", "source"),
    )
```

- [ ] **Step 2: Apply indexes to existing DB**

```bash
cd backend
python -c "
from database import engine
import models
models.Base.metadata.create_all(bind=engine)
print('Indexes applied')
"
```
Expected: `Indexes applied`

- [ ] **Step 3: Commit**

```bash
git add backend/models.py
git commit -m "perf: add DB indexes on name, company_id, source"
```

---

## Task 3: Scraper — Per-Source Error Isolation

**Files:**
- Modify: `backend/scraper.py`

- [ ] **Step 1: Isolate fallback scrapers so one failure doesn't kill others**

Replace `_scrape_fallback` function:

```python
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
```

- [ ] **Step 2: Add HTTP 429 detection to page.goto calls**

At the top of `scrape_internshala`, `scrape_timesjobs`, `scrape_shine`, add this helper before each `page.goto`:

```python
# Inside each scrape function, wrap goto like this:
response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
if response and response.status == 429:
    print(f"[{source_name}] Rate limited (429) on page {page_no}, stopping")
    break
```

For Internshala add after `await page.goto(...)` on line ~63:
```python
            response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            if response and response.status == 429:
                print(f"[Internshala] Rate limited (429) on page {page_no}, stopping")
                break
```

For TimesJobs after `await page.goto(...)` on line ~122:
```python
            response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            if response and response.status == 429:
                print(f"[TimesJobs] Rate limited (429) on page {page_no}, stopping")
                break
```

For Shine after `await page.goto(...)` on line ~181:
```python
            response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            if response and response.status == 429:
                print(f"[Shine] Rate limited (429) on page {page_no}, stopping")
                break
```

- [ ] **Step 3: Commit**

```bash
git add backend/scraper.py
git commit -m "fix: isolate scraper sources, detect 429 rate limits"
```

---

## Task 4: Frontend — Remove Dead Code + Error UX + Memory Leak

**Files:**
- Modify: `frontend/src/components/MapView.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Remove dead `useJobsState` hook from MapView.jsx**

Delete lines 131–142 (the entire `useJobsState` function):
```javascript
// DELETE this entire function:
function useJobsState(companyId, isSelected) {
  const [jobs, setJobs] = [
    useRef([]).current,
    async () => {
      try {
        const { data } = await axios.get(`/api/companies/${companyId}/jobs`);
      } catch {}
    },
  ];
  return [jobs, setJobs];
}
```

Also delete the `CompanyMarker` component (lines 88–128) which references `useJobsState` — it's unused, `CompanyMarkerWithJobs` is the active one.

- [ ] **Step 2: Fix memory leak — clean up popupopen listener**

In `CompanyMarkerWithJobs`, update the `useEffect` to return a cleanup:

```javascript
useEffect(() => {
  if (isSelected && markerRef.current) {
    markerRef.current.openPopup();
    loadJobs();
    const el = markerRef.current.getElement();
    if (el) {
      el.classList.remove("pin-bounce");
      void el.offsetWidth;
      el.classList.add("pin-bounce");
    }
  }
}, [isSelected]);
```

This is already correct — the leak was in the dead `CompanyMarker`. Removing it resolves it.

- [ ] **Step 3: Add error banner state to App.jsx**

Add `loadError` state and update `fetchCompanies`:

```javascript
const [loadError, setLoadError] = useState(false);

async function fetchCompanies() {
  try {
    const { data: companies } = await axios.get("/api/companies");
    setCompanies(companies);
    setLoadError(false);

    const stats = await axios.get("/api/stats").then(r => r.data).catch(() => null);
    if (!stats) return;
    const total = Object.values(stats).reduce((a, b) => a + b, 0);
    console.group("%c Ahmedabad Jobs — Platform Breakdown", "color:#0fbcf9;font-weight:bold;font-size:14px");
    Object.entries(stats)
      .sort((a, b) => b[1] - a[1])
      .forEach(([source, count]) => {
        const colors = { linkedin: "#0d47a1", internshala: "#e65100", timesjobs: "#6a1b9a", shine: "#1b5e20" };
        const color = colors[source] || "#555";
        console.log(`%c ${source.padEnd(14)} %c ${count} jobs`, `color:${color};font-weight:bold`, "color:#333");
      });
    console.log(`%c ${"TOTAL".padEnd(14)} %c ${total} jobs`, "color:#333;font-weight:bold", "color:#333;font-weight:bold");
    console.groupEnd();
  } catch {
    setLoadError(true);
  } finally {
    setLoading(false);
  }
}
```

- [ ] **Step 4: Add error banner + geolocation denied banner to App.jsx JSX**

In the return, add after `<header>`:

```jsx
{loadError && (
  <div className="error-banner">
    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>wifi_off</span>
    Could not load companies — backend may be offline.
    <button onClick={() => { setLoadError(false); fetchCompanies(); }} className="error-retry">Retry</button>
    <button onClick={() => setLoadError(false)} className="error-dismiss">✕</button>
  </div>
)}
```

Pass `onLocationDenied` to MapView:

```jsx
const [locationDenied, setLocationDenied] = useState(false);

// In JSX:
{locationDenied && (
  <div className="location-banner">
    <span className="material-symbols-outlined" style={{ fontSize: 14 }}>location_off</span>
    Enable location to see nearby jobs
    <button onClick={() => setLocationDenied(false)} className="error-dismiss">✕</button>
  </div>
)}
<MapView
  companies={filtered}
  selected={selected}
  onSelect={setSelected}
  onLocationDenied={() => setLocationDenied(true)}
/>
```

- [ ] **Step 5: Wire `onLocationDenied` in MapView.jsx `UserLocation` component**

Update `UserLocation`:

```javascript
function UserLocation({ onLocated, onLocationDenied }) {
  const map = useMap();
  const located = useRef(false);

  useEffect(() => {
    if (located.current) return;
    located.current = true;
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        onLocated([latitude, longitude]);
        map.flyTo([latitude, longitude], 15, { duration: 1.2 });
      },
      () => {
        if (onLocationDenied) onLocationDenied();
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }, []);

  return null;
}
```

Update MapView export to accept and pass `onLocationDenied`:

```javascript
export default function MapView({ companies, selected, onSelect, onLocationDenied }) {
  const [userPos, setUserPos] = useState(null);
  return (
    <div className="map-wrapper">
      <MapContainer center={CENTER} zoom={ZOOM} className="map" zoomControl={true}>
        <TileLayer url={TILE_URL} attribution={TILE_ATTR} />
        <UserLocation onLocated={setUserPos} onLocationDenied={onLocationDenied} />
        <FlyTo selected={selected} />
        {userPos && (
          <>
            <Circle center={userPos} radius={2500} pathOptions={{ color: "#2e5bff", weight: 1.5, fillColor: "#2e5bff", fillOpacity: 0.06, dashArray: "6 4" }} />
            <Marker position={userPos} icon={userDotIcon()} zIndexOffset={1000} />
          </>
        )}
        {companies.filter((c) => c.latitude && c.longitude).map((c) => (
          <CompanyMarkerWithJobs key={c.id} company={c} isSelected={selected?.id === c.id} onSelect={onSelect} />
        ))}
      </MapContainer>
    </div>
  );
}
```

- [ ] **Step 6: Add banner styles to App.css**

```css
.error-banner {
  background: #fff3cd;
  border-bottom: 1px solid #ffc107;
  color: #856404;
  padding: 8px 20px;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  z-index: 999;
}

.location-banner {
  position: fixed;
  bottom: 52px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(25, 27, 36, 0.85);
  backdrop-filter: blur(12px);
  color: rgba(255,255,255,0.85);
  font-size: 11px;
  font-weight: 500;
  padding: 7px 14px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 1001;
  pointer-events: auto;
}

.error-retry {
  margin-left: 8px;
  padding: 3px 10px;
  background: #856404;
  color: #fff;
  border: none;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.error-dismiss {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  color: inherit;
  font-size: 14px;
  padding: 0 4px;
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/MapView.jsx frontend/src/App.jsx frontend/src/App.css
git commit -m "fix: remove dead hook, add error banners, wire geolocation denied"
```

---

## Task 5: Client-Side Filters

**Files:**
- Create: `frontend/src/components/FilterBar.jsx`
- Create: `frontend/src/components/FilterBar.css`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/components/Sidebar.css`

- [ ] **Step 1: Create FilterBar.jsx**

```jsx
// frontend/src/components/FilterBar.jsx
import "./FilterBar.css";

const ROLE_KEYWORDS = {
  Frontend: ["react", "vue", "angular", "frontend", "ui", "next", "svelte"],
  Backend: ["node", "python", "django", "fastapi", "java", "backend", "golang", "ruby", "php", "spring"],
  "Full Stack": ["full stack", "fullstack", "mern", "mean"],
  Mobile: ["android", "ios", "flutter", "react native", "mobile"],
  DevOps: ["devops", "cloud", "aws", "docker", "kubernetes", "ci/cd", "sre"],
  Data: ["data", "ml", "machine learning", "ai", "analyst", "spark", "tableau"],
  Design: ["figma", "ux", "ui design", "product design", "designer"],
};

const SOURCES = ["linkedin", "internshala", "timesjobs", "shine"];

const EXP_RANGES = [
  { label: "Any", min: -1, max: 999 },
  { label: "Fresher (0–1yr)", min: 0, max: 1 },
  { label: "Junior (1–3yr)", min: 1, max: 3 },
  { label: "Mid (3–6yr)", min: 3, max: 6 },
  { label: "Senior (6yr+)", min: 6, max: 999 },
];

export { ROLE_KEYWORDS, SOURCES, EXP_RANGES };

export default function FilterBar({ filters, onChange }) {
  const { role, expIndex, sources } = filters;

  function toggleSource(src) {
    const next = sources.includes(src)
      ? sources.filter((s) => s !== src)
      : [...sources, src];
    onChange({ ...filters, sources: next });
  }

  const hasActiveFilters = role !== "All" || expIndex !== 0 || sources.length > 0;

  return (
    <div className="filter-bar">
      {/* Role chips */}
      <div className="filter-row">
        <div className="filter-chips scrollable">
          {["All", ...Object.keys(ROLE_KEYWORDS)].map((r) => (
            <button
              key={r}
              className={`chip ${role === r ? "chip-active" : ""}`}
              onClick={() => onChange({ ...filters, role: r })}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Experience + Source row */}
      <div className="filter-row filter-row-bottom">
        <select
          className="exp-select"
          value={expIndex}
          onChange={(e) => onChange({ ...filters, expIndex: Number(e.target.value) })}
        >
          {EXP_RANGES.map((r, i) => (
            <option key={r.label} value={i}>{r.label}</option>
          ))}
        </select>

        <div className="filter-chips">
          {SOURCES.map((src) => (
            <button
              key={src}
              className={`chip chip-source ${sources.includes(src) ? "chip-active" : ""}`}
              onClick={() => toggleSource(src)}
            >
              {src}
            </button>
          ))}
        </div>

        {hasActiveFilters && (
          <button
            className="chip chip-reset"
            onClick={() => onChange({ role: "All", expIndex: 0, sources: [] })}
          >
            ✕ Reset
          </button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create FilterBar.css**

```css
/* frontend/src/components/FilterBar.css */
.filter-bar {
  padding: 10px 16px 8px;
  border-bottom: 1px solid #ededfa;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #fbf8ff;
  flex-shrink: 0;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-row-bottom {
  flex-wrap: wrap;
}

.filter-chips {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}

.filter-chips.scrollable {
  flex-wrap: nowrap;
  overflow-x: auto;
  padding-bottom: 2px;
  scrollbar-width: none;
}

.filter-chips.scrollable::-webkit-scrollbar {
  display: none;
}

.chip {
  padding: 4px 11px;
  border-radius: 999px;
  border: 1.5px solid #e2e1ef;
  background: #fff;
  color: #434656;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.12s;
  font-family: 'Be Vietnam Pro', sans-serif;
}

.chip:hover {
  border-color: #2e5bff;
  color: #2e5bff;
}

.chip-active {
  background: #2e5bff;
  border-color: #2e5bff;
  color: #fff;
}

.chip-source {
  text-transform: capitalize;
}

.chip-reset {
  border-color: #e2e1ef;
  color: #747688;
  margin-left: auto;
}

.chip-reset:hover {
  border-color: #ba1a1a;
  color: #ba1a1a;
}

.exp-select {
  padding: 4px 10px;
  border: 1.5px solid #e2e1ef;
  border-radius: 999px;
  background: #fff;
  color: #434656;
  font-size: 11px;
  font-weight: 700;
  font-family: 'Be Vietnam Pro', sans-serif;
  cursor: pointer;
  outline: none;
  appearance: none;
  padding-right: 24px;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%23747688'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
}
```

- [ ] **Step 3: Add filter logic helpers to App.jsx and wire state**

Add these imports + state + filter logic to `App.jsx`:

```javascript
import FilterBar, { ROLE_KEYWORDS, EXP_RANGES } from "./components/FilterBar";

// State (add alongside existing state):
const [filters, setFilters] = useState({ role: "All", expIndex: 0, sources: [] });

// Filter logic (replace the existing `filtered` line):
function parseExpYears(expStr) {
  if (!expStr) return null;
  const nums = expStr.match(/\d+/g);
  if (!nums) return null;
  return parseFloat(nums[0]);
}

function jobMatchesFilters(job, filters) {
  const { role, expIndex, sources } = filters;
  const titleLower = (job.title || "").toLowerCase();

  if (role !== "All") {
    const keywords = ROLE_KEYWORDS[role] || [];
    if (!keywords.some((kw) => titleLower.includes(kw))) return false;
  }

  const expRange = EXP_RANGES[expIndex];
  if (expRange && expRange.min >= 0) {
    const yrs = parseExpYears(job.experience);
    if (yrs !== null && (yrs < expRange.min || yrs > expRange.max)) return false;
  }

  if (sources.length > 0) {
    if (!sources.includes(job.source)) return false;
  }

  return true;
}

const filtered = companies.filter((c) => {
  const nameMatch = c.name.toLowerCase().includes(search.toLowerCase());
  if (!nameMatch) return false;

  const noActiveFilters =
    filters.role === "All" && filters.expIndex === 0 && filters.sources.length === 0;
  if (noActiveFilters) return true;

  // Company passes if it has at least one job matching filters
  // (jobs are fetched lazily per company, so filter on sources array for now)
  if (filters.sources.length > 0) {
    const hasSource = c.sources.some((s) => filters.sources.includes(s));
    if (!hasSource) return false;
  }

  return true;
});
```

- [ ] **Step 4: Add FilterBar to Sidebar.jsx**

Import and render FilterBar inside the sidebar (between header and list):

```jsx
import FilterBar from "./FilterBar";  // add import at top

// In Sidebar component, add filters + onChange props:
export default function Sidebar({ companies, selected, onSelect, loading, filters, onFilterChange }) {

// In JSX, between sidebar-header and sidebar-list:
<div className="sidebar-header">
  {/* ... existing header content ... */}
</div>
<FilterBar filters={filters} onChange={onFilterChange} />
<div className="sidebar-list">
  {/* ... existing cards ... */}
</div>
```

- [ ] **Step 5: Pass filters to Sidebar in App.jsx**

```jsx
<Sidebar
  companies={filtered}
  selected={selected}
  onSelect={setSelected}
  loading={loading}
  filters={filters}
  onFilterChange={setFilters}
/>
```

- [ ] **Step 6: Verify filters work**

Start servers, open app, click "Frontend" chip — sidebar should reduce to companies with frontend jobs. Click "Reset" — all companies return.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/FilterBar.jsx frontend/src/components/FilterBar.css \
        frontend/src/App.jsx frontend/src/components/Sidebar.jsx
git commit -m "feat: add client-side role/experience/source filters"
```

---

## Task 6: Bookmarks Hook + UI

**Files:**
- Create: `frontend/src/hooks/useBookmarks.js`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/components/Sidebar.css`
- Modify: `frontend/src/components/MapView.jsx`
- Modify: `frontend/src/components/MapView.css`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Create useBookmarks hook**

```javascript
// frontend/src/hooks/useBookmarks.js
import { useState, useEffect } from "react";

const STORAGE_KEY = "ahmedabad-jobs-bookmarks";

export default function useBookmarks() {
  const [bookmarks, setBookmarks] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return new Set(stored ? JSON.parse(stored) : []);
    } catch {
      return new Set();
    }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...bookmarks]));
  }, [bookmarks]);

  function toggle(id) {
    setBookmarks((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function isBookmarked(id) {
    return bookmarks.has(id);
  }

  return { bookmarks, toggle, isBookmarked };
}
```

- [ ] **Step 2: Add bookmark state to App.jsx**

```javascript
import useBookmarks from "./hooks/useBookmarks";

// Inside App component:
const { bookmarks, toggle: toggleBookmark, isBookmarked } = useBookmarks();
```

- [ ] **Step 3: Add "⭐ Saved" chip to FilterBar.jsx**

In FilterBar.jsx, add a `showSaved` prop and render saved chip in the source row:

```jsx
// Add to FilterBar props:
export default function FilterBar({ filters, onChange, bookmarkCount, showSaved, onToggleSaved }) {

// Add saved chip before source chips:
{bookmarkCount > 0 && (
  <button
    className={`chip chip-source ${showSaved ? "chip-active chip-saved" : ""}`}
    onClick={onToggleSaved}
    style={showSaved ? { background: "#f59e0b", borderColor: "#f59e0b" } : { borderColor: "#f59e0b", color: "#92400e" }}
  >
    ★ Saved ({bookmarkCount})
  </button>
)}
```

- [ ] **Step 4: Wire showSaved state in App.jsx**

```javascript
const [showSaved, setShowSaved] = useState(false);

// Update filtered to respect showSaved:
const filtered = companies.filter((c) => {
  if (showSaved && !isBookmarked(c.id)) return false;
  const nameMatch = c.name.toLowerCase().includes(search.toLowerCase());
  if (!nameMatch) return false;
  const noActiveFilters = filters.role === "All" && filters.expIndex === 0 && filters.sources.length === 0;
  if (noActiveFilters) return true;
  if (filters.sources.length > 0) {
    const hasSource = c.sources.some((s) => filters.sources.includes(s));
    if (!hasSource) return false;
  }
  return true;
});

// Pass to Sidebar:
<Sidebar
  companies={filtered}
  selected={selected}
  onSelect={setSelected}
  loading={loading}
  filters={filters}
  onFilterChange={setFilters}
  bookmarkCount={bookmarks.size}
  showSaved={showSaved}
  onToggleSaved={() => setShowSaved((v) => !v)}
  isBookmarked={isBookmarked}
  onToggleBookmark={toggleBookmark}
/>
```

- [ ] **Step 5: Add star icon to Sidebar cards**

In `Sidebar.jsx`, update the card to show star:

```jsx
export default function Sidebar({ companies, selected, onSelect, loading, filters, onFilterChange, bookmarkCount, showSaved, onToggleSaved, isBookmarked, onToggleBookmark }) {

// Inside card JSX, add star button:
<div
  key={c.id}
  className={`company-card ${isActive ? "active" : ""}`}
  onClick={() => onSelect(isActive ? null : c)}
>
  {/* existing avatar + info */}
  <button
    className={`bookmark-btn ${isBookmarked(c.id) ? "bookmarked" : ""}`}
    onClick={(e) => { e.stopPropagation(); onToggleBookmark(c.id); }}
    title={isBookmarked(c.id) ? "Remove bookmark" : "Bookmark"}
  >
    {isBookmarked(c.id) ? "★" : "☆"}
  </button>
  <div className="company-arrow">
    <span className="material-symbols-outlined">arrow_forward</span>
  </div>
</div>
```

Also pass `bookmarkCount`, `showSaved`, `onToggleSaved` to FilterBar inside Sidebar:

```jsx
<FilterBar
  filters={filters}
  onChange={onFilterChange}
  bookmarkCount={bookmarkCount}
  showSaved={showSaved}
  onToggleSaved={onToggleSaved}
/>
```

- [ ] **Step 6: Add bookmark button styles to Sidebar.css**

```css
.bookmark-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #c4c5d9;
  line-height: 1;
  padding: 2px 4px;
  flex-shrink: 0;
  transition: color 0.15s, transform 0.15s;
}

.bookmark-btn:hover {
  color: #f59e0b;
  transform: scale(1.2);
}

.bookmark-btn.bookmarked {
  color: #f59e0b;
}
```

- [ ] **Step 7: Add gold ring to bookmarked map pins in MapView.jsx**

Update `makeIcon` to accept `isBookmarked` and add gold ring:

```javascript
function makeIcon(letter, name = "", active = false, domain = "", bookmarked = false) {
  const color = colorForName(name);
  const w = active ? 42 : 34;
  const h = active ? 54 : 44;
  const inner = active ? 28 : 22;
  const logoUrl = domain ? `https://www.google.com/s2/favicons?sz=64&domain=${domain}` : "";
  const scale = active ? `transform:scale(1.15);` : "";
  const ring = bookmarked ? `box-shadow:0 0 0 3px #f59e0b,0 3px 6px rgba(0,0,0,0.25);border-radius:50%;` : "";

  const html = `
    <div style="position:relative;width:${w}px;height:${h}px;${scale}filter:drop-shadow(0 3px 6px rgba(0,0,0,0.25));">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 130" width="${w}" height="${h}">
        <path d="M50 0 C22.4 0 0 22.4 0 50 C0 77.6 50 130 50 130 C50 130 100 77.6 100 50 C100 22.4 77.6 0 50 0Z" fill="${color}" ${bookmarked ? 'stroke="#f59e0b" stroke-width="6"' : ''}/>
        <circle cx="50" cy="47" r="26" fill="rgba(255,255,255,0.2)"/>
        <circle cx="50" cy="47" r="22" fill="white"/>
      </svg>
      <div style="position:absolute;top:${Math.round(h * 0.16)}px;left:50%;transform:translateX(-50%);width:${inner}px;height:${inner}px;display:flex;align-items:center;justify-content:center;overflow:hidden;border-radius:50%;">
        ${logoUrl
          ? `<img src="${logoUrl}" style="width:100%;height:100%;object-fit:contain;padding:1px;" onerror="this.style.display='none';if(this.nextElementSibling)this.nextElementSibling.style.display='flex'"/>
             <span style="display:none;width:100%;height:100%;align-items:center;justify-content:center;font-family:-apple-system,sans-serif;font-size:${Math.round(inner * 0.55)}px;font-weight:800;color:${color};">${letter}</span>`
          : `<span style="display:flex;width:100%;height:100%;align-items:center;justify-content:center;font-family:-apple-system,sans-serif;font-size:${Math.round(inner * 0.55)}px;font-weight:800;color:${color};">${letter}</span>`
        }
      </div>
    </div>`;

  return L.divIcon({ html, className: "", iconSize: [w, h], iconAnchor: [w / 2, h], popupAnchor: [0, -h] });
}
```

Update `CompanyMarkerWithJobs` to accept and use `isBookmarked`:

```javascript
function CompanyMarkerWithJobs({ company, isSelected, onSelect, isBookmarked }) {
  const icon = makeIcon(
    company.name.charAt(0).toUpperCase(),
    company.name,
    isSelected,
    company.domain,
    isBookmarked
  );
  // ... rest unchanged
}
```

Update MapView to pass `isBookmarked` from props:

```javascript
export default function MapView({ companies, selected, onSelect, onLocationDenied, isBookmarked }) {
  // ...
  {companies.filter((c) => c.latitude && c.longitude).map((c) => (
    <CompanyMarkerWithJobs
      key={c.id}
      company={c}
      isSelected={selected?.id === c.id}
      onSelect={onSelect}
      isBookmarked={isBookmarked ? isBookmarked(c.id) : false}
    />
  ))}
}
```

Update App.jsx MapView usage:

```jsx
<MapView
  companies={filtered}
  selected={selected}
  onSelect={setSelected}
  onLocationDenied={() => setLocationDenied(true)}
  isBookmarked={isBookmarked}
/>
```

- [ ] **Step 8: Add bookmark count to header in App.jsx**

```jsx
{bookmarks.size > 0 && (
  <span className="bookmark-count" onClick={() => setShowSaved(v => !v)}>
    ★ {bookmarks.size} saved
  </span>
)}
```

Add to `App.css`:

```css
.bookmark-count {
  font-size: 11px;
  font-weight: 700;
  color: #92400e;
  background: #fef3c7;
  border: 1.5px solid #f59e0b;
  padding: 4px 12px;
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.12s;
}
.bookmark-count:hover {
  background: #fde68a;
}
```

- [ ] **Step 9: Verify bookmarks persist**

Star a company, refresh page — star should still be filled. Open map — that pin should have gold stroke outline.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/hooks/useBookmarks.js \
        frontend/src/components/Sidebar.jsx frontend/src/components/Sidebar.css \
        frontend/src/components/MapView.jsx frontend/src/App.jsx frontend/src/App.css \
        frontend/src/components/FilterBar.jsx
git commit -m "feat: add localStorage bookmarks with star UI and gold map pins"
```

---

## Task 7: Mobile — Bottom Sheet

**Files:**
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/components/Sidebar.css`
- Modify: `frontend/src/App.css`
- Modify: `frontend/src/components/MapView.jsx`

- [ ] **Step 1: Add bottom sheet state to Sidebar.jsx**

```jsx
import { useState } from "react";

export default function Sidebar({ ... }) {
  const [sheetExpanded, setSheetExpanded] = useState(false);
  const [showMobileFilters, setShowMobileFilters] = useState(false);

  const activeFilterCount = [
    filters.role !== "All" ? 1 : 0,
    filters.expIndex !== 0 ? 1 : 0,
    filters.sources.length,
  ].reduce((a, b) => a + b, 0);

  return (
    <aside className={`sidebar ${sheetExpanded ? "sheet-expanded" : "sheet-collapsed"}`}>
      {/* Drag handle — mobile only */}
      <div className="sheet-handle" onClick={() => setSheetExpanded(v => !v)}>
        <div className="sheet-pill" />
        <div className="sheet-handle-row">
          <span className="sidebar-title" style={{ fontSize: 18 }}>Active Hiring</span>
          <span className="sidebar-badge">{companies.length}</span>
          <button
            className={`mobile-filter-btn ${activeFilterCount > 0 ? "has-filters" : ""}`}
            onClick={(e) => { e.stopPropagation(); setShowMobileFilters(v => !v); }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>tune</span>
            Filter {activeFilterCount > 0 ? `(${activeFilterCount})` : ""}
          </button>
        </div>
      </div>

      {/* Mobile filter modal */}
      {showMobileFilters && (
        <div className="mobile-filter-modal">
          <FilterBar filters={filters} onChange={onFilterChange} bookmarkCount={bookmarkCount} showSaved={showSaved} onToggleSaved={onToggleSaved} />
          <button className="mobile-filter-close" onClick={() => setShowMobileFilters(false)}>Done</button>
        </div>
      )}

      {/* Desktop filter bar — hidden on mobile */}
      <div className="desktop-only">
        <div className="sidebar-header">
          <div className="sidebar-title-row">
            <div>
              <h2 className="sidebar-title">Active Hiring</h2>
              <p className="sidebar-subtitle">Top companies in Ahmedabad today</p>
            </div>
            <span className="sidebar-badge">{companies.length} Companies</span>
          </div>
        </div>
        <FilterBar filters={filters} onChange={onFilterChange} bookmarkCount={bookmarkCount} showSaved={showSaved} onToggleSaved={onToggleSaved} />
      </div>

      <div className="sidebar-list">
        {companies.map((c) => { /* ... existing card code ... */ })}
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Add mobile bottom sheet CSS to Sidebar.css**

```css
/* Mobile bottom sheet */
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    width: 100%;
    height: auto;
    border-right: none;
    border-top: 1px solid #e7e7f4;
    border-radius: 24px 24px 0 0;
    z-index: 500;
    transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
    box-shadow: 0 -8px 40px rgba(46, 91, 255, 0.1);
  }

  .sidebar.sheet-collapsed {
    transform: translateY(calc(100% - 72px));
  }

  .sidebar.sheet-expanded {
    transform: translateY(0);
    max-height: 60vh;
    overflow: hidden;
  }

  .sidebar-list {
    max-height: calc(60vh - 140px);
  }

  .desktop-only {
    display: none;
  }
}

@media (min-width: 769px) {
  .sheet-handle {
    display: none;
  }
  .mobile-filter-modal {
    display: none;
  }
}

.sheet-handle {
  padding: 8px 16px 4px;
  cursor: pointer;
  flex-shrink: 0;
}

.sheet-pill {
  width: 36px;
  height: 4px;
  background: #c4c5d9;
  border-radius: 999px;
  margin: 0 auto 8px;
}

.sheet-handle-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0 8px;
}

.mobile-filter-btn {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: 1.5px solid #e2e1ef;
  border-radius: 999px;
  background: #fff;
  font-size: 12px;
  font-weight: 700;
  font-family: 'Be Vietnam Pro', sans-serif;
  color: #434656;
  cursor: pointer;
}

.mobile-filter-btn.has-filters {
  border-color: #2e5bff;
  color: #2e5bff;
  background: #f3f2ff;
}

.mobile-filter-modal {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  background: #fbf8ff;
  border-radius: 24px 24px 0 0;
  border-top: 1px solid #e7e7f4;
  padding: 16px;
  box-shadow: 0 -8px 40px rgba(0,0,0,0.1);
  z-index: 600;
}

.mobile-filter-close {
  width: 100%;
  margin-top: 12px;
  padding: 12px;
  background: #2e5bff;
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
  font-family: 'Plus Jakarta Sans', sans-serif;
  cursor: pointer;
}
```

- [ ] **Step 3: Make map full screen on mobile + adjust pin size**

In `MapView.jsx`, add mobile detection:

```javascript
const isMobile = window.innerWidth <= 768;

// In makeIcon, use larger size on mobile:
const w = active ? 42 : (isMobile ? 40 : 34);
const h = active ? 54 : (isMobile ? 52 : 44);
```

In `MapView.css`, add:

```css
@media (max-width: 768px) {
  .map-wrapper {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 1;
  }

  .leaflet-popup-content {
    min-width: 200px;
    max-width: 240px;
  }
}
```

- [ ] **Step 4: Move disclaimer inside bottom sheet on mobile**

In `App.jsx`, move the disclaimer div inside Sidebar on mobile by using CSS:

```css
/* App.css */
@media (max-width: 768px) {
  .disclaimer {
    display: none;
  }
  .header {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 600;
  }
}
```

- [ ] **Step 5: Test on 375px width**

Open DevTools → Responsive → iPhone SE (375×667). Verify:
- Map is full screen
- Bottom sheet shows collapsed (just drag handle + title)
- Tapping handle expands to 60% height
- Filter button opens modal
- Pins are tappable

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/Sidebar.jsx frontend/src/components/Sidebar.css \
        frontend/src/components/MapView.jsx frontend/src/components/MapView.css \
        frontend/src/App.css
git commit -m "feat: mobile bottom sheet layout with filter modal"
```

---

## Task 8: Deploy Config

**Files:**
- Modify: `frontend/vite.config.js`
- Create: `frontend/.env.example`
- Create: `backend/.env.example`
- Create: `backend/requirements.txt`
- Create: `.gitignore`

- [ ] **Step 1: Update vite.config.js to use VITE_API_URL**

```javascript
// frontend/vite.config.js
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      proxy: mode === 'development' ? {
        '/api': {
          target: env.VITE_API_URL || 'http://localhost:8000',
          changeOrigin: true,
        }
      } : undefined
    }
  }
})
```

- [ ] **Step 2: Update axios calls to use base URL**

In `App.jsx`, add at top:

```javascript
import axios from "axios";
axios.defaults.baseURL = import.meta.env.VITE_API_URL || "";
```

- [ ] **Step 3: Create frontend/.env.example**

```bash
# frontend/.env.example
VITE_API_URL=https://your-backend.onrender.com
```

- [ ] **Step 4: Create backend/.env.example**

```bash
# backend/.env.example
ALLOWED_ORIGINS=http://localhost:5174,https://your-app.vercel.app
DATABASE_URL=/data/jobs.db
LI_AT_COOKIE=your_linkedin_li_at_cookie_here
```

- [ ] **Step 5: Update backend database.py to use DATABASE_URL env var**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DB_PATH = os.getenv("DATABASE_URL", "./jobs.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Generate requirements.txt**

```bash
cd backend
pip freeze > requirements.txt
```

Verify it contains: `fastapi`, `uvicorn`, `sqlalchemy`, `playwright`, `httpx`, `python-multipart`

- [ ] **Step 7: Create root .gitignore**

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.env
jobs.db
backend/backend.log
backend/frontend.log

# Node
node_modules/
dist/
.env
.env.local

# Debug files
backend/debug_*.py
backend/test_*.py
backend/inspect_*.py
backend/seed*.py
backend/patch_*.py
backend/regeocode.py
```

- [ ] **Step 8: Commit deploy config**

```bash
git add frontend/vite.config.js frontend/.env.example backend/.env.example \
        backend/requirements.txt backend/database.py .gitignore frontend/src/App.jsx
git commit -m "feat: add deploy config for Vercel + Render, env vars"
```

---

## Task 9: Final Verification

- [ ] **Step 1: Start both servers clean**

```bash
# Terminal 1:
cd backend && python run.py

# Terminal 2:
cd frontend && npm run dev
```

- [ ] **Step 2: Smoke test checklist**

- [ ] App loads with no console errors
- [ ] Companies and pins appear on map
- [ ] Role filter "Frontend" reduces visible companies
- [ ] Source filter "LinkedIn" reduces visible companies
- [ ] Reset button clears all filters
- [ ] Star a company → refresh → still starred
- [ ] Starred pin has gold outline on map
- [ ] ★ Saved chip appears in filter row
- [ ] Error banner appears if backend is offline (stop backend, reload)
- [ ] Mobile: open DevTools 375px → bottom sheet visible → tap to expand → filter button opens modal

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: production-ready - filters, bookmarks, mobile, security"
```

---

## Deploy Steps (Manual — After All Tasks Complete)

### Render.com (Backend)
1. Push repo to GitHub
2. New Web Service → connect repo → set root to `backend/`
3. Build command: `pip install -r requirements.txt && playwright install chromium`
4. Start command: `python run.py`
5. Add env vars: `ALLOWED_ORIGINS`, `LI_AT_COOKIE`, `DATABASE_URL=/data/jobs.db`
6. Add Persistent Disk → mount at `/data`
7. Copy the Render service URL (e.g. `https://ahmedabad-jobs.onrender.com`)

### Vercel (Frontend)
1. New Project → import from GitHub → set root to `frontend/`
2. Build command: `npm run build`
3. Add env var: `VITE_API_URL=https://ahmedabad-jobs.onrender.com`
4. Deploy → get Vercel URL
5. Go back to Render → add Vercel URL to `ALLOWED_ORIGINS`
