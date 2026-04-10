# Ahmedabad Jobs Map — Production Ready Design

**Date:** 2026-04-08
**Status:** Approved
**Primary Users:** Job seekers (developers) + recruiters, job seekers first

---

## Goals

Make the app investor-worthy and user-retaining by:
1. Fixing all known bugs and security issues (solid foundation)
2. Adding role/experience/source filters (biggest user pain point)
3. Adding localStorage bookmarks (retention mechanism)
4. Full mobile responsiveness (bottom sheet UI)
5. Deploying to production (Vercel + Render)

No auth required in this sprint.

---

## Section 1 — Foundation (Bugs + Security)

### Backend

**CORS hardening:**
- Restrict `allow_origins` from `["*"]` to `["http://localhost:5174", "https://<production-domain>.vercel.app"]`
- Read allowed origins from `ALLOWED_ORIGINS` env var (comma-separated)

**`/api/ingest` hardening:**
- Max file size: 5MB (reject with HTTP 413 if exceeded)
- MIME type check: only `application/json` and `text/csv` accepted
- Return structured error messages, not bare exceptions

**Database indexes:**
```sql
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_jobs_company_id ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
```
Added via SQLAlchemy `Index` declarations in `models.py`.

**Scraper error handling:**
- Each source (LinkedIn, Internshala, TimesJobs, Shine) wrapped in individual try/except
- Log which source failed and why (network vs parse vs timeout)
- Return partial results — don't abort entire scrape if one source fails
- Distinguish HTTP 429 (rate limit) from connection errors

### Frontend

**Remove dead code:**
- Delete `useJobsState` hook (lines 131–142 in MapView.jsx) — never functionally used

**Error UX:**
- `fetchCompanies` catch block: show a dismissible error banner ("Could not load companies — backend may be offline")
- Geolocation denied: show small non-intrusive banner "Enable location to see nearby jobs"

**Memory leak fix:**
- `popupopen` event handler: clean up listener on marker unmount via `useEffect` cleanup function

---

## Section 2 — Filters

### Architecture

All filtering is **client-side** — no new API endpoints. Filter state lives in `App.jsx` and is passed to both `Sidebar` and `MapView`.

### Filter Types

**Role filter** (pill chips, single-select + "All"):
| Chip | Matches job titles containing |
|------|-------------------------------|
| Frontend | react, vue, angular, frontend, ui, next |
| Backend | node, python, django, fastapi, java, backend, golang, ruby |
| Full Stack | full stack, fullstack, mern, mean |
| Mobile | android, ios, flutter, react native, mobile |
| DevOps | devops, cloud, aws, docker, kubernetes, ci/cd |
| Data | data, ml, machine learning, ai, analyst, spark |
| Design | figma, ux, ui design, product design |

**Experience filter** (dropdown):
- Any, Fresher (0–1yr), Junior (1–3yr), Mid (3–6yr), Senior (6yr+)
- Parsed from `job.experience` string using regex number extraction

**Source filter** (pill chips, multi-select):
- All, LinkedIn, Internshala, TimesJobs, Shine
- Matches `company.sources` array

### Filter Logic

- Filters are **ANDed** across types
- A company passes if it has **at least one job** matching all active filters
- Companies with 0 matching jobs: hidden from sidebar AND removed from map
- Sidebar badge updates to show filtered count
- Filters reset button appears when any filter is active

### UI Placement

- Filter bar sits between sidebar header and company list
- Role chips scroll horizontally on mobile
- Source chips below role chips
- Experience dropdown inline with source chips

---

## Section 3 — Bookmarks

### Storage

```js
// localStorage key
"ahmedabad-jobs-bookmarks" = "[1, 5, 23]"  // array of company IDs
```

Custom hook `useBookmarks()` in `src/hooks/useBookmarks.js`:
- `bookmarks`: Set of company IDs
- `toggle(id)`: add/remove from set, persist to localStorage
- `isBookmarked(id)`: boolean check

### UI

**Sidebar cards:** Star icon (☆/★) top-right corner of each card. Filled gold when bookmarked.

**Map pins:** Bookmarked companies get a gold `ring-4 ring-yellow-400` outline on their pin icon.

**Saved filter:** New `⭐ Saved` pill chip in the source filter row. When active, sidebar and map show only bookmarked companies.

**Header:** Bookmark count badge next to company count when bookmarks > 0: `★ 3 saved`

### Behaviour

- Bookmark persists across page refreshes and browser sessions
- No backend changes — purely frontend
- Toggling bookmark updates map pin style immediately (reactive via state)

---

## Section 4 — Mobile + Deploy

### Mobile (breakpoint: 768px)

**Layout:**
- Map takes full screen (`100vw × 100vh`) on mobile
- Sidebar becomes a **bottom sheet** — fixed bottom, `border-radius: 24px 24px 0 0`

**Bottom sheet states:**
- **Collapsed:** shows only header bar (drag handle + "Active Hiring" + count) — height ~72px
- **Expanded:** slides up to 60% screen height, scrollable company list inside
- Drag handle (pill) at top — tap to toggle, swipe up/down to expand/collapse
- Map still interactable in background when collapsed

**Filters on mobile:**
- Filter bar hidden by default
- Single "⚙ Filter" button in bottom sheet header — taps open a modal bottom sheet with all filter controls
- Active filter count shown on button badge: `⚙ Filter (2)`

**Pins:**
- `iconSize` increases from `[34,44]` to `[40,52]` on mobile for easier tapping
- Popup `maxWidth` reduced to 240px on mobile

**Disclaimer:**
- Moves inside bottom sheet footer on mobile (not floating over map)

### Deploy

**Frontend — Vercel:**
- `VITE_API_URL` env var — all `axios` calls use this base URL
- `vite.config.js` proxy only active in dev (`mode === 'development'`)
- Build command: `npm run build`, output: `dist/`

**Backend — Render.com:**
- Free tier web service, Python 3.12
- Persistent disk mounted at `/data` for `jobs.db`
- `DATABASE_URL` env var points to `/data/jobs.db`
- `ALLOWED_ORIGINS` env var set to Vercel domain
- Start command: `python run.py`

**Environment files:**
- `.env.example` created for both frontend and backend
- `.env` added to `.gitignore`
- LinkedIn `li_at` cookie stored as `LI_AT_COOKIE` env var on Render

---

## Implementation Order

1. Foundation fixes (backend security + frontend bugs)
2. DB indexes
3. Filters (client-side, no backend changes)
4. Bookmarks hook + UI
5. Mobile bottom sheet
6. Deploy config (env vars, Vercel, Render)

---

## Out of Scope (This Sprint)

- User authentication
- Recruiter dashboard / featured pins
- Push notifications / job alerts
- Company profile pages
- Monetization

---

## Success Criteria

- Zero console errors on fresh load
- Filters reduce visible companies + pins correctly
- Bookmarks survive page refresh
- App fully usable on iPhone SE (375px width)
- Backend deployed, frontend deployed, both talking to each other
- No `*` CORS, no unprotected ingest endpoint
